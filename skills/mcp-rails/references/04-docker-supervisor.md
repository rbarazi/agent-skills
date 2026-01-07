# MCP Docker Process Supervisor

## Purpose
Manage MCP servers running as Docker containers with process lifecycle management, automatic restarts, exponential backoff, and JSON-RPC communication over stdin/stdout.

## Core Features
- Process supervision with configurable restart behavior
- Exponential backoff on failures (2s, 4s, 8s, 16s, 32s max)
- Thread-safe stdout buffering for JSON-RPC responses
- Support for both stdio and HTTP transport modes
- Debug logging and process state inspection

## Implementation

```ruby
# app/services/mcp_docker_process_supervisor.rb
require "open3"
require "timeout"
require "json"
require "logger"

class MCPDockerProcessSupervisor
  class ProcessNotReadyError < StandardError; end
  class ProcessFailedError < StandardError; end

  attr_reader :pid, :status

  def initialize(
    command:,
    args:,
    env: {},
    log_path: nil,
    startup_timeout: 10,
    max_restarts: 5,
    logger: nil,
    transport_mode: "stdio",
    http_port: nil
  )
    raise ArgumentError, "Only 'docker' command is supported" unless command == "docker"

    @command = command
    @args = args
    @env = env.transform_keys(&:to_s)
    @log_path = log_path || Rails.root.join("log/mcp_docker_supervisor.log")
    @startup_timeout = startup_timeout
    @status = :stopped
    @process_ready = false
    @running = false
    @restart_enabled = true
    @restart_count = 0
    @max_restarts = max_restarts
    @pid = nil
    @stdin = @stdout = @stderr = @wait_thr = nil
    @supervisor_thread = nil
    @mutex = Mutex.new
    @stdout_buffer = ""
    @buffer_mutex = Mutex.new
    @buffer_cv = ConditionVariable.new
    @transport_mode = transport_mode.to_s
    @http_port = http_port

    FileUtils.mkdir_p(File.dirname(@log_path))

    @logger = logger || Logger.new(@log_path, 10, 1_048_576)
    @logger.formatter = proc do |severity, datetime, _progname, msg|
      "[#{datetime.strftime('%Y-%m-%d %H:%M:%S.%3N')}] #{msg}\n"
    end
  end

  # Start process supervision
  def start
    @mutex.synchronize do
      return self if @running
      @running = true
      @restart_enabled = true
      @restart_count = 0
    end

    log("[SUPERVISOR] Starting process supervision")
    @supervisor_thread = Thread.new { supervise }

    begin
      wait_for_ready
      log("[SUPERVISOR] Process started successfully")
    rescue => e
      log("[ERROR] Failed to start process: #{e.message}")
      stop
      raise
    end

    self
  end

  # Stop process supervision
  def stop
    log("[SUPERVISOR] Stopping process supervision")
    @mutex.synchronize do
      @running = false
      @restart_enabled = false
    end

    terminate_process
    @supervisor_thread&.join(5)
    log("[SUPERVISOR] Process supervision stopped")
  end

  # Manual restart (resets restart count)
  def restart
    log("[SUPERVISOR] Manual restart requested")
    @mutex.synchronize { @restart_count = 0 }
    terminate_process
    # Supervision thread will restart automatically
  end

  def running?
    @running && @process_ready && process_alive?
  end

  def ready?
    case @transport_mode
    when "http"
      @process_ready && process_alive? && http_endpoint_ready?
    else
      @process_ready && process_alive?
    end
  end

  def process_alive?
    return false unless @pid
    Process.kill(0, @pid)
    true
  rescue Errno::ESRCH
    false
  rescue Errno::EPERM
    true  # Process exists but no permission
  end

  # Send JSON-RPC request and get response
  def json_rpc_request(request_data, timeout: 10)
    ensure_ready!

    request_json = request_data.is_a?(String) ? request_data : request_data.to_json
    log("[JSON-RPC] Sending request: #{request_json[0..100]}...")

    case @transport_mode
    when "http"
      http_json_rpc_request(request_json, timeout: timeout)
    else
      stdio_json_rpc_request(request_data, request_json, timeout: timeout)
    end
  end

  # Debug helper
  def debug_info
    {
      running: @running,
      process_ready: @process_ready,
      status: @status,
      pid: @pid,
      process_alive: (@pid ? process_alive? : false),
      restart_count: @restart_count,
      log_path: @log_path.to_s
    }
  end

  # Get recent log entries
  def recent_logs(lines: 20)
    return [] unless File.exist?(@log_path)
    File.readlines(@log_path).last(lines).map(&:strip)
  rescue => e
    ["Error reading logs: #{e.message}"]
  end

  private

  # Main supervision loop
  def supervise
    while @running
      begin
        spawn_process
        wait_for_process_exit
      rescue => e
        log("[ERROR] Supervisor error: #{e.message}")
        mark_process_failed
      end

      break unless should_restart?

      backoff_time = calculate_backoff
      log("[SUPERVISOR] Restarting in #{backoff_time}s (attempt #{@restart_count + 1}/#{@max_restarts})")
      sleep backoff_time
    end

    log("[SUPERVISOR] Supervision loop ended")
  end

  def spawn_process
    @mutex.synchronize { @process_ready = false }
    @status = :starting

    log("[SPAWN] Running #{@command} #{@args.join(' ')}")

    @stdin, @stdout, @stderr, @wait_thr = Open3.popen3(@env, @command, *@args)
    @pid = @wait_thr.pid
    @status = :running

    log("[PID] Started process with PID #{@pid}")

    sleep 0.1  # Give process time to initialize

    unless process_alive?
      @status = :failed
      raise ProcessFailedError, "Process exited immediately after spawn"
    end

    start_output_streaming
    @mutex.synchronize { @process_ready = true }
    log("[READY] Process is ready for communication")
  rescue Errno::ENOENT => e
    log("[ERROR] Command not found: #{e.message}")
    @status = :failed
    raise ProcessFailedError, "Docker command not found: #{e.message}"
  end

  def start_output_streaming
    @stdout_thread = stream_output(@stdout, "STDOUT")
    @stderr_thread = stream_output(@stderr, "STDERR")
  end

  def stream_output(io, label)
    Thread.new do
      io.each_line do |line|
        log("[#{label}] #{line.strip}")
        if label == "STDOUT"
          @buffer_mutex.synchronize do
            @stdout_buffer += line
            @buffer_cv.signal
          end
        end
      end
    rescue => e
      log("[ERROR] Failed to stream #{label}: #{e.message}")
    end
  end

  def wait_for_ready
    log("[STARTUP] Waiting for process to be ready (timeout: #{@startup_timeout}s)")

    Timeout.timeout(@startup_timeout) do
      loop do
        return if @process_ready && process_alive?
        raise ProcessFailedError, "Process failed during startup" if @status == :failed
        sleep 0.1
      end
    end
  rescue Timeout::Error
    log("[ERROR] Process startup timeout after #{@startup_timeout} seconds")
    stop
    raise ProcessFailedError, "Process failed to start within #{@startup_timeout} seconds"
  end

  def should_restart?
    return false unless @running && @restart_enabled
    return false if @restart_count >= @max_restarts
    @mutex.synchronize { @restart_count += 1 }
    true
  end

  def calculate_backoff
    [2 ** @restart_count, 32].min  # 2, 4, 8, 16, 32 (max)
  end

  def terminate_process
    return unless @pid

    begin
      log("[TERMINATE] Sending TERM signal to PID #{@pid}")
      Process.kill("TERM", @pid)

      Timeout.timeout(5) { @wait_thr&.join }
    rescue Timeout::Error
      log("[TERMINATE] Process didn't exit gracefully, sending KILL")
      begin
        Process.kill("KILL", @pid)
      rescue Errno::ESRCH
        # Process already dead, ignore
      end
    rescue Errno::ESRCH
      log("[WARN] Tried to kill non-existent PID #{@pid}")
    ensure
      @mutex.synchronize { @process_ready = false }
      close_streams
    end
  end

  def close_streams
    [@stdin, @stdout, @stderr].compact.each { |s| s.close rescue nil }
    @stdin = @stdout = @stderr = @wait_thr = nil
  end

  def ensure_ready!
    raise ProcessNotReadyError, "Process is not ready" unless ready?
  end

  def mark_process_failed
    @mutex.synchronize { @process_ready = false }
    @status = :failed
  end

  def log(msg)
    @logger.info(msg)
  rescue => e
    $stderr.puts("[LOG ERROR] #{e.message}: #{msg}")
  end

  # STDIO transport: write request, read matching response
  def stdio_json_rpc_request(request_data, request_json, timeout: 10)
    request_obj = request_data.is_a?(String) ? JSON.parse(request_json) : request_data
    request_id = request_obj["id"] || request_obj[:id]

    write_to_stdin(request_json + "\n")
    response = read_json_rpc_response(request_id: request_id, timeout: timeout)

    JSON.parse(response)
  end

  def write_to_stdin(data)
    ensure_ready!
    @stdin.write(data)
    @stdin.flush
  rescue Errno::EPIPE, IOError => e
    mark_process_failed
    raise ProcessFailedError, "Process stdin not available: #{e.message}"
  end

  def read_json_rpc_response(request_id: nil, timeout: 10)
    ensure_ready!
    start_time = Time.now

    loop do
      @buffer_mutex.synchronize do
        if (json_obj = extract_matching_json_response(@stdout_buffer, request_id))
          return json_obj
        end

        unless process_alive?
          if @stdout_buffer.strip.length > 0
            if (json_obj = extract_matching_json_response(@stdout_buffer, request_id))
              return json_obj
            end
          end
          raise ProcessFailedError, "No data received from stdout"
        end

        if Time.now - start_time > timeout
          raise ProcessFailedError, "Timeout reading JSON-RPC response"
        end

        remaining = timeout - (Time.now - start_time)
        @buffer_cv.wait(@buffer_mutex, remaining)
      end
    end
  end

  def extract_matching_json_response(buffer, request_id)
    return nil if buffer.strip.empty?

    # Try parsing entire buffer as JSON first
    begin
      parsed = JSON.parse(buffer.strip)
      if is_matching_response?(parsed, request_id)
        result = buffer.strip
        buffer.clear
        return result
      end
    rescue JSON::ParserError
      # Not complete, try line by line
    end

    # Try line by line
    lines = buffer.split("\n")
    lines.each_with_index do |line, index|
      next if line.strip.empty?
      begin
        parsed = JSON.parse(line.strip)
        if is_matching_response?(parsed, request_id)
          remaining = lines[(index + 1)..-1] || []
          buffer.replace(remaining.join("\n"))
          return line.strip
        end
      rescue JSON::ParserError
        # Incomplete line
      end
    end

    nil
  end

  def is_matching_response?(parsed_json, request_id)
    return true if request_id.nil?  # Accept any for backwards compatibility
    response_id = parsed_json["id"] || parsed_json[:id]
    response_id == request_id
  end

  # HTTP transport mode
  def http_json_rpc_request(request_json, timeout: 10)
    require "net/http"
    uri = URI(http_endpoint)

    Net::HTTP.start(uri.host, uri.port, open_timeout: timeout, read_timeout: timeout) do |http|
      request = Net::HTTP::Post.new(uri.path)
      request["Content-Type"] = "application/json"
      request.body = request_json

      response = http.request(request)

      if response.code == "200"
        JSON.parse(response.body)
      else
        raise ProcessFailedError, "HTTP request failed: #{response.code}"
      end
    end
  end

  def http_endpoint
    "http://localhost:#{@http_port}/mcp" if @http_port
  end

  def http_endpoint_ready?
    return false unless @http_port && @transport_mode == "http"

    require "net/http"
    uri = URI("http://localhost:#{@http_port}/mcp/health")
    Net::HTTP.start(uri.host, uri.port, open_timeout: 2, read_timeout: 2) do |http|
      response = http.get(uri.path)
      response.code == "200"
    end
  rescue
    false
  end
end
```

