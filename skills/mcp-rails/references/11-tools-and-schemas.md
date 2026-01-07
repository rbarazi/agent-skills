# Tools and Schemas (Multi-Tool Server)

## Purpose
Implement an MCP server that exposes multiple tools with clear schemas, shared helpers, and proper validation. Use `app/mcp_servers/weather_mcp_server/server.rb` as the canonical reference implementation.

## Tool Registration Pattern

Register tools declaratively at class level:

```ruby
module MyFeatureMCPServer
  class Server < BaseMCPServer
    server_name "my_feature"
    server_version "1.0.0"
    server_instructions "MCP Server for MyFeature operations."

    # Register all tools at class level
    tool :get_item
    tool :update_item
    tool :list_items

    # Tool implementation follows below...
  end
end
```

## Tool Method Structure

Keep tool methods small with this pattern:

1. **Validate inputs early** - Raise or return error for invalid data
2. **Normalize inputs** - Standardize format, handle edge cases
3. **Call backing service** - Delegate data fetching to service classes
4. **Build plain text response** - For non-UI clients (Claude Desktop, etc.)
5. **Return MCP-compliant result** - Standard content array format

```ruby
# Get an item by ID
#
# @param [String] item_id The unique identifier for the item
# @param [String] format Response format
# @option format [String] "brief" Short summary only
# @option format [String] "detailed" Full item details
# @return [Hash] Item information
def get_item(item_id:, format: "brief")
  Rails.logger.debug("#{self.class.name}: Getting item #{item_id}")

  # 1. Validate
  validate_format!(format)

  # 2. Normalize
  normalized_id = normalize_item_id(item_id)
  return error_result("Invalid item ID format") unless normalized_id

  # 3. Fetch via service
  item_data = item_service.find(normalized_id, format: format)
  return error_result("Item not found: #{item_id}") if item_data.blank?

  # 4. Build plain text
  text = "Item #{normalized_id}: #{item_data[:name]} - #{item_data[:summary]}"

  # 5. Return MCP result
  { content: [{ type: "text", text: text }], isError: false }
end
```

## Schema Extraction

`BaseMCPServer` uses `FunctionSchemaExtractor` to build JSON schema from method signatures and YARD documentation:

```ruby
# The weather forecast for a location
#
# @param [String] location City and country code (e.g., "Paris,FR")
# @param [String] unit Temperature unit
# @option unit [String] "celsius" Celsius scale
# @option unit [String] "fahrenheit" Fahrenheit scale
# @return [Hash] Forecast data with temperatures
def get_weather_forecast(location:, unit: "celsius")
  # Implementation...
end
```

Generates this JSON schema:

```json
{
  "name": "get_weather_forecast",
  "description": "The weather forecast for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City and country code (e.g., \"Paris,FR\")"
      },
      "unit": {
        "type": "string",
        "description": "Temperature unit",
        "enum": ["celsius", "fahrenheit"],
        "default": "celsius"
      }
    },
    "required": ["location"]
  }
}
```

### Schema Guidelines

1. **Keep parameter names stable** - Changing names breaks client integrations
2. **Use simple types** - `string`, `number`, `boolean`, `array` where possible
3. **Document constraints** - Use `@option` for enum values, describe formats
4. **Mark required params** - Only keyword args without defaults are required
5. **Provide examples** - Include example values in descriptions

## Shared Helpers Pattern

Extract common operations to private methods:

```ruby
class Server < BaseMCPServer
  # ... tool registrations and implementations ...

  private

  # Validation helpers
  def validate_format!(format)
    valid_formats = %w[brief detailed full]
    unless valid_formats.include?(format.to_s)
      raise ArgumentError, "Invalid format. Expected one of #{valid_formats.join(', ')}"
    end
  end

  def validate_limit!(limit)
    limit_int = limit.to_i
    unless limit_int.between?(1, 100)
      raise ArgumentError, "Limit must be between 1 and 100"
    end
    limit_int
  end

  # Normalization helpers
  def normalize_item_id(id)
    return nil if id.blank?
    id.to_s.strip.downcase.gsub(/[^a-z0-9-]/, '')
  end

  def normalize_location(location)
    parts = location.to_s.split(",").map(&:strip).reject(&:blank?)
    return nil unless parts.length.in?([2, 3])

    country = parts.last
    return nil unless country.match?(/\A[a-zA-Z]{2}\z/)

    parts[-1] = country.upcase
    parts.join(",")
  end

  # Service accessors
  def item_service
    @item_service ||= ItemService.new
  end

  def external_client
    @external_client ||= ExternalApiClient.new(api_key: api_key)
  end

  def api_key
    config.dig(:env, "EXTERNAL_API_KEY").presence || ENV["EXTERNAL_API_KEY"]
  end

  # Standard error result
  def error_result(message)
    {
      content: [{ type: "text", text: message }],
      isError: true
    }
  end
end
```

