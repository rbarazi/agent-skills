# MCP Session Management

## Purpose
Track MCP client sessions for both OAuth-authenticated and legacy clients. Manage session lifecycle, expiry, and scope validation.

## Models

### MCP::Client (Legacy)

Simple client registration for non-OAuth MCP clients:

```ruby
# app/models/mcp/client.rb
class MCP::Client < ApplicationRecord
  belongs_to :tool
  has_many :sessions, class_name: "MCP::ClientSession", dependent: :destroy

  validates :name, presence: true
  validates :mcp_server_name, presence: true
  validates :tool, presence: true
end
```

### MCP::ClientSession

Track active MCP sessions with OAuth or legacy authentication:

```ruby
# app/models/mcp/client_session.rb
class MCP::ClientSession < ApplicationRecord
  belongs_to :client, class_name: "MCP::Client", optional: true
  belongs_to :tool
  belongs_to :oauth_client, class_name: "OAuthClient", optional: true
  belongs_to :access_token, class_name: "OAuthAccessToken", optional: true

  validates :tool, presence: true
  validates :mcp_server_name, presence: true

  # Validate authentication method
  validate :has_authentication_method

  # Scopes
  scope :oauth_authenticated, -> { joins(:access_token) }
  scope :legacy_authenticated, -> { joins(:client) }
  scope :valid_oauth_sessions, -> {
    joins(:access_token).where(
      oauth_access_tokens: { expires_at: Time.current.. }
    )
  }
  scope :valid_sessions, -> { where("expires_at > ?", Time.current) }

  # Check authentication type
  def oauth_authenticated?
    access_token.present? && access_token.token_valid?
  end

  def legacy_authenticated?
    client.present?
  end

  # Get account context from session
  def current_account
    if oauth_authenticated?
      access_token.user&.account || Current.account
    else
      client&.account || tool&.account || Current.account
    end
  end

  # Enhanced validity check for OAuth sessions
  def valid?(context = nil)
    return super(context) unless oauth_authenticated?

    super(context) &&
      expires_at > Time.current &&
      access_token.token_valid? &&
      oauth_client.active?
  end

  def expired?
    Time.current > effective_expires_at
  end

  def effective_expires_at
    return expires_at unless oauth_authenticated?
    [expires_at, access_token.expires_at].min
  end

  # Extend session on activity
  def extend_activity!
    new_expiry = 30.minutes.from_now
    # Don't extend beyond token expiry for OAuth
    new_expiry = [new_expiry, access_token.expires_at].min if oauth_authenticated?

    update!(
      last_activity_at: Time.current,
      expires_at: new_expiry
    )
  end

  # Scope checking
  def available_scopes
    return [] unless oauth_authenticated?
    @available_scopes ||= access_token.token_metadata["scopes"] || []
  end

  def has_scope?(required_scope)
    return true unless oauth_authenticated?  # Legacy has full access
    available_scopes.include?(required_scope) || available_scopes.include?("mcp:*")
  end

  private

  def has_authentication_method
    both_present = oauth_client.present? && client.present?

    if both_present
      errors.add(:base, "Cannot have both OAuth and legacy client")
    end

    if oauth_client.blank? && client.blank?
      errors.add(:base, "Must have OAuth or legacy client")
    end

    if oauth_client.present? && access_token.blank?
      errors.add(:access_token, "required for OAuth sessions")
    end
  end
end
```

## Database Migration

```ruby
# db/migrate/create_mcp_client_sessions.rb
class CreateMCPClientSessions < ActiveRecord::Migration[7.0]
  def change
    create_table :mcp_client_sessions, id: :uuid do |t|
      t.references :client, type: :uuid, foreign_key: { to_table: :mcp_clients }, null: true
      t.references :tool, type: :uuid, foreign_key: true, null: false
      t.references :oauth_client, type: :uuid, foreign_key: true, null: true
      t.references :access_token, type: :uuid, foreign_key: { to_table: :oauth_access_tokens }, null: true

      t.string :mcp_server_name, null: false
      t.jsonb :client_info_snapshot
      t.datetime :expires_at, null: false
      t.datetime :last_activity_at

      t.timestamps

      t.index :mcp_server_name
      t.index :expires_at
    end

    create_table :mcp_clients, id: :uuid do |t|
      t.references :tool, type: :uuid, foreign_key: true, null: false

      t.string :name, null: false
      t.string :mcp_server_name, null: false

      t.timestamps

      t.index [:tool_id, :name], unique: true
    end
  end
end
```

## Controller Integration

Session handling in the MCP servers controller:

