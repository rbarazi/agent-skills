# MCP Transport Layer

## Purpose
Abstract the communication mechanism between MCP client and server. Supports HTTP, SSE (Server-Sent Events), and subprocess (Docker/stdio) transports with automatic fallback.

## Transport Interface

All transports implement a common interface:

```ruby
# app/services/mcp_client/transport/json_rpc_transport.rb
module MCPClient::Transport
  class JsonRpcTransport
    # Perform JSON-RPC request. Returns Hash with symbolized keys.
    def post(body, accept: "application/json")
      raise NotImplementedError
    end

    # Gracefully stop/cleanup resources
    def stop; end

    # Check if transport is ready for communication
    def ready?
      raise NotImplementedError
    end

    # Session ID from server (nil for transports without sessions)
    def session_id
      nil
    end
  end
end
```

## HTTP Transport

Direct HTTP POST for JSON-RPC communication. Simplest and most compatible.

```ruby
# app/services/mcp_client/transport/remote_http_transport.rb
module MCPClient::Transport
  class RemoteHttpTransport < JsonRpcTransport
    PROTOCOL_VERSION = "2025-03-26"

    attr_accessor :access_token
    attr_reader :endpoint, :session_id

    def initialize(endpoint:, access_token: nil, faraday: nil, session: nil)
      @endpoint = endpoint
      @access_token = access_token
      @session = session
      @session_id = session&.id

      @conn = faraday || Faraday.new(
        url: endpoint,
        request: { open_timeout: 5, read_timeout: 120 }
      ) do |f|
        f.request :url_encoded
        f.response :raise_error
        f.adapter :net_http
      end
    end

    def post(body, accept: "application/json")
      resp = @conn.post do |req|
        if @session
          req.headers.merge!(@session.headers_for(accept: accept))
          req.headers["Authorization"] = "Bearer #{@access_token}" if @access_token
        else
          req.headers["Content-Type"] = "application/json"
          req.headers["Accept"] = accept
          req.headers["Mcp-Session-Id"] = @session_id if @session_id
          req.headers["Mcp-Protocol-Version"] = PROTOCOL_VERSION
          req.headers["Authorization"] = "Bearer #{@access_token}" if @access_token
        end
        req.body = JSON.generate(body)
      end

      # Capture session ID from response
      @session_id = resp.headers["Mcp-Session-Id"]
      @session.id = @session_id if @session

      # Handle SSE response (some servers respond with SSE even to HTTP)
      if resp.headers["Content-Type"]&.include?("text/event-stream")
        parse_sse(resp.body)
      else
        data = JSON.parse(resp.body).deep_symbolize_keys
        check_for_auth_error!(data)
        data
      end
    end

    def ready?
      @conn.present?
    end

    private

    def parse_sse(body)
      events = body.split(/\n\n+/).map do |chunk|
        next unless chunk.include?("data:")
        data_lines = chunk.lines.select { |l| l.start_with?("data:") }
        data = data_lines.map { |l| l.sub(/^data:\s*/, "").strip }.join("\n")
        JSON.parse(data).deep_symbolize_keys rescue { data: data }
      end.compact
      events.last || {}
    end

    def check_for_auth_error!(data)
      error = data[:error]
      if error && error[:message]&.match?(/unauthorized|token/i)
        raise MCPClient::RpcAuthorizationError, error[:message]
      end
    end
  end
end
```

## SSE Transport

Long-lived streaming connection for servers requiring SSE. Uses background listener thread.

