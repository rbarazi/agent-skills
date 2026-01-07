# MCP OAuth Flow

## Purpose
Handle OAuth 2.1 authentication for MCP servers. Supports both machine-to-machine (client credentials) and interactive (authorization code + PKCE) flows.

## Configuration

Set redirect URI in application constants:

```ruby
# config/initializers/application_constants.rb
APP_PROTOCOL = ENV.fetch("APP_PROTOCOL", "https")
APP_URL = ENV["APP_URL"]
MCP_OAUTH_REDIRECT_URI = "#{APP_PROTOCOL}://#{APP_URL}/mcp/oauth/callback"
```

## OAuth Flow Class

Encapsulates OAuth discovery (RFC 8414), PKCE, and client credentials flows.

```ruby
# app/services/mcp_client/oauth_flow.rb
class MCPClient
  class OAuthFlow
    attr_accessor :access_token, :token_endpoint, :client_id, :client_secret,
                  :authorization_endpoint, :pending_state, :pending_code_verifier,
                  :endpoint

    def initialize(endpoint: nil,
                   access_token: nil,
                   token_endpoint: nil,
                   client_id: nil,
                   client_secret: nil,
                   authorization_endpoint: nil,
                   pending_state: nil,
                   pending_code_verifier: nil)
      @endpoint = endpoint
      @access_token = access_token
      @token_endpoint = token_endpoint
      @client_id = client_id
      @client_secret = client_secret
      @authorization_endpoint = authorization_endpoint
      @pending_state = pending_state
      @pending_code_verifier = pending_code_verifier
    end

    # Reset access token when it becomes invalid/expired
    def reset_access_token!
      @access_token = nil
    end

    # -----------------------------------------------------------------
    # Machine-to-Machine (Client Credentials)
    # -----------------------------------------------------------------

    # Perform OAuth 2.0 Client Credentials flow.
    # Returns true when authentication succeeded.
    def authenticate_with_client_credentials!
      return false unless @token_endpoint && @client_id && @client_secret

      oauth = MCPOAuthClient.new(
        token_endpoint: @token_endpoint,
        client_id: @client_id,
        client_secret: @client_secret
      )
      token = oauth.fetch_token
      if token
        @access_token = token
        true
      else
        false
      end
    rescue StandardError => e
      Rails.logger.error("MCP OAuth client_credentials error: #{e.message}")
      false
    end

    # -----------------------------------------------------------------
    # Interactive PKCE Flow
    # -----------------------------------------------------------------

    # Build authorization URL from WWW-Authenticate header or discovery.
    # Returns URL string or nil when discovery fails.
    def authorization_url_from_error(error)
      header = error.response&.dig(:response_headers, "www-authenticate")
      metadata_url = parse_www_authenticate(header)

      # Try metadata URL from challenge first
      if metadata_url
        url = discover_authorization_url(metadata_url)
        return url if url
      end

      # Fallback: discovery relative to MCP endpoint
      discover_authorization_from_endpoint
    end

    # Exchange authorization code for access token using PKCE verifier.
    # Returns true when exchange succeeded.
    def exchange_code(code, state)
      discover_authorization_from_endpoint if @token_endpoint.nil?
      return false unless @token_endpoint && @client_id

      resp = Faraday.post(@token_endpoint, {
        grant_type: "authorization_code",
        code: code,
        redirect_uri: MCP_OAUTH_REDIRECT_URI,
        client_id: @client_id,
        code_verifier: @pending_code_verifier
      }, "Content-Type" => "application/x-www-form-urlencoded")

      data = JSON.parse(resp.body)
      @access_token = data["access_token"]

      if @access_token
        @pending_state = nil
        @pending_code_verifier = nil
        true
      else
        false
      end
    rescue StandardError => e
      Rails.logger.error("MCP OAuth code exchange error: #{e.message}")
      false
    end

    private

    # -----------------------------------------------------------------
    # Discovery (RFC 8414)
    # -----------------------------------------------------------------

    def parse_www_authenticate(header)
      return nil unless header
      match = header.match(/authorization_uri="([^\"]+)"/i)
      match && match[1]
    end

    def discover_authorization_from_endpoint
      return nil unless @endpoint

      uri = URI(@endpoint)
      base = "#{uri.scheme}://#{uri.host}"
      base += ":#{uri.port}" if uri.port && uri.port != uri.default_port

      as_meta = get_json("#{base}/.well-known/oauth-authorization-server")
      @token_endpoint ||= as_meta["token_endpoint"]
      @authorization_endpoint = as_meta["authorization_endpoint"]
      registration_endpoint = as_meta["registration_endpoint"]

      # Dynamic client registration if no client_id
      register_client(registration_endpoint) if @client_id.nil? && registration_endpoint
      build_authorization_url
    rescue StandardError => e
      Rails.logger.debug("OAuth discovery failed: #{e.class}: #{e.message}")
      nil
    end

    def discover_authorization_url(resource_metadata_url)
      resource_meta = get_json(resource_metadata_url)
      as = resource_meta["authorization_servers"]&.first
      return nil unless as

      as_meta = get_json("#{as}/.well-known/oauth-authorization-server")
      @token_endpoint ||= as_meta["token_endpoint"]
      @authorization_endpoint = as_meta["authorization_endpoint"]
      registration_endpoint = as_meta["registration_endpoint"]

      register_client(registration_endpoint) if @client_id.nil? && registration_endpoint
      build_authorization_url
    rescue StandardError => e
      Rails.logger.debug("Resource OAuth discovery failed: #{e.message}")
      nil
    end

    def get_json(url)
      resp = Faraday.get(url)
      JSON.parse(resp.body)
    end

    # -----------------------------------------------------------------
    # Dynamic Client Registration (RFC 7591)
    # -----------------------------------------------------------------

    def register_client(registration_endpoint)
      resp = Faraday.post(registration_endpoint, {
        redirect_uris: [MCP_OAUTH_REDIRECT_URI],
        client_name: "Agentify MCP Client",
        token_endpoint_auth_method: "none"
      }.to_json, "Content-Type" => "application/json")

      data = JSON.parse(resp.body)
      @client_id = data["client_id"]
      @client_secret = data["client_secret"]
    end

    # -----------------------------------------------------------------
    # PKCE URL Building
    # -----------------------------------------------------------------

    def build_authorization_url
      return nil unless @authorization_endpoint && @client_id

      # Reuse verifier/state to avoid out-of-sync OAuth flows
      @pending_code_verifier ||= SecureRandom.urlsafe_base64(32)
      @pending_state ||= SecureRandom.hex(8)

      challenge = Base64.urlsafe_encode64(
        Digest::SHA256.digest(@pending_code_verifier)
      ).delete("=")

      uri = URI(@authorization_endpoint)
      params = URI.decode_www_form(uri.query.to_s)
      params << ["response_type", "code"]
      params << ["client_id", @client_id]
      params << ["redirect_uri", MCP_OAUTH_REDIRECT_URI]
      params << ["code_challenge", challenge]
      params << ["code_challenge_method", "S256"]
      params << ["state", @pending_state]
      uri.query = URI.encode_www_form(params)
      uri.to_s
    end
  end
end
```

