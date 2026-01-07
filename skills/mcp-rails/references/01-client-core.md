# MCP Client Core Implementation

## Purpose
Communicate with MCP servers using JSON-RPC 2.0 over HTTP/SSE.

## Protocol Constants

```ruby
JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2025-03-26"  # Current MCP spec version
```

## Core Client Structure

```ruby
# app/services/mcp_client.rb
class MCPClient
  JSONRPC_VERSION = "2.0"
  PROTOCOL_VERSION = "2025-03-26"

  class AuthorizationRequiredError < StandardError
    attr_reader :url
    def initialize(url)
      @url = url
      super("Authorization required")
    end
  end

  class RpcAuthorizationError < StandardError; end

  TRANSPORT_STRATEGIES = %w[http-first sse-first http-only sse-only].freeze

  attr_reader :mode, :endpoint, :supervisor
  attr_accessor :access_token

  def initialize(mode: :remote,
                 endpoint: nil,
                 supervisor: nil,
                 access_token: nil,
                 transport_strategy: "http-first",
                 transport: nil,
                 # OAuth parameters for flow reconstruction
                 pending_state: nil,
                 pending_code_verifier: nil,
                 client_id: nil,
                 client_secret: nil,
                 token_endpoint: nil)
    @mode = mode.to_sym
    @access_token = access_token
    @transport_strategy = transport_strategy.to_s
    @next_id = 1
    @session_obj = MCPClient::Session.new(access_token: @access_token)
    @session = nil  # Session ID from server

    validate_mode_requirements!(endpoint, supervisor)
    @endpoint = endpoint
    @supervisor = supervisor

    # Initialize OAuth flow if credentials provided
    @oauth_flow = build_oauth_flow(
      endpoint: endpoint,
      client_id: client_id,
      client_secret: client_secret,
      token_endpoint: token_endpoint,
      pending_state: pending_state,
      pending_code_verifier: pending_code_verifier
    )

    @transport = transport || build_default_transport
  end

  # Initialize MCP session - MUST be called before other operations
  def initialize_session!
    body = rpc_request(
      "initialize",
      protocolVersion: PROTOCOL_VERSION,
      clientInfo: { name: "my-mcp-client", version: "0.1" },
      capabilities: {}
    )

    resp = post(body, accept: "application/json, text/event-stream")
    @session = @transport.session_id
    @session_obj.id = @session
    Rails.logger.info "MCP session established: #{@session}"
    resp
  end

  def ping
    body = rpc_request("ping")
    resp = post(body, accept: "application/json")
    resp[:result]
  end

  def list_tools
    ensure_session!
    body = rpc_request("tools/list")
    result = post(body)[:result]
    result
  end

  def call_tool(name, arguments = {})
    ensure_session!
    body = rpc_request("tools/call", name: name, arguments: arguments)
    result = post(body)[:result]
    result
  end

  def ready?
    @transport.ready?
  end

  def stop
    @transport.stop
  end

  private

  def validate_mode_requirements!(endpoint, supervisor)
    case @mode
    when :remote
      raise ArgumentError, "endpoint required for remote mode" unless endpoint
    when :subprocess
      raise ArgumentError, "supervisor required for subprocess mode" unless supervisor
    else
      raise ArgumentError, "mode must be :remote or :subprocess"
    end
  end

  def build_default_transport
    case @mode
    when :remote
      MCPClient::Transport::StrategySelector.build(
        endpoint: @endpoint,
        access_token: @access_token,
        strategy: @transport_strategy,
        session: @session_obj
      )
    when :subprocess
      MCPClient::Transport::SubprocessTransport.new(supervisor: @supervisor)
    end
  end

  def build_oauth_flow(endpoint:, client_id:, client_secret:, token_endpoint:, pending_state:, pending_code_verifier:)
    return nil unless client_id || pending_state

    MCPClient::OAuthFlow.new(
      endpoint: endpoint,
      client_id: client_id,
      client_secret: client_secret,
      token_endpoint: token_endpoint,
      pending_state: pending_state,
      pending_code_verifier: pending_code_verifier
    )
  end

  def rpc_request(method, **params)
    {
      jsonrpc: JSONRPC_VERSION,
      id: @next_id,
      method: method,
      params: params
    }.tap { @next_id += 1 }
  end

  def post(body, accept: "application/json")
    raise "No transport configured" unless @transport
    @transport.post(body, accept: accept)
  rescue Faraday::UnauthorizedError, RpcAuthorizationError => e
    handle_auth_error(e)
  end

  def handle_auth_error(error)
    # Reset token on auth failure
    @access_token = nil
    @session_obj.access_token = nil

    # If OAuth flow configured, attempt to get new token
    if @oauth_flow&.authenticate_with_client_credentials!
      @access_token = @oauth_flow.access_token
      @session_obj.access_token = @access_token
      retry
    end

    # Build authorization URL for interactive flow
    url = @oauth_flow&.authorization_url_from_error(error)
    raise AuthorizationRequiredError.new(url) if url
    raise
  end

  def ensure_session!
    return if @session.present?
    initialize_session!
  end
end
```

## Session Object

```ruby
# app/services/mcp_client/session.rb
class MCPClient::Session
  attr_accessor :id, :access_token

  def initialize(id: nil, access_token: nil)
    @id = id
    @access_token = access_token
  end

  def headers_for(accept: "application/json")
    {
      "Content-Type" => "application/json",
      "Accept" => accept
    }.tap do |h|
      h["Mcp-Session-Id"] = @id if @id.present?
      h["Authorization"] = "Bearer #{@access_token}" if @access_token.present?
    end
  end
end
```

## Usage Example

```ruby
# Connect to remote MCP server
client = MCPClient.new(
  mode: :remote,
  endpoint: "https://mcp.example.com/v1",
  transport_strategy: "http-first"
)

# Initialize session (required before other calls)
client.initialize_session!

# List available tools
tools = client.list_tools
puts tools["tools"].map { |t| t["name"] }

# Call a tool
result = client.call_tool("get_weather", { location: "New York" })
puts result
```

## Testing Strategy

```ruby
RSpec.describe MCPClient do
  describe "#initialize_session!" do
    it "establishes session with server" do
      # Use VCR or WebMock for external servers
      VCR.use_cassette("mcp_initialize") do
        client = MCPClient.new(mode: :remote, endpoint: "https://mcp.test/")
        response = client.initialize_session!

        expect(response[:result]).to include("protocolVersion")
        expect(client.ready?).to be true
      end
    end
  end

  describe "#call_tool" do
    it "raises without session" do
      client = MCPClient.new(mode: :remote, endpoint: "https://mcp.test/")
      # Session is auto-initialized, but you can test error handling
    end
  end
end
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AuthorizationRequiredError` | Server requires OAuth | Redirect to `error.url` for user auth |
| `RpcAuthorizationError` | Token expired/invalid | Refresh token or re-authenticate |
| No session ID returned | Server doesn't support sessions | Some servers are stateless, handle gracefully |

## Next Steps

- [Transport Layer](02-transport-layer.md) - HTTP, SSE, subprocess transports
- [OAuth Flow](03-oauth-flow.md) - Add authentication support