```ruby
# app/services/mcp_client/transport/remote_sse_transport.rb
module MCPClient::Transport
  class RemoteSSETransport < JsonRpcTransport
    PROTOCOL_VERSION = "2025-03-26"

    attr_accessor :access_token
    attr_reader :endpoint, :session_id

    def initialize(endpoint:, access_token: nil, faraday: nil, session: nil)
      @endpoint = endpoint
      @access_token = access_token
      @session = session

      @conn = faraday || Faraday.new(
        url: endpoint,
        request: { open_timeout: 5, read_timeout: 120 }
      ) do |f|
        f.request :url_encoded
        f.response :raise_error
        f.adapter :net_http
      end

      # Start background listener
      @listener = MCPClient::SSEListener.new(
        conn: @conn,
        endpoint: endpoint,
        access_token: access_token,
        protocol_version: PROTOCOL_VERSION,
        initial_session: session&.id,
        session: session
      )
      @listener.start!
      @listener.wait_for_post_path(timeout: 10)
      @session_id = @listener.session_id
      @session.id = @session_id if @session
    end

    def post(body, accept: "text/event-stream")
      request_id = body[:id]
      path = @listener.post_path

      @conn.post(path) do |req|
        req.headers["Content-Type"] = "application/json"
        req.headers["Accept"] = accept
        req.headers["Mcp-Protocol-Version"] = PROTOCOL_VERSION
        req.headers["Mcp-Session-Id"] = @session_id if @session_id
        req.headers["Authorization"] = "Bearer #{@access_token}" if @access_token
        req.body = JSON.generate(body)
      end

      # Wait for response via SSE stream
      @listener.wait_for_response(request_id)
    end

    def stop
      @listener.stop!
    end

    def ready?
      @listener.running?
    end
  end
end
```

## SSE Listener

Background thread that maintains SSE connection and buffers responses.

```ruby
# app/services/mcp_client/sse_listener.rb
class MCPClient::SSEListener
  attr_reader :post_path, :session_id

  def initialize(conn:, endpoint:, access_token: nil, protocol_version:,
                 initial_session: nil, session: nil)
    @conn = conn
    @endpoint = endpoint
    @access_token = access_token
    @protocol_version = protocol_version
    @session_object = session
    @session_id = initial_session

    @responses = {}.extend(MonitorMixin)
    @listener_thread = nil
  end

  def start!
    return if @listener_thread&.alive?
    @listener_thread = Thread.new { listen }
  end

  def stop!
    @listener_thread&.kill
  end

  def running?
    !!(@listener_thread&.alive?)
  end

  # Block until server sends endpoint event with POST path
  def wait_for_post_path(timeout: 10)
    deadline = Time.now + timeout
    loop do
      return @post_path if @post_path
      raise "Timed out waiting for SSE endpoint" if Time.now > deadline
      sleep 0.05
    end
  end

  # Block until response with matching ID arrives
  def wait_for_response(request_id, timeout: 120)
    deadline = Time.now + timeout
    loop do
      resp = @responses.synchronize { @responses.delete(request_id) }
      return resp if resp
      raise "Timeout waiting for response id=#{request_id}" if Time.now > deadline
      sleep 0.05
    end
  end

  private

  def listen
    buffer = String.new
    @conn.get(@endpoint) do |req|
      req.headers["Accept"] = "text/event-stream"
      req.headers["Mcp-Protocol-Version"] = @protocol_version
      req.headers["Authorization"] = "Bearer #{@access_token}" if @access_token
      req.headers["Mcp-Session-Id"] = @session_id if @session_id

      req.options.on_data = proc do |chunk, _|
        buffer << chunk
        process_buffer(buffer)
      end
    end
  rescue => e
    Rails.logger.error "SSEListener error: #{e.class}: #{e.message}"
  end

  def process_buffer(buffer)
    loop do
      event_chunk, buffer = MCPClient::SSEParser.extract_next_event_from_buffer(buffer)
      break unless event_chunk

      parsed = MCPClient::SSEParser.parse_event(event_chunk)
      next if parsed.empty?

      case parsed[:event]
      when "endpoint"
        @responses.synchronize { @post_path = parsed[:data] }
      else
        handle_json_rpc_event(parsed[:data])
      end
    end
  end

  def handle_json_rpc_event(data)
    return unless data.is_a?(Hash) && data[:jsonrpc] == "2.0" && data.key?(:id)
    @responses.synchronize { @responses[data[:id]] = data }
  end
end
```

## SSE Parser

Lightweight parser for SSE event streams.