## Usage Examples

### Basic Usage

```ruby
supervisor = MCPDockerProcessSupervisor.new(
  command: "docker",
  args: ["run", "--rm", "-i", "mcp-server:latest"],
  env: { "API_KEY" => "secret" },
  startup_timeout: 10,
  max_restarts: 5
)

begin
  supervisor.start  # Blocks until ready or timeout

  # Send JSON-RPC request
  response = supervisor.json_rpc_request({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {}
  })

  puts response["result"]["tools"]
ensure
  supervisor.stop
end
```

### With MCP Client

```ruby
# Create supervisor
supervisor = MCPDockerProcessSupervisor.new(
  command: "docker",
  args: [
    "run", "--rm", "-i",
    "-e", "GITHUB_TOKEN=#{token}",
    "mcp/github-server:latest"
  ],
  startup_timeout: 15
)

# Create MCP client with subprocess transport
client = MCPClient.new(
  mode: :subprocess,
  supervisor: supervisor
)

# Use client normally
client.initialize_session!
tools = client.list_tools
result = client.call_tool("get_repo", owner: "rails", repo: "rails")
```

### HTTP Transport Mode

```ruby
supervisor = MCPDockerProcessSupervisor.new(
  command: "docker",
  args: [
    "run", "--rm",
    "-p", "8080:8080",
    "mcp-server-with-http:latest"
  ],
  transport_mode: "http",
  http_port: 8080,
  startup_timeout: 20
)

supervisor.start

# Requests go over HTTP instead of stdio
response = supervisor.json_rpc_request({
  jsonrpc: "2.0",
  id: 1,
  method: "ping"
})
```

