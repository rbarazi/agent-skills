# MCP Server Implementation

## Purpose
Build MCP servers that can be consumed by Claude Desktop, VS Code, and other MCP clients. Provides a DSL for defining tools and resources.

## Architecture

```
MCP Client (Claude Desktop, etc.)
    ↓ HTTP POST JSON-RPC
MCP::ServersController
    ↓ routes to
BaseMCPServer subclass
    ↓ calls
Tool methods
```

## Base MCP Server

The DSL for defining MCP servers:

```ruby
# app/mcp_servers/base_mcp_server.rb
class BaseMCPServer
  PROTOCOL_VERSION = "2025-03-26"

  # Widget resource formats
  UI_WIDGET_MIME_TYPE = "application/vnd.ui.widget+json".freeze
  UI_RESOURCE_URI_PREFIX = "ui://".freeze

  include FunctionSchemaExtractor

  class << self
    attr_reader :tool_method_names, :name, :version, :instructions, :resource_templates

    # Register a method as an MCP tool
    def tool(method_name_sym)
      @tool_method_names ||= []
      @tool_method_names << method_name_sym unless @tool_method_names.include?(method_name_sym)
    end

    # Set server metadata
    def server_name(name)
      @name = name
    end

    def server_version(version)
      @version = version
    end

    def server_instructions(instructions)
      @instructions = instructions
    end

    # Register a UI widget resource template
    def widget_resource(uri_template, name:, description:, mime_type: UI_WIDGET_MIME_TYPE)
      @resource_templates ||= []
      @resource_templates << {
        uri_template: uri_template,
        name: name,
        description: description,
        mime_type: mime_type
      }
    end
  end

  attr_reader :session, :config

  def initialize(session: nil, config: nil)
    @session = session
    @config = (config || {}).with_indifferent_access
  end

  # Handle MCP session initialization
  def initialize_session!(params)
    capabilities = { tools: { listChanged: false } }

    if self.class.resource_templates&.any?
      capabilities[:resources] = { subscribe: false, listChanged: false }
    end

    {
      serverInfo: {
        name: self.class.server_name,
        version: self.class.version
      },
      protocolVersion: PROTOCOL_VERSION,
      capabilities: capabilities,
      instructions: self.class.instructions
    }
  end

  # Main dispatch method
  def call(method:, params: {})
    case method
    when "initialize"               then initialize_session!(params)
    when "ping"                     then {}
    when "resources/list"           then list_resources
    when "resources/templates/list" then list_resource_templates
    when "resources/read"           then read_resource(params[:uri])
    when "tools/list"               then list_available_tools
    when "tools/call"               then call_tool(params[:name], **params[:arguments])
    else
      raise "Unsupported method: #{method}"
    end
  end

  # List all registered tools with their schemas
  def list_available_tools
    tools = (self.class.tool_method_names || []).map do |method_name|
      metadata = method_metadata(method_name.to_s)
      metadata[:name] = method_name.to_s unless metadata.key?(:name)
      metadata
    end
    { tools: tools }
  end

  # Execute a tool by name
  def call_tool(tool_name, **arguments)
    method_sym = (self.class.tool_method_names || []).find { |m| m.to_s == tool_name }

    unless method_sym && respond_to?(method_sym, true)
      raise "Tool not found or method not implemented: #{tool_name}"
    end

    symbolized_args = arguments.deep_symbolize_keys
    public_send(method_sym, **symbolized_args)
  rescue ArgumentError => e
    Rails.logger.error "MCPServer: ArgumentError invoking #{tool_name}: #{e.message}"
    raise
  end

  # List resource templates
  def list_resource_templates
    templates = (self.class.resource_templates || []).map do |template|
      {
        uriTemplate: template[:uri_template],
        name: template[:name],
        description: template[:description],
        mimeType: template[:mime_type]
      }
    end
    { resourceTemplates: templates }
  end

  # Override in subclasses for dynamic resource lists
  def list_resources
    { resources: [], has_more: false, after: nil }
  end

  # Override in subclasses to provide resource content
  def read_resource(uri)
    { contents: [] }
  end

  protected

  # Helper to build tool result with embedded UI widget
  def tool_result_with_widget(text:, widget:, copy_text: nil, tool_name: nil)
    instance_id = SecureRandom.uuid
    tool_identifier = tool_name || self.class.name.demodulize.underscore
    uri = "ui://widgets/#{tool_identifier}/#{instance_id}"

    widget_payload = {
      widget: widget,
      copy_text: copy_text || text
    }

    {
      content: [
        { type: "text", text: text },
        {
          type: "resource",
          resource: {
            uri: uri,
            mimeType: UI_WIDGET_MIME_TYPE,
            text: widget_payload.to_json
          }
        }
      ],
      isError: false
    }
  end

  # UI helper methods
  def ui_card(children:)
    { type: "Card", children: children }
  end

  def ui_text(value, **options)
    { type: "Text", value: value }.merge(options)
  end
end
```