```ruby
# app/services/mcp_client/sse_parser.rb
class MCPClient::SSEParser
  class << self
    # Extract next complete event from buffer
    def extract_next_event_from_buffer(buffer)
      if (idx = buffer.index("\n\n"))
        event_chunk = buffer[0..idx]
        remaining = buffer[(idx + 2)..-1]
        [event_chunk, remaining]
      else
        [nil, buffer]
      end
    end

    # Parse SSE event chunk into Hash
    def parse_event(chunk)
      return {} if chunk.nil? || chunk.empty?

      event_name = chunk.lines
        .find { |l| l.start_with?("event:") }
        &.split(":", 2)&.last&.strip

      data_lines = chunk.lines.select { |l| l.start_with?("data:") }
      return {} if data_lines.empty?

      data_string = data_lines
        .map { |l| l.sub(/^data:\s*/, "").strip }
        .join("\n")

      parsed_data = begin
        JSON.parse(data_string).deep_symbolize_keys
      rescue JSON::ParserError
        data_string
      end

      { event: event_name, data: parsed_data }
    end
  end
end
```

## Subprocess Transport

Communicates with MCP server running as Docker subprocess via stdin/stdout.

```ruby
# app/services/mcp_client/transport/subprocess_transport.rb
module MCPClient::Transport
  class SubprocessTransport < JsonRpcTransport
    attr_reader :supervisor

    def initialize(supervisor:)
      @supervisor = supervisor
    end

    def post(body, accept: "application/json")
      # Lazily start to avoid Docker dependency during tests
      supervisor.start unless supervisor.ready?

      response = @supervisor.json_rpc_request(body, timeout: 10)
      response.deep_symbolize_keys
    rescue MCPDockerProcessSupervisor::ProcessNotReadyError => e
      raise StandardError, "MCP server not ready: #{e.message}"
    rescue MCPDockerProcessSupervisor::ProcessFailedError => e
      raise StandardError, "MCP server failed: #{e.message}"
    end

    def stop
      @supervisor.stop if @supervisor.running?
    end

    def ready?
      @supervisor.ready?
    end

    def session_id; end
  end
end
```

## Strategy Selector

Factory that builds appropriate transport based on strategy.

```ruby
# app/services/mcp_client/transport/strategy_selector.rb
module MCPClient::Transport
  class StrategySelector
    STRATEGIES = %w[http-only sse-only http-first sse-first].freeze

    def self.build(endpoint:, access_token: nil, strategy: "http-first", session: nil)
      case strategy.to_s
      when "http-only"
        RemoteHttpTransport.new(
          endpoint: endpoint, access_token: access_token, session: session
        )
      when "sse-only"
        RemoteSSETransport.new(
          endpoint: endpoint, access_token: access_token, session: session
        )
      when "http-first"
        CompositeFallbackTransport.new(
          primary: RemoteHttpTransport.new(
            endpoint: endpoint, access_token: access_token, session: session
          ),
          secondary: -> {
            RemoteSSETransport.new(
              endpoint: endpoint, access_token: access_token, session: session
            )
          }
        )
      when "sse-first"
        CompositeFallbackTransport.new(
          primary: RemoteSSETransport.new(
            endpoint: endpoint, access_token: access_token, session: session
          ),
          secondary: -> {
            RemoteHttpTransport.new(
              endpoint: endpoint, access_token: access_token, session: session
            )
          }
        )
      else
        raise ArgumentError, "Unknown strategy: #{strategy}"
      end
    end
  end
end
```

## Composite Fallback Transport

Tries primary transport, falls back to secondary on specific errors.