## Integration with AgentTool

Store MCP configuration in AgentTool model:

```ruby
class AgentTool < ApplicationRecord
  def build_mcp_supervisor
    config = prepare_supervisor_config

    MCPDockerProcessSupervisor.new(
      command: config[:command],
      args: config[:args],
      env: config[:env],
      log_path: Rails.root.join("log/mcp_#{id}.log"),
      startup_timeout: config[:startup_timeout] || 10,
      max_restarts: config[:max_restarts] || 5
    )
  end

  def prepare_supervisor_config
    args = mcp_config.fetch("args", [])
    env = mcp_config.fetch("env", {})

    # Apply any transformations (e.g., NPX to Docker)
    {
      command: "docker",
      args: args,
      env: env,
      startup_timeout: mcp_config["startup_timeout"],
      max_restarts: mcp_config["max_restarts"]
    }
  end
end
```

## Process State Management

```ruby
supervisor = MCPDockerProcessSupervisor.new(**config)

# State checks
supervisor.running?       # false - not started yet
supervisor.ready?         # false - not started yet
supervisor.process_alive? # false - no PID

supervisor.start

supervisor.running?       # true
supervisor.ready?         # true
supervisor.process_alive? # true
supervisor.pid            # 12345
supervisor.status         # :running

# Debug info
supervisor.debug_info
# => { running: true, process_ready: true, status: :running,
#      pid: 12345, process_alive: true, restart_count: 0 }

# View logs
supervisor.recent_logs(lines: 10)
# => ["[2025-01-15 10:30:00.123] [SPAWN] Running docker...", ...]
```