## Function Schema Extractor

Automatically extracts tool schemas from method signatures and YARD docs:

```ruby
# app/utils/function_schema_extractor.rb
module FunctionSchemaExtractor
  def method_metadata(method_name)
    method = method(method_name)
    parameters = extract_parameters(method)
    required_params = extract_required_params(method)
    description = extract_method_description(method_name)

    {
      name: method_name.to_s,
      description: description,
      inputSchema: {
        type: "object",
        properties: parameters,
        required: required_params
      }
    }
  end

  private

  def extract_parameters(method)
    method.parameters.map do |param_type, param_name|
      next unless [:keyreq, :key].include?(param_type)

      param_info = build_parameter_info(method.name, param_name, param_type)
      [param_name.to_sym, param_info]
    end.compact.to_h
  end

  def build_parameter_info(method_name, param_name, param_type)
    param_info = {
      type: infer_parameter_type(method_name, param_name),
      description: extract_param_description(method_name, param_name)
    }

    if enum_values = detect_enum_values(method_name, param_name)
      param_info[:enum] = enum_values
    end

    param_info
  end

  def infer_parameter_type(method_name, param_name)
    docs = extract_method_docs(method_name)
    return "string" unless docs

    type_match = docs.match(/@param\s+\[(.*?)\]\s+#{param_name}/)
    return "string" unless type_match

    case type_match[1].downcase
    when "integer", "fixnum" then "integer"
    when "float", "decimal", "numeric" then "number"
    when "boolean", "bool" then "boolean"
    when "array" then "array"
    when "hash", "object" then "object"
    else "string"
    end
  end

  def extract_required_params(method)
    method.parameters
          .select { |param_type, _| param_type == :keyreq }
          .map { |_, param_name| param_name.to_s }
  end

  def extract_method_docs(method_name)
    method = method(method_name)
    file, line = method.source_location
    return nil unless file && line

    lines = File.readlines(file)
    comment_lines = []

    current_line = line - 2
    while current_line >= 0 && lines[current_line] =~ /^\s*#/
      comment_lines.unshift(lines[current_line].strip.sub(/^\s*#\s?/, ""))
      current_line -= 1
    end

    comment_lines.join("\n")
  end
end
```

## Example MCP Server

