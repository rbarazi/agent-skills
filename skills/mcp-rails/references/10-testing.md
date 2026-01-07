# MCP Testing

## Purpose
Comprehensive test strategies for MCP client, server, and subprocess components.

## Client Testing

### Session Persistence

```ruby
RSpec.describe MCPClient do
  describe "session management" do
    let(:client) { described_class.new(mode: :remote, endpoint: "http://mcp.example.com") }

    it "persists session ID across requests" do
      stub_request(:post, "http://mcp.example.com/")
        .with(body: hash_including(method: "initialize"))
        .to_return(
          status: 200,
          headers: { "Mcp-Session-Id" => "session-123" },
          body: { jsonrpc: "2.0", id: 1, result: {} }.to_json
        )

      stub_request(:post, "http://mcp.example.com/")
        .with(
          body: hash_including(method: "tools/list"),
          headers: { "Mcp-Session-Id" => "session-123" }
        )
        .to_return(body: { jsonrpc: "2.0", id: 2, result: { tools: [] } }.to_json)

      client.initialize_session!
      client.list_tools

      expect(WebMock).to have_requested(:post, "http://mcp.example.com/")
        .with(headers: { "Mcp-Session-Id" => "session-123" })
        .once
    end
  end
end
```

### Transport Testing

```ruby
RSpec.describe MCPClient::Transport do
  describe "HTTP transport" do
    let(:transport) { MCPClient::Transport::RemoteHttpTransport.new(endpoint: "http://mcp.example.com") }

    it "sends JSON-RPC request" do
      stub_request(:post, "http://mcp.example.com/")
        .to_return(body: { jsonrpc: "2.0", id: 1, result: {} }.to_json)

      response = transport.post({ jsonrpc: "2.0", id: 1, method: "ping" })

      expect(response[:result]).to eq({})
    end
  end

  describe "SSE transport" do
    let(:transport) { MCPClient::Transport::RemoteSseTransport.new(endpoint: "http://mcp.example.com") }

    it "handles SSE events" do
      stub_request(:post, "http://mcp.example.com/sse")
        .to_return(
          headers: { "Content-Type" => "text/event-stream" },
          body: "data: #{{ jsonrpc: '2.0', id: 1, result: {} }.to_json}\n\n"
        )

      response = transport.post({ jsonrpc: "2.0", id: 1, method: "tools/list" })

      expect(response[:result]).to eq({})
    end
  end

  describe "transport fallback" do
    let(:transport) do
      MCPClient::Transport::CompositeFallbackTransport.new(
        endpoint: "http://mcp.example.com",
        strategies: [:http, :sse]
      )
    end

    it "falls back to SSE when HTTP returns 404" do
      stub_request(:post, "http://mcp.example.com/")
        .to_return(status: 404)

      stub_request(:post, "http://mcp.example.com/sse")
        .to_return(body: { jsonrpc: "2.0", id: 1, result: {} }.to_json)

      response = transport.post({ jsonrpc: "2.0", id: 1, method: "tools/list" })

      expect(response[:result]).to eq({})
    end
  end
end
```

### OAuth Challenge Testing

```ruby
RSpec.describe MCPClient do
  describe "OAuth flow" do
    let(:client) { described_class.new(mode: :remote, endpoint: "http://mcp.example.com") }

    it "raises AuthorizationRequiredError on 401" do
      stub_request(:post, "http://mcp.example.com/")
        .to_return(
          status: 401,
          headers: {
            "WWW-Authenticate" => 'Bearer realm="mcp", resource_metadata="http://mcp.example.com/.well-known/oauth-protected-resource"'
          }
        )

      expect { client.initialize_session! }
        .to raise_error(MCPClient::AuthorizationRequiredError) do |error|
          expect(error.metadata_url).to eq("http://mcp.example.com/.well-known/oauth-protected-resource")
        end
    end

    it "completes PKCE flow" do
      oauth_flow = MCPClient::OAuthFlow.new(
        metadata_url: "http://mcp.example.com/.well-known/oauth-protected-resource",
        redirect_uri: "http://localhost:3000/oauth/callback"
      )

      # Mock discovery
      stub_request(:get, "http://mcp.example.com/.well-known/oauth-protected-resource")
        .to_return(body: { authorization_endpoint: "http://auth.example.com/authorize" }.to_json)

      auth_url = oauth_flow.start_authorization
      expect(auth_url).to include("code_challenge=")
      expect(auth_url).to include("code_challenge_method=S256")
    end
  end
end
```