## Simple OAuth Client

For machine-to-machine client credentials flow:

```ruby
# app/services/mcp_oauth_client.rb
class MCPOAuthClient
  def initialize(token_endpoint:, client_id:, client_secret:)
    @token_endpoint = token_endpoint
    @client_id = client_id
    @client_secret = client_secret
    @conn = Faraday.new(url: token_endpoint) do |f|
      f.request :url_encoded
      f.response :raise_error
      f.adapter :net_http
    end
  end

  def fetch_token
    resp = @conn.post do |req|
      req.headers["Content-Type"] = "application/x-www-form-urlencoded"
      req.body = URI.encode_www_form(
        grant_type: "client_credentials",
        client_id: @client_id,
        client_secret: @client_secret
      )
    end
    JSON.parse(resp.body)["access_token"]
  end
end
```

## OAuth Callback Controller

Handle the OAuth callback from MCP server:

```ruby
# app/controllers/mcp/oauth_controller.rb
module MCP
  class OauthController < ApplicationController
    skip_before_action :verify_authenticity_token, only: [:callback]

    def callback
      code = params[:code]
      state = params[:state]

      # Find the pending OAuth session by state
      tool = find_tool_by_oauth_state(state)
      if tool.nil?
        flash[:alert] = "OAuth session not found"
        return redirect_to root_path
      end

      # Reconstruct MCP client with pending OAuth state
      client = build_mcp_client_for_tool(tool)

      if client.exchange_code(code, state)
        # Store the access token
        tool.update_mcp_oauth_token(client.access_token)
        flash[:notice] = "MCP server connected successfully"
      else
        flash[:alert] = "Failed to exchange OAuth code"
      end

      redirect_to agent_tools_path
    end

    private

    def find_tool_by_oauth_state(state)
      # Look up tool configuration by pending OAuth state
      AgentTool.find_by_oauth_state(state)
    end

    def build_mcp_client_for_tool(tool)
      config = tool.mcp_config
      MCPClient.new(
        mode: :remote,
        endpoint: config["endpoint"],
        pending_state: config["pending_oauth_state"],
        pending_code_verifier: config["pending_code_verifier"],
        client_id: config["client_id"],
        token_endpoint: config["token_endpoint"]
      )
    end
  end
end
```

## Integration with MCPClient

The OAuth flow integrates with MCPClient's error handling:

```ruby
# In MCPClient#post (error handling section)
def post(body, accept: "application/json")
  @transport.post(body, accept: accept)
rescue Faraday::UnauthorizedError, RpcAuthorizationError => e
  # Reset invalid token
  @oauth_flow.reset_access_token!
  @access_token = nil
  @session_obj.access_token = nil

  # 1. Try client credentials (machine-to-machine)
  if @oauth_flow.authenticate_with_client_credentials!
    @access_token = @oauth_flow.access_token
    @session_obj.access_token = @access_token
    @transport.access_token = @access_token if @transport.respond_to?(:access_token=)
    retry
  end

  # 2. Interactive PKCE - build authorization URL
  url = @oauth_flow.authorization_url_from_error(e)
  raise AuthorizationRequiredError.new(url) if url
  raise
end
```

## Storing OAuth State

Store OAuth state in tool configuration for callback handling:

```ruby
# AgentTool model helper methods
class AgentTool < ApplicationRecord
  def pending_oauth_state
    mcp_config&.dig("pending_oauth_state")
  end

  def pending_code_verifier
    mcp_config&.dig("pending_code_verifier")
  end

  def save_oauth_pending_state(state:, verifier:, client_id:, token_endpoint:)
    update(mcp_config: mcp_config.merge(
      "pending_oauth_state" => state,
      "pending_code_verifier" => verifier,
      "client_id" => client_id,
      "token_endpoint" => token_endpoint
    ))
  end

  def update_mcp_oauth_token(token)
    update(mcp_config: mcp_config.merge(
      "access_token" => token,
      "pending_oauth_state" => nil,
      "pending_code_verifier" => nil
    ))
  end

  def self.find_by_oauth_state(state)
    where("mcp_config->>'pending_oauth_state' = ?", state).first
  end
end
```

## Routes

```ruby
# config/routes.rb
namespace "mcp" do
  get "oauth/callback", to: "oauth#callback", as: :oauth_callback
end
```

## Usage Flow

### Machine-to-Machine (Automatic)

```ruby
# Client has credentials - will auto-authenticate
client = MCPClient.new(
  mode: :remote,
  endpoint: "https://mcp.example.com/v1",
  client_id: "abc123",
  client_secret: "secret",
  token_endpoint: "https://mcp.example.com/oauth/token"
)

# First call triggers client_credentials flow automatically
client.list_tools  # Works without manual auth
```

### Interactive PKCE (User Redirect)

```ruby
begin
  client = MCPClient.new(
    mode: :remote,
    endpoint: "https://mcp.example.com/v1"
  )
  client.list_tools
rescue MCPClient::AuthorizationRequiredError => e
  # Save OAuth state to database
  agent_tool.save_oauth_pending_state(
    state: client.pending_state,
    verifier: client.pending_code_verifier,
    client_id: client.client_id,
    token_endpoint: client.token_endpoint
  )

  # Redirect user to authorize
  redirect_to e.url
end

# After callback:
# OAuth controller handles code exchange and stores token
```

## Testing

```ruby
RSpec.describe MCPClient::OAuthFlow do
  describe "#authenticate_with_client_credentials!" do
    it "fetches token with client credentials" do
      stub_request(:post, "https://auth.example.com/token")
        .with(body: hash_including(grant_type: "client_credentials"))
        .to_return(body: { access_token: "abc123" }.to_json)

      flow = described_class.new(
        token_endpoint: "https://auth.example.com/token",
        client_id: "client",
        client_secret: "secret"
      )

      expect(flow.authenticate_with_client_credentials!).to be true
      expect(flow.access_token).to eq("abc123")
    end
  end

  describe "#build_authorization_url" do
    it "generates PKCE challenge" do
      flow = described_class.new(
        authorization_endpoint: "https://auth.example.com/authorize",
        client_id: "client"
      )

      url = flow.send(:build_authorization_url)

      expect(url).to include("code_challenge=")
      expect(url).to include("code_challenge_method=S256")
      expect(url).to include("state=")
    end
  end

  describe "#exchange_code" do
    it "exchanges code for token" do
      stub_request(:post, "https://auth.example.com/token")
        .to_return(body: { access_token: "token123" }.to_json)

      flow = described_class.new(
        token_endpoint: "https://auth.example.com/token",
        client_id: "client",
        pending_code_verifier: "verifier123"
      )

      expect(flow.exchange_code("code", "state")).to be true
      expect(flow.access_token).to eq("token123")
    end
  end
end
```

## Security Considerations

1. **PKCE Required**: Always use S256 code challenge method
2. **State Validation**: Verify state matches before exchange
3. **Token Storage**: Store tokens encrypted in database
4. **Token Expiry**: Handle token refresh or re-authentication
5. **Redirect URI**: Must match registered URI exactly

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "OAuth session not found" | State mismatch | Check state stored in DB matches callback |
| "Failed to exchange" | Invalid verifier | Ensure verifier persisted correctly |
| Discovery fails | No `.well-known` | Server doesn't support discovery |
| Client registration fails | Endpoint unavailable | Manual client registration required |

## Next Steps

- [Docker Supervisor](04-docker-supervisor.md) - Container management for subprocess MCP
- [Server Implementation](05-server-implementation.md) - Build MCP servers