```ruby
# app/mcp_servers/weather_mcp_server.rb
class WeatherMCPServer < BaseMCPServer
  server_name "weather-server"
  server_version "1.0.0"
  server_instructions "Get weather information for any location"

  # Register resource template for weather widgets
  widget_resource "ui://widgets/weather/{instance_id}",
    name: "Weather Widget",
    description: "Interactive weather display"

  # Register this method as an MCP tool
  tool :get_weather

  # Get current weather for a location
  # @param [String] location The city name or coordinates
  # @param [String] units Temperature units (metric/imperial)
  # @option units [String] "metric" Celsius
  # @option units [String] "imperial" Fahrenheit
  # @return [Hash] Weather data
  def get_weather(location:, units: "metric")
    # Fetch weather data (implement your logic)
    weather_data = WeatherService.fetch(location, units: units)

    # Return with UI widget
    tool_result_with_widget(
      text: "Weather in #{location}: #{weather_data[:temp]}°",
      widget: ui_card(children: [
        ui_text(location, weight: "bold", size: "lg"),
        ui_text("#{weather_data[:temp]}° #{weather_data[:condition]}")
      ]),
      tool_name: "get_weather"
    )
  end

  tool :get_forecast

  # Get weather forecast
  # @param [String] location The city name
  # @param [Integer] days Number of days (1-7)
  def get_forecast(location:, days: 5)
    forecast = WeatherService.forecast(location, days: days)

    {
      content: [
        { type: "text", text: "#{days}-day forecast for #{location}:\n#{forecast}" }
      ],
      isError: false
    }
  end
end
```

## Controller Implementation

Handle JSON-RPC requests for MCP servers:

```ruby
# app/controllers/mcp/servers_controller.rb
module MCP
  class ServersController < ApplicationController
    include OAuthAuthentication
    include OAuthCors

    allow_unauthenticated_access only: %i[stdio sse options]
    skip_before_action :verify_authenticity_token, only: [:stdio, :sse, :options]

    before_action :authenticate_mcp_client, except: [:options]

    InvalidSessionError = Class.new(StandardError)
    SessionExpiredError = Class.new(StandardError)
    ServerNotFoundError = Class.new(StandardError)

    rescue_from InvalidSessionError do |e|
      render_jsonrpc_error(-32001, "Invalid session", e.message, :unauthorized)
    end

    rescue_from SessionExpiredError do |e|
      render_jsonrpc_error(-32003, "Session expired", e.message, :unauthorized)
    end

    rescue_from ServerNotFoundError do |e|
      render_jsonrpc_error(-32601, "Server not found", e.message, :not_found)
    end

    # Main JSON-RPC endpoint
    def stdio
      output = mcp_server.call(
        method: rpc_params&.dig(:method),
        params: rpc_params&.dig(:params)
      )
      render_jsonrpc_success(output)
    end

    # SSE streaming endpoint (placeholder)
    def sse
      head :ok
    end

    # CORS preflight
    def options
      head :ok
    end

    private

    def allowed_cors_headers
      super + %w[Mcp-Session-Id]
    end

    def exposed_cors_headers
      super + %w[Mcp-Session-Id]
    end

    def tool
      @tool ||= Tool.find_by(name: permitted_params[:mcp_server_name])
      raise ServerNotFoundError, "Tool not found" unless @tool
      @tool
    end

    def mcp_client_session
      @mcp_client_session ||= find_or_create_session
    end

    def find_or_create_session
      session_id = request.headers["Mcp-Session-Id"]

      session = tool.mcp_client_sessions.find_by(id: session_id) if session_id.present?

      if session&.valid? && !session.expired?
        extend_session_activity(session)
        session
      elsif rpc_params&.dig(:method) == "initialize"
        create_session
      else
        raise InvalidSessionError, "Session not found"
      end
    end

    def create_session
      MCP::ClientSession.create!(
        tool: tool,
        mcp_server_name: tool.name,
        client_info_snapshot: rpc_params&.dig(:params, :clientInfo),
        expires_at: 30.minutes.from_now,
        last_activity_at: Time.current
      )
    end

    def extend_session_activity(session)
      session.extend_activity!
    end

    def mcp_server
      @mcp_server ||= tool.server_instance(session: mcp_client_session).tap do |server|
        raise ServerNotFoundError, "Server not found" unless server
      end
    end

    def permitted_params
      params.permit(:mcp_server_name, :jsonrpc, :method, :id, params: {}, server: {})
    end

    def rpc_params
      permitted_params[:server]
    end

    def render_jsonrpc_success(result)
      response.headers["Mcp-Session-Id"] = mcp_client_session&.id
      render json: {
        jsonrpc: "2.0",
        id: rpc_params&.dig(:id),
        result: result
      }
    end

    def render_jsonrpc_error(code, message, details = nil, status = :internal_server_error)
      error_data = { code: code, message: message }
      error_data[:data] = { details: details } if details

      render json: {
        jsonrpc: "2.0",
        id: rpc_params&.dig(:id),
        error: error_data
      }, status: status
    end
  end
end
```