## Server Testing

### JSON-RPC Validation

```ruby
RSpec.describe MCP::ServersController, type: :request do
  describe "POST /mcp/:server_name" do
    it "returns valid JSON-RPC success response" do
      post "/mcp/test_server", params: {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: { protocolVersion: "2025-03-26" }
      }.to_json, headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      json = JSON.parse(response.body)
      expect(json["jsonrpc"]).to eq("2.0")
      expect(json["id"]).to eq(1)
      expect(json).to have_key("result")
    end

    it "returns valid JSON-RPC error response" do
      post "/mcp/test_server", params: {
        jsonrpc: "2.0",
        id: 1,
        method: "unknown_method"
      }.to_json, headers: { "Content-Type" => "application/json" }

      json = JSON.parse(response.body)
      expect(json["error"]).to be_present
      expect(json["error"]["code"]).to eq(-32601) # Method not found
    end
  end
end
```

### Scope Enforcement

```ruby
RSpec.describe MCP::ServersController, type: :request do
  describe "scope enforcement" do
    let(:token) { create(:oauth_access_token, scopes: ["mcp:read"]) }

    it "allows access with correct scope" do
      post "/mcp/test_server", params: {
        jsonrpc: "2.0",
        id: 1,
        method: "tools/list"
      }.to_json, headers: {
        "Content-Type" => "application/json",
        "Authorization" => "Bearer #{token.token}"
      }

      expect(response).to have_http_status(:ok)
    end

    it "denies access with insufficient scope" do
      post "/mcp/test_server", params: {
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: { name: "write_file", arguments: {} }
      }.to_json, headers: {
        "Content-Type" => "application/json",
        "Authorization" => "Bearer #{token.token}"  # Only has read scope
      }

      json = JSON.parse(response.body)
      expect(json["error"]["code"]).to eq(-32600)
      expect(json["error"]["message"]).to include("scope")
    end
  end
end
```

### Session Testing

```ruby
RSpec.describe MCP::ServersController, type: :request do
  describe "session handling" do
    it "creates session on initialize" do
      post "/mcp/test_server", params: {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: { protocolVersion: "2025-03-26" }
      }.to_json, headers: { "Content-Type" => "application/json" }

      expect(response.headers["Mcp-Session-Id"]).to be_present
    end

    it "extends session on activity" do
      session = create(:mcp_client_session, expires_at: 1.hour.from_now)

      travel_to 30.minutes.from_now do
        post "/mcp/test_server", params: {
          jsonrpc: "2.0",
          id: 1,
          method: "ping"
        }.to_json, headers: {
          "Content-Type" => "application/json",
          "Mcp-Session-Id" => session.session_id
        }

        session.reload
        expect(session.expires_at).to be > 30.minutes.from_now
      end
    end
  end
end
```

## Subprocess Testing

### Supervisor Lifecycle

```ruby
RSpec.describe MCPDockerProcessSupervisor do
  let(:supervisor) do
    described_class.new(
      command: "docker",
      args: ["run", "--rm", "-i", "mcp-test:latest"],
      startup_timeout: 5
    )
  end

  describe "#start" do
    it "starts container and waits for ready" do
      expect(supervisor.start).to be true
      expect(supervisor.ready?).to be true
      expect(supervisor.running?).to be true
    ensure
      supervisor.stop
    end

    it "times out if container never becomes ready" do
      slow_supervisor = described_class.new(
        command: "sleep",
        args: ["infinity"],
        startup_timeout: 1
      )

      expect { slow_supervisor.start }
        .to raise_error(MCPDockerProcessSupervisor::StartupTimeoutError)
    end
  end

  describe "#stop" do
    it "gracefully stops container" do
      supervisor.start
      supervisor.stop

      expect(supervisor.running?).to be false
    end
  end

  describe "restart on failure" do
    it "restarts crashed container" do
      supervisor.start
      Process.kill("KILL", supervisor.pid)

      sleep 0.5  # Allow restart
      expect(supervisor.running?).to be true
    end
  end
end
```