```ruby
# In MCP::ServersController

def find_or_create_session
  session_id = request.headers["Mcp-Session-Id"]

  if oauth_authenticated?
    find_or_create_oauth_session(session_id)
  else
    find_or_create_legacy_session(session_id)
  end
end

def find_or_create_oauth_session(session_id)
  session = tool.mcp_client_sessions.find_by(
    id: session_id,
    oauth_client_id: @current_oauth_client.id,
    access_token_id: @current_access_token.id
  )

  if session&.valid?
    if rpc_params&.dig(:method) == "initialize"
      return create_oauth_session
    end
    extend_session_activity(session)
    session
  elsif rpc_params&.dig(:method) == "initialize"
    create_oauth_session
  else
    raise InvalidSessionError, "OAuth session not found or expired"
  end
end

def find_or_create_legacy_session(session_id)
  session = tool.mcp_client_sessions.find_by(id: session_id) if session_id.present?

  if session&.valid? && !session.expired?
    extend_session_activity(session) unless rpc_params&.dig(:method) == "initialize"
    session
  elsif rpc_params&.dig(:method) == "initialize"
    create_legacy_session
  elsif session_id.blank?
    raise InvalidSessionError, "Session not found"
  elsif session&.expired?
    raise SessionExpiredError, "Session expired at #{session.expires_at}"
  else
    raise InvalidSessionError, "Session not found"
  end
end

def create_oauth_session
  MCP::ClientSession.create!(
    tool: tool,
    oauth_client: @current_oauth_client,
    access_token: @current_access_token,
    mcp_server_name: tool.name,
    client_info_snapshot: rpc_params&.dig(:params, :clientInfo),
    expires_at: [@current_access_token.expires_at, 30.minutes.from_now].min,
    last_activity_at: Time.current
  )
end

def create_legacy_session
  client = MCP::Client.find_or_create_by!(
    tool: tool,
    mcp_server_name: tool.name
  ) do |c|
    c.name = "Default Client for #{tool.name}"
  end

  MCP::ClientSession.create!(
    tool: tool,
    client: client,
    mcp_server_name: tool.name,
    client_info_snapshot: rpc_params&.dig(:params, :clientInfo),
    expires_at: 30.minutes.from_now,
    last_activity_at: Time.current
  )
end

def extend_session_activity(session)
  session.extend_activity!
end
```

## Scope Validation

Define and validate required scopes for MCP methods:

```ruby
def validate_mcp_access_scope
  required_scopes = determine_required_scopes

  has_required_scope = required_scopes.any? do |scope|
    mcp_client_session.has_scope?(scope)
  end

  render_oauth_error("insufficient_scope") unless has_required_scope
end

def determine_required_scopes
  case rpc_params&.dig(:method)
  when "ping", "tools/list", "resources/list", "prompts/list"
    %w[mcp:read]
  when "tools/call"
    %w[mcp:write]
  when "initialize"
    %w[mcp:admin]
  else
    %w[mcp:admin]
  end
end
```

## Usage in MCP Servers

Access session data in your MCP server implementation:

```ruby
class MyMCPServer < BaseMCPServer
  tool :user_data

  def user_data(query:)
    # Access session info
    account = session.current_account
    user = session.access_token&.user

    # Check scopes
    unless session.has_scope?("mcp:read")
      return { content: [{ type: "text", text: "Insufficient scope" }], isError: true }
    end

    # Use account context
    data = account.users.where("name LIKE ?", "%#{query}%")

    {
      content: [{ type: "text", text: data.to_json }],
      isError: false
    }
  end
end
```

## Session Cleanup

Rake task to clean expired sessions:

```ruby
# lib/tasks/mcp.rake
namespace :mcp do
  desc "Clean expired MCP client sessions"
  task cleanup_sessions: :environment do
    expired_count = MCP::ClientSession.where("expires_at < ?", Time.current).delete_all
    puts "Deleted #{expired_count} expired sessions"
  end
end
```

Schedule via whenever or sidekiq-cron:

```ruby
# config/schedule.rb
every 1.hour do
  rake "mcp:cleanup_sessions"
end
```

## Testing

```ruby
RSpec.describe MCP::ClientSession do
  describe "#oauth_authenticated?" do
    it "returns true when access token is present and valid" do
      token = create(:oauth_access_token, :valid)
      session = create(:mcp_client_session, access_token: token)

      expect(session.oauth_authenticated?).to be true
    end

    it "returns false when access token is expired" do
      token = create(:oauth_access_token, :expired)
      session = create(:mcp_client_session, access_token: token)

      expect(session.oauth_authenticated?).to be false
    end
  end

  describe "#extend_activity!" do
    it "extends session expiry" do
      session = create(:mcp_client_session, expires_at: 5.minutes.from_now)

      expect {
        session.extend_activity!
      }.to change { session.reload.expires_at }

      expect(session.expires_at).to be > 25.minutes.from_now
    end

    it "does not extend beyond token expiry for OAuth" do
      token_expiry = 10.minutes.from_now
      token = create(:oauth_access_token, expires_at: token_expiry)
      session = create(:mcp_client_session, access_token: token)

      session.extend_activity!

      expect(session.expires_at).to be <= token_expiry
    end
  end

  describe "#has_scope?" do
    it "returns true for legacy sessions" do
      session = create(:mcp_client_session, :legacy)

      expect(session.has_scope?("mcp:write")).to be true
    end

    it "checks OAuth token scopes" do
      token = create(:oauth_access_token,
        token_metadata: { "scopes" => ["mcp:read"] })
      session = create(:mcp_client_session, access_token: token)

      expect(session.has_scope?("mcp:read")).to be true
      expect(session.has_scope?("mcp:write")).to be false
    end
  end
end
```

## Next Steps

- [Multi-Worker Coordination](07-multi-worker-coordination.md) - Database locks for subprocess ownership