## Weather MCP Reference Pattern

From `app/mcp_servers/weather_mcp_server/server.rb`:

```ruby
module WeatherMCPServer
  class Server < BaseMCPServer
    STYLE_PRESETS = {
      clear: { background: "...", icon: "..." },
      cloudy: { background: "...", icon: "..." },
      # ... more presets
    }.freeze

    server_name "weather"
    server_version "1.0.0"
    server_instructions "MCP Server for weather forecasting."

    # Widget resources for UI rendering
    widget_resource "ui://widgets/weather/{instance_id}",
      name: "Weather Widget",
      description: "Displays current weather as a Card widget"

    tool :get_current_weather
    tool :get_weather_forecast

    def get_current_weather(location:, unit: "celsius")
      unit_str = validate_unit!(unit)
      normalized = normalize_location(location)
      return error_result("Invalid location format") unless normalized

      data = openweather_client.current_weather(location: normalized, unit: unit_str)
      text = "Current weather in #{normalized}: #{data[:temperature]}#{data[:unit_symbol]}"

      # With UI widget
      widget_data = weather_widget_data(weather_data: data)
      WidgetTemplateService.hydrate_for_tool_result(
        template: :weatherCurrent,
        data: widget_data,
        text: text,
        tool_name: "weather"
      )
    end

    private

    def validate_unit!(unit)
      valid = %w[celsius fahrenheit]
      raise ArgumentError, "Invalid unit" unless valid.include?(unit.to_s)
      unit.to_s
    end

    def openweather_client
      @openweather_client ||= OpenweatherClient.new(api_key: api_key)
    end

    def api_key
      config.dig(:env, "OPENWEATHER_API_KEY").presence || ENV["OPENWEATHER_API_KEY"]
    end
  end
end
```

## Directory Structure

```
app/mcp_servers/
└── my_feature_mcp_server/
    ├── server.rb              # Main MCP server class
    ├── my_feature_client.rb   # External API client (optional)
    └── data_transformer.rb    # Data transformation helpers (optional)

spec/mcp_servers/
└── my_feature_mcp_server/
    ├── server_spec.rb         # Tool behavior tests
    └── my_feature_client_spec.rb
```

## Testing Checklist

### Tool Registration
```ruby
RSpec.describe MyFeatureMCPServer::Server do
  describe "tool registration" do
    it "registers get_item tool" do
      tools = described_class.new(config: {}).tools_list
      expect(tools.map { |t| t[:name] }).to include("get_item")
    end
  end
end
```

### Input Validation
```ruby
describe "#get_item" do
  it "rejects invalid format" do
    expect { server.get_item(item_id: "123", format: "bad") }
      .to raise_error(ArgumentError, /Invalid format/)
  end
end
```

### Backing Service Integration
```ruby
describe "#get_item" do
  let(:item_service) { instance_double(ItemService) }

  before do
    allow(ItemService).to receive(:new).and_return(item_service)
    allow(item_service).to receive(:find).and_return({ name: "Test", summary: "..." })
  end

  it "calls service with normalized ID" do
    server.get_item(item_id: "ABC-123", format: "brief")
    expect(item_service).to have_received(:find).with("abc-123", format: "brief")
  end
end
```

### MCP-Compliant Response
```ruby
describe "#get_item" do
  it "returns MCP-compliant content array" do
    result = server.get_item(item_id: "123", format: "brief")

    expect(result[:content]).to be_an(Array)
    expect(result[:content].first[:type]).to eq("text")
    expect(result[:isError]).to be false
  end
end
```

## Next Steps

- [UI Widget Pipeline](12-ui-widget-pipeline.md) - Adding rich UI widgets to tool results