### Multi-Worker Coordination

```ruby
RSpec.describe MCPDockerProcessSupervisor do
  describe "multi-worker coordination" do
    let(:tool) { create(:tool) }

    it "only one worker owns the supervisor" do
      workers = 3.times.map do
        Thread.new do
          supervisor = described_class.new(
            tool_id: tool.id,
            command: "docker",
            args: ["run", "--rm", "-i", "mcp-test:latest"]
          )
          supervisor.acquire_lock
        end
      end

      results = workers.map(&:value)

      expect(results.count(true)).to eq(1)
      expect(results.count(false)).to eq(2)
    end

    it "releases lock on stop" do
      supervisor = described_class.new(tool_id: tool.id, ...)
      supervisor.acquire_lock
      supervisor.stop

      instance = MCPServerInstance.find_by(tool_id: tool.id)
      expect(instance).to be_nil
    end

    it "cleans up stale locks" do
      create(:mcp_server_instance,
        tool_id: tool.id,
        last_health_check_at: 10.minutes.ago
      )

      MCPServerInstance.cleanup_stale!(timeout: 5.minutes)

      expect(MCPServerInstance.find_by(tool_id: tool.id)).to be_nil
    end
  end
end
```

## Integration Testing

### End-to-End Flow

```ruby
RSpec.describe "MCP Integration", type: :request do
  let(:agent) { create(:agent) }
  let(:tool) { create(:tool, mcp_server_name: "test_server") }

  before do
    agent.tools << tool
  end

  it "completes full tool call cycle" do
    # 1. Initialize session
    post "/mcp/test_server", params: {
      jsonrpc: "2.0", id: 1, method: "initialize",
      params: { protocolVersion: "2025-03-26" }
    }.to_json, headers: json_headers

    session_id = response.headers["Mcp-Session-Id"]

    # 2. List tools
    post "/mcp/test_server", params: {
      jsonrpc: "2.0", id: 2, method: "tools/list"
    }.to_json, headers: json_headers.merge("Mcp-Session-Id" => session_id)

    tools = JSON.parse(response.body).dig("result", "tools")
    expect(tools).to be_present

    # 3. Call tool
    post "/mcp/test_server", params: {
      jsonrpc: "2.0", id: 3, method: "tools/call",
      params: { name: tools.first["name"], arguments: {} }
    }.to_json, headers: json_headers.merge("Mcp-Session-Id" => session_id)

    result = JSON.parse(response.body)["result"]
    expect(result).to be_present
  end

  def json_headers
    { "Content-Type" => "application/json" }
  end
end
```

## Test Helpers

```ruby
# spec/support/mcp_helpers.rb
module MCPHelpers
  def stub_mcp_server(endpoint, responses = {})
    responses.each do |method, response|
      stub_request(:post, endpoint)
        .with(body: hash_including(method: method))
        .to_return(body: { jsonrpc: "2.0", id: 1, result: response }.to_json)
    end
  end

  def mcp_request(method, params = {})
    { jsonrpc: "2.0", id: 1, method: method, params: params }
  end
end

RSpec.configure do |config|
  config.include MCPHelpers, type: :request
end
```

## Best Practices

1. **Isolate transport tests**: Test each transport independently
2. **Mock external MCP servers**: Use WebMock for remote servers
3. **Test fallback paths**: Verify fallback behavior works correctly
4. **Use factories for sessions**: Create realistic session fixtures
5. **Test concurrency**: Verify multi-worker behavior under contention
6. **Clean up containers**: Ensure Docker containers are stopped after tests
