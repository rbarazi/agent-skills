# OAuth Token Service

## Purpose
Manage token issuance, validation, and lifecycle with timing-attack resistant operations.

## Token Service

```ruby
# app/services/token_service.rb
class TokenService
  ACCESS_TOKEN_TTL = 1.hour
  AUTHORIZATION_CODE_TTL = 10.minutes

  # Issue a new access token
  def self.issue_access_token(oauth_client:, user: nil, authorization_code: nil, scopes: [])
    OAuthAccessToken.create!(
      oauth_client: oauth_client,
      user: user,
      authorization_code: authorization_code,
      token: generate_secure_token,
      expires_at: ACCESS_TOKEN_TTL.from_now,
      token_metadata: {
        scopes: scopes,
        token_type: "Bearer",
        issued_at: Time.current.to_i
      }
    )
  end

  # Issue authorization code
  def self.issue_authorization_code(oauth_client:, user:, redirect_uri:, code_challenge: nil, code_challenge_method: nil, scopes: [])
    OAuthAuthorizationCode.create!(
      oauth_client: oauth_client,
      user: user,
      code: generate_secure_token,
      redirect_uri: redirect_uri,
      expires_at: AUTHORIZATION_CODE_TTL.from_now,
      pkce_data: {
        code_challenge: code_challenge,
        code_challenge_method: code_challenge_method,
        scopes: scopes
      }.compact
    )
  end

  # Timing-safe token validation
  def self.validate_access_token(token)
    return nil if token.blank? || token.length < 32

    # Get candidates for constant-time comparison
    candidates = OAuthAccessToken.valid
      .joins(:oauth_client)
      .where(oauth_clients: { active: true })
      .limit(100)

    found_token = nil

    # Constant-time comparison loop
    candidates.each do |candidate|
      if ActiveSupport::SecurityUtils.secure_compare(candidate.token, token)
        found_token = candidate
      end
    end

    # Always do dummy comparison for timing consistency
    unless found_token
      ActiveSupport::SecurityUtils.secure_compare(token, "x" * token.length)
    end

    return nil unless found_token
    return nil if found_token.expires_at <= Time.current
    return nil unless found_token.oauth_client&.active?

    found_token
  end

  # Get token info (for introspection)
  def self.token_info(token)
    access_token = validate_access_token(token)
    return nil unless access_token

    {
      active: true,
      client_id: access_token.oauth_client.client_id,
      user_id: access_token.user&.id,
      scopes: access_token.scopes || [],
      expires_at: access_token.expires_at.iso8601,
      issued_at: Time.at(access_token.token_metadata["issued_at"]).iso8601
    }
  end

  # Revoke a token
  def self.revoke_token(token)
    access_token = OAuthAccessToken.find_by(token: token)
    return false unless access_token
    access_token.destroy
    true
  end

  # Cleanup expired tokens
  def self.cleanup_expired_tokens
    expired_tokens = OAuthAccessToken.where("expires_at < ?", Time.current).count
    expired_codes = OAuthAuthorizationCode.where("expires_at < ?", Time.current).count

    OAuthAccessToken.where("expires_at < ?", Time.current).delete_all
    OAuthAuthorizationCode.where("expires_at < ?", Time.current).delete_all

    {
      access_tokens_removed: expired_tokens,
      authorization_codes_removed: expired_codes
    }
  end

  private

  def self.generate_secure_token
    SecureRandom.urlsafe_base64(32)
  end
end
```

## Security Configuration

```ruby
# config/initializers/oauth_security.rb
class OAuthSecurityConfig
  class << self
    def token_lifetime
      ENV.fetch("OAUTH_TOKEN_LIFETIME", 3600).to_i
    end

    def code_lifetime
      ENV.fetch("OAUTH_CODE_LIFETIME", 600).to_i
    end

    def refresh_token_lifetime
      ENV.fetch("OAUTH_REFRESH_TOKEN_LIFETIME", 86400).to_i
    end

    def require_pkce_for_public_clients?
      ENV.fetch("OAUTH_REQUIRE_PKCE", "true") == "true"
    end
  end
end
```

## Authentication Concern

```ruby
# app/controllers/concerns/oauth_authentication.rb
module OAuthAuthentication
  extend ActiveSupport::Concern

  included do
    before_action :authenticate_oauth_token, if: :oauth_protected?
  end

  def authenticate_oauth_token
    token = extract_bearer_token
    return render_oauth_error("invalid_token") unless token

    @current_access_token = TokenService.validate_access_token(token)
    return render_oauth_error("invalid_token") unless @current_access_token

    @current_oauth_client = @current_access_token.oauth_client
    @current_user = @current_access_token.user
  end

  def oauth_authenticated?
    @current_access_token.present?
  end

  private

  def extract_bearer_token
    auth_header = request.headers["Authorization"]
    return nil unless auth_header&.start_with?("Bearer ")
    auth_header.split(" ", 2).last
  end

  def oauth_protected?
    false  # Override in controllers
  end

  def render_oauth_error(error_code, description = nil, status = :unauthorized)
    render json: {
      error: error_code,
      error_description: description
    }.compact, status: status
  end
end
```

## Cleanup Task

```ruby
# lib/tasks/oauth.rake
namespace :oauth do
  desc "Clean up expired OAuth tokens and codes"
  task cleanup: :environment do
    result = TokenService.cleanup_expired_tokens
    puts "Removed #{result[:access_tokens_removed]} tokens, #{result[:authorization_codes_removed]} codes"
  end

  desc "Revoke all tokens for a client"
  task :revoke_client, [:client_id] => :environment do |_, args|
    client = OAuthClient.find_by!(client_id: args[:client_id])
    count = client.oauth_access_tokens.delete_all
    puts "Revoked #{count} tokens for client #{args[:client_id]}"
  end
end
```

Schedule cleanup:

```ruby
# config/schedule.rb (whenever gem)
every 1.hour do
  rake "oauth:cleanup"
end
```

## Testing

```ruby
RSpec.describe TokenService do
  describe ".issue_access_token" do
    it "creates token with correct attributes" do
      client = create(:oauth_client)
      scopes = %w[read write]

      token = described_class.issue_access_token(
        oauth_client: client,
        scopes: scopes
      )

      expect(token.token).to be_present
      expect(token.expires_at).to be > Time.current
      expect(token.scopes).to eq(scopes)
    end
  end

  describe ".validate_access_token" do
    it "returns valid token" do
      token = create(:oauth_access_token)

      result = described_class.validate_access_token(token.token)

      expect(result).to eq(token)
    end

    it "returns nil for expired token" do
      token = create(:oauth_access_token, expires_at: 1.hour.ago)

      result = described_class.validate_access_token(token.token)

      expect(result).to be_nil
    end

    it "returns nil for inactive client" do
      client = create(:oauth_client, active: false)
      token = create(:oauth_access_token, oauth_client: client)

      result = described_class.validate_access_token(token.token)

      expect(result).to be_nil
    end
  end

  describe ".cleanup_expired_tokens" do
    it "removes expired tokens" do
      create(:oauth_access_token, expires_at: 1.hour.ago)
      valid_token = create(:oauth_access_token)

      result = described_class.cleanup_expired_tokens

      expect(result[:access_tokens_removed]).to eq(1)
      expect(OAuthAccessToken.exists?(valid_token.id)).to be true
    end
  end
end
```

## Next Steps

- [Monitoring](05-monitoring.md) - Audit and cleanup