```ruby
# app/services/mcp_client/transport/composite_fallback_transport.rb
module MCPClient::Transport
  class CompositeFallbackTransport < JsonRpcTransport
    FALLBACK_STATUSES = [404, 405].freeze

    def initialize(primary:, secondary:)
      @primary = primary
      @secondary = secondary
    end

    def post(body, accept: "application/json")
      @primary.post(body, accept: accept)
    rescue Faraday::ClientError => e
      status = e.response[:status] rescue nil
      raise unless FALLBACK_STATUSES.include?(status)

      # Lazily instantiate secondary if it's a Proc
      @secondary = @secondary.call if @secondary.is_a?(Proc)
      @secondary.post(body, accept: accept)
    end

    def stop
      @primary.stop if @primary.respond_to?(:stop)
      concrete = @secondary.is_a?(Proc) ? nil : @secondary
      concrete&.stop if concrete&.respond_to?(:stop)
    end

    def ready?
      @primary.ready? || @secondary.ready?
    end

    def session_id
      @primary.session_id || @secondary.session_id
    end
  end
end
```

## Usage Examples

### HTTP-Only (Simplest)

```ruby
transport = MCPClient::Transport::StrategySelector.build(
  endpoint: "https://mcp.example.com/v1",
  strategy: "http-only"
)

client = MCPClient.new(
  mode: :remote,
  endpoint: "https://mcp.example.com/v1",
  transport: transport
)
```

### With Fallback (Recommended)

```ruby
# Try HTTP first, fall back to SSE if server returns 404/405
client = MCPClient.new(
  mode: :remote,
  endpoint: "https://mcp.example.com/v1",
  transport_strategy: "http-first"
)
```

### Subprocess Mode

```ruby
supervisor = MCPDockerProcessSupervisor.new(
  tool: tool,
  docker_args: ['run', '--rm', '-i', 'my-mcp-server:latest']
)

client = MCPClient.new(
  mode: :subprocess,
  supervisor: supervisor
)
```

## Testing Strategy

```ruby
RSpec.describe MCPClient::Transport::RemoteHttpTransport do
  let(:endpoint) { "https://mcp.test/v1" }
  let(:transport) { described_class.new(endpoint: endpoint) }

  describe "#post" do
    it "sends JSON-RPC request" do
      stub_request(:post, endpoint)
        .with(body: hash_including(jsonrpc: "2.0"))
        .to_return(
          status: 200,
          body: { jsonrpc: "2.0", id: 1, result: {} }.to_json,
          headers: { "Content-Type" => "application/json" }
        )

      result = transport.post({ jsonrpc: "2.0", id: 1, method: "ping" })
      expect(result[:result]).to eq({})
    end

    it "captures session ID from response headers" do
      stub_request(:post, endpoint)
        .to_return(
          status: 200,
          body: { jsonrpc: "2.0", id: 1, result: {} }.to_json,
          headers: {
            "Content-Type" => "application/json",
            "Mcp-Session-Id" => "abc123"
          }
        )

      transport.post({ jsonrpc: "2.0", id: 1, method: "ping" })
      expect(transport.session_id).to eq("abc123")
    end
  end
end

RSpec.describe MCPClient::Transport::CompositeFallbackTransport do
  it "falls back on 404" do
    primary = instance_double(MCPClient::Transport::RemoteHttpTransport)
    secondary = instance_double(MCPClient::Transport::RemoteSSETransport)

    allow(primary).to receive(:post)
      .and_raise(Faraday::ClientError.new(nil, { status: 404 }))
    allow(secondary).to receive(:post)
      .and_return({ jsonrpc: "2.0", id: 1, result: {} })

    transport = described_class.new(primary: primary, secondary: -> { secondary })
    result = transport.post({ jsonrpc: "2.0", id: 1, method: "ping" })

    expect(result[:result]).to eq({})
  end
end
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| SSE timeout | Server slow to respond | Increase `read_timeout` in Faraday config |
| Thread safety | Concurrent access to responses | Use MonitorMixin for synchronization |
| Memory leak | SSE listener thread not stopped | Always call `transport.stop` on cleanup |
| 405 errors | Server requires SSE | Use `sse-first` or `sse-only` strategy |

## Next Steps

- [OAuth Flow](03-oauth-flow.md) - Add authentication to transports
- [Docker Supervisor](04-docker-supervisor.md) - Subprocess transport backend