## Routes

```ruby
# config/routes.rb
namespace "mcp" do
  post ":mcp_server_name/", to: "servers#stdio", as: :stdio_mcp_server
  get ":mcp_server_name/stream", to: "servers#sse", as: :sse_mcp_server
  match ":mcp_server_name/", to: "servers#options", via: :options
  match ":mcp_server_name/stream", to: "servers#options", via: :options
end
```

## Tool Model Integration

Link MCP servers to Tool model:

```ruby
# app/models/tool.rb
class Tool < ApplicationRecord
  MCP_SERVER_CLASSES = {
    "weather" => "WeatherMCPServer",
    "github" => "GithubMCPServer",
    # Add more mappings
  }.freeze

  def server_class
    class_name = MCP_SERVER_CLASSES[name] || "#{name.camelize}MCPServer"
    class_name.constantize
  rescue NameError
    nil
  end

  def server_instance(session: nil)
    klass = server_class
    return nil unless klass

    klass.new(session: session, config: mcp_config)
  end

  def has_mcp_server?
    server_class.present?
  end
end
```

## Testing

```ruby
RSpec.describe WeatherMCPServer do
  let(:session) { create(:mcp_client_session) }
  let(:server) { described_class.new(session: session) }

  describe "#list_available_tools" do
    it "returns registered tools with schemas" do
      result = server.list_available_tools

      expect(result[:tools]).to include(
        hash_including(
          name: "get_weather",
          inputSchema: hash_including(
            type: "object",
            properties: hash_including(:location, :units)
          )
        )
      )
    end
  end

  describe "#call_tool" do
    it "executes the tool and returns result" do
      allow(WeatherService).to receive(:fetch).and_return(
        { temp: 72, condition: "Sunny" }
      )

      result = server.call_tool("get_weather", location: "New York")

      expect(result[:content]).to include(
        hash_including(type: "text")
      )
    end
  end

  describe "#call" do
    it "handles initialize method" do
      result = server.call(method: "initialize", params: {})

      expect(result[:serverInfo][:name]).to eq("weather-server")
      expect(result[:protocolVersion]).to eq("2025-03-26")
    end

    it "handles tools/list method" do
      result = server.call(method: "tools/list", params: {})

      expect(result[:tools]).to be_an(Array)
    end
  end
end
```

## Common Patterns

### Error Handling

```ruby
def risky_tool(param:)
  result = external_service.call(param)

  {
    content: [{ type: "text", text: result }],
    isError: false
  }
rescue ExternalService::Error => e
  {
    content: [{ type: "text", text: "Error: #{e.message}" }],
    isError: true
  }
end
```

### Accessing Session Data

```ruby
def user_specific_tool(data:)
  # Access session info
  user_id = session.user_id
  client_info = session.client_info_snapshot

  # Access config
  api_key = config[:api_key]

  # Your logic here
end
```

### Resource Reading

```ruby
def read_resource(uri)
  case uri
  when /^ui:\/\/widgets\/weather\/(.+)$/
    instance_id = $1
    widget_data = cache.fetch("weather_widget:#{instance_id}")

    {
      contents: [{
        uri: uri,
        mimeType: UI_WIDGET_MIME_TYPE,
        text: widget_data.to_json
      }]
    }
  else
    { contents: [] }
  end
end
```

## Next Steps

- [Session Management](06-session-management.md) - Client session handling
- [Multi-Worker Coordination](07-multi-worker-coordination.md) - Database locks