## Restart Behavior

```ruby
# Automatic restarts with exponential backoff
# When process crashes, supervisor will:
# 1. Wait 2 seconds, restart (attempt 1)
# 2. Wait 4 seconds, restart (attempt 2)
# 3. Wait 8 seconds, restart (attempt 3)
# ... up to max_restarts

# Manual restart resets the counter
supervisor.restart  # Resets restart_count to 0

# After max_restarts failures, supervision stops
# Check with:
supervisor.debug_info[:restart_count]
```

## Testing

```ruby
RSpec.describe MCPDockerProcessSupervisor do
  let(:config) do
    {
      command: "docker",
      args: ["run", "--rm", "-i", "test-server:latest"],
      log_path: Rails.root.join("tmp/test_mcp.log"),
      startup_timeout: 5
    }
  end

  describe "#start" do
    it "starts Docker process and waits for ready" do
      # Mock Open3.popen3 for testing
      stdin = StringIO.new
      stdout = StringIO.new('{"jsonrpc":"2.0","result":{}}')
      stderr = StringIO.new
      wait_thr = double("wait_thread", pid: 12345, value: double(success?: true))

      allow(Open3).to receive(:popen3).and_return([stdin, stdout, stderr, wait_thr])
      allow_any_instance_of(described_class).to receive(:process_alive?).and_return(true)

      supervisor = described_class.new(**config)
      supervisor.start

      expect(supervisor.running?).to be true
      expect(supervisor.pid).to eq(12345)
    end
  end

  describe "#json_rpc_request", :integration do
    it "sends request and receives response" do
      supervisor = described_class.new(**config)
      supervisor.start

      response = supervisor.json_rpc_request({
        jsonrpc: "2.0",
        id: 1,
        method: "ping"
      })

      expect(response).to include("jsonrpc" => "2.0")
    ensure
      supervisor.stop
    end
  end
end
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| ProcessNotReadyError | Called before start() | Always call supervisor.start first |
| Timeout on startup | Container slow to start | Increase startup_timeout |
| No data from stdout | Process crashed | Check recent_logs, verify Docker image |
| Max restarts reached | Repeated failures | Check debug_info, review logs |
| EPIPE error | Process died mid-request | Check container health, restart |

## Best Practices

1. **Always call stop()**: Use ensure blocks to clean up
2. **Set appropriate timeouts**: Balance between responsiveness and reliability
3. **Log to unique files**: Use tool/agent ID in log path
4. **Handle errors gracefully**: Catch ProcessFailedError and ProcessNotReadyError
5. **Monitor restart count**: Alert if approaching max_restarts

## Next Steps

- [Server Implementation](05-server-implementation.md) - Build MCP servers
- [Multi-Worker Coordination](07-multi-worker-coordination.md) - Database locks for process ownership
