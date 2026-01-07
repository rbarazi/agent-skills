# OAuth Client Management

## Purpose
Implement dynamic client registration (RFC 7591) and client lifecycle management.

## Client Registration Service

```ruby
# app/services/client_registration_service.rb
class ClientRegistrationService
  include ActiveModel::Model

  attr_reader :oauth_client
  attr_accessor :client_name, :client_type, :client_uri, :redirect_uris,
                :grant_types, :response_types, :token_endpoint_auth_method, :scopes

  validates :client_type, inclusion: { in: %w[public confidential] }
  validate :validate_redirect_uris
  validate :validate_grant_types

  def initialize(params = {})
    @client_name = params[:client_name]
    @client_type = params[:client_type] || "public"
    @client_uri = params[:client_uri]
    @redirect_uris = Array(params[:redirect_uris]).compact
    @grant_types = Array(params[:grant_types]).presence || %w[authorization_code]
    @response_types = Array(params[:response_types]).presence || %w[code]
    @token_endpoint_auth_method = params[:token_endpoint_auth_method] || default_auth_method
    @scopes = params[:scopes]&.split(" ") || default_scopes
  end

  def register
    return false unless valid?

    @oauth_client = OAuthClient.new(
      name: client_name || "OAuth Client #{SecureRandom.hex(4)}",
      client_type: client_type,
      oauth_metadata: {
        client_uri: client_uri,
        redirect_uris: redirect_uris,
        grant_types: grant_types,
        response_types: response_types,
        token_endpoint_auth_method: token_endpoint_auth_method,
        scopes: scopes
      }
    )

    if @oauth_client.save
      @oauth_client
    else
      errors.merge!(@oauth_client.errors)
      false
    end
  end

  private

  def default_auth_method
    client_type == "public" ? "none" : "client_secret_basic"
  end

  def default_scopes
    %w[read write]
  end

  def validate_redirect_uris
    validator = OAuthRedirectUriValidator.new(client_type: client_type)
    validator.validate(redirect_uris)
  rescue ArgumentError => e
    errors.add(:redirect_uris, e.message)
  end

  def validate_grant_types
    supported = %w[authorization_code client_credentials refresh_token]
    invalid = grant_types - supported
    errors.add(:grant_types, "unsupported: #{invalid.join(', ')}") if invalid.any?
  end
end
```

## Redirect URI Validator

```ruby
# app/models/oauth_redirect_uri_validator.rb
class OAuthRedirectUriValidator
  LOCALHOST_PATTERNS = [
    /\Ahttp:\/\/localhost(:\d+)?(\/.*)?/,
    /\Ahttp:\/\/127\.0\.0\.1(:\d+)?(\/.*)?/,
    /\Ahttp:\/\/\[::1\](:\d+)?(\/.*)?/
  ].freeze

  def initialize(client_type:)
    @client_type = client_type
  end

  def validate(uris)
    raise ArgumentError, "At least one redirect_uri required" if uris.empty?

    uris.each { |uri| validate_uri(uri) }
    true
  end

  private

  def validate_uri(uri)
    parsed = URI.parse(uri)

    # Must be absolute URI
    raise ArgumentError, "#{uri} must be absolute URI" unless parsed.absolute?

    # HTTPS required for production, HTTP allowed for localhost
    if parsed.scheme == "http"
      unless localhost_uri?(uri)
        raise ArgumentError, "#{uri} must use HTTPS (except localhost)"
      end
    elsif parsed.scheme != "https"
      raise ArgumentError, "#{uri} must use HTTPS scheme"
    end

    # No fragments allowed
    raise ArgumentError, "#{uri} must not contain fragments" if parsed.fragment
  end

  def localhost_uri?(uri)
    LOCALHOST_PATTERNS.any? { |pattern| uri.match?(pattern) }
  end
end
```

## Registration Endpoint

```ruby
# In OAuthController
def register
  service = ClientRegistrationService.new(registration_params.to_h)
  oauth_client = service.register

  if oauth_client
    render json: client_registration_response(oauth_client), status: :created
  else
    render_oauth_error("invalid_client_metadata", service.errors.full_messages.to_sentence)
  end
end

def registration_params
  params.permit(
    :client_name,
    :client_type,
    :client_uri,
    :scopes,
    :token_endpoint_auth_method,
    redirect_uris: [],
    grant_types: [],
    response_types: []
  )
end

def client_registration_response(oauth_client)
  {
    client_id: oauth_client.client_id,
    client_name: oauth_client.name,
    client_type: oauth_client.client_type,
    grant_types: oauth_client.grant_types || [],
    redirect_uris: oauth_client.redirect_uris || [],
    scope: (oauth_client.scopes || []).join(" "),
    token_endpoint_auth_method: oauth_client.token_endpoint_auth_method
  }.tap do |response|
    # Include secret for confidential clients
    response[:client_secret] = oauth_client.client_secret if oauth_client.confidential?
  end
end
```

## Client Types

| Type | Description | Auth Method | PKCE Required |
|------|-------------|-------------|---------------|
| `public` | Browser/mobile apps | none | Yes |
| `confidential` | Server-side apps | client_secret_basic | No |

## Usage Example

### Register a Public Client

```bash
curl -X POST https://your-app.com/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Mobile App",
    "client_type": "public",
    "redirect_uris": ["myapp://callback"],
    "grant_types": ["authorization_code"],
    "scopes": "read write"
  }'
```

Response:
```json
{
  "client_id": "abc123...",
  "client_name": "My Mobile App",
  "client_type": "public",
  "redirect_uris": ["myapp://callback"],
  "scope": "read write"
}
```

### Register a Confidential Client

```bash
curl -X POST https://your-app.com/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Backend Service",
    "client_type": "confidential",
    "redirect_uris": ["https://service.example.com/callback"],
    "grant_types": ["client_credentials", "authorization_code"]
  }'
```

Response:
```json
{
  "client_id": "xyz789...",
  "client_secret": "secret...",
  "client_name": "Backend Service",
  "client_type": "confidential"
}
```

## Testing

```ruby
RSpec.describe ClientRegistrationService do
  describe "#register" do
    it "creates public client without secret" do
      service = described_class.new(
        client_name: "Test App",
        client_type: "public",
        redirect_uris: ["http://localhost:3000/callback"]
      )

      client = service.register

      expect(client).to be_present
      expect(client.client_secret).to be_nil
      expect(client.public?).to be true
    end

    it "creates confidential client with secret" do
      service = described_class.new(
        client_name: "Server App",
        client_type: "confidential",
        redirect_uris: ["https://app.example.com/callback"]
      )

      client = service.register

      expect(client).to be_present
      expect(client.client_secret).to be_present
      expect(client.confidential?).to be true
    end

    it "rejects HTTP URIs for production" do
      service = described_class.new(
        redirect_uris: ["http://example.com/callback"]
      )

      expect(service.register).to be false
      expect(service.errors[:redirect_uris]).to be_present
    end
  end
end
```

## Next Steps

- [Token Service](04-token-service.md) - Token lifecycle
- [Monitoring](05-monitoring.md) - Audit and cleanup
