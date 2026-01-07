# Slack OAuth Integration

## Required Scopes

```ruby
OAUTH_SCOPES = [
  "app_mentions:read",    # Listen for @mentions
  "channels:history",     # Access channel messages
  "chat:write",           # Send messages
  "files:read",           # Process file uploads
  "reactions:read",       # Track reactions
  "reactions:write",      # Add status reactions
  "users:read",           # User info lookup
].freeze
```

Add `assistant:write` for Slack Assistant features.

## SlackChannel Model

```ruby
class SlackChannel < AgentChannel
  include ChannelClient
  include ChannelOAuth

  OAUTH_VERSION = "v2"
  OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"

  validates :signing_secret, presence: true, if: :active?
  has_many :user_slack_channels, foreign_key: :agent_channel_id

  def oauth_authorize_url(params = {})
    super(params.merge(scope: oauth_scopes.join(",")))
  end

  def fetch_oauth_access(code)
    client.send(:oauth_v2_access, {
      client_id:,
      client_secret:,
      code: code
    })
  end

  def from_oauth!(code, user_id)
    rc = fetch_oauth_access(code)
    channel = user_slack_channels.with_team_id(rc.team&.id).first

    if channel
      channel.health_check!(rc)
    else
      user_slack_channels.create!(
        user_id:,
        token: rc.access_token,
        team_id: rc.team&.id,
        name: rc.team&.name
      )
    end
  end

  private

  def build_client
    Slack::Web::Client.new
  end
end
```

## UserSlackChannel Model

```ruby
class UserSlackChannel < UserAgentChannel
  store_accessor :channel_info, :domain, :name, :team_id

  scope :with_token, ->(token) { where(token: token) }
  scope :with_team_id, ->(team_id) { where("channel_info->>'team_id' = ?", team_id) }

  def client
    @client ||= Slack::Web::Client.new(token:)
  end

  def health_check!(rc)
    update!(oauth_scopes: rc.scope, activated_user_id: rc.authed_user&.id)
    activate!(rc.access_token)
  end
end
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SLACK_CLIENT_ID` | OAuth client ID |
| `SLACK_CLIENT_SECRET` | OAuth client secret |
| `SLACK_SIGNING_SECRET` | Webhook signature verification |
