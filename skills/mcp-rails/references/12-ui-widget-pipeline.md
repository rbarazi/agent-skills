# UI Widget Pipeline (MCP-UI)

## Purpose
Expose rich UI widget components alongside MCP tool results. This enables ChatKit, Slack, and other UI-aware clients to render interactive widgets while maintaining plain text fallback for CLI clients.

## Reference Playbooks
- `docs/jtbd/add_component_to_mcp_server.md`
- `docs/jtbd/render_widget_from_tool_result.md`

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     MCP Tool Call                                 │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   MCP Server Tool Method                          │
│  1. Validate inputs                                               │
│  2. Fetch data from backing service                               │
│  3. Build widget data structure                                   │
│  4. Call WidgetTemplateService.hydrate_for_tool_result           │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                 WidgetTemplateService                             │
│  - Loads template from config/ui_widget_templates/               │
│  - Hydrates placeholders with data                               │
│  - Returns MCP-compliant content array                           │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│               MCP Tool Result Response                            │
│  {                                                                │
│    "content": [                                                   │
│      { "type": "text", "text": "Plain text for CLI" },           │
│      { "type": "resource", "resource": { widget payload } }      │
│    ],                                                             │
│    "isError": false                                               │
│  }                                                                │
└──────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Implementation

### Step 1: Create Widget Template

Create a `.widget` file in `config/ui_widget_templates/`:

```json
// config/ui_widget_templates/myWidget.widget
{
  "version": "1.0",
  "name": "myWidget",
  "copy_text": "Summary: {{title}} - {{description}}",
  "template": "{\"type\":\"Card\",\"theme\":\"light\",\"children\":[{\"type\":\"Title\",\"value\":{{ title | json }}},{\"type\":\"Text\",\"value\":{{ description | json }}}]}",
  "jsonSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "title": { "type": "string" },
      "description": { "type": "string" }
    },
    "required": ["title", "description"],
    "additionalProperties": false
  }
}
```

Template syntax:
- `{{variable}}` - Simple string substitution (for plain text values)
- `{{ variable | json }}` - JSON-encoded value (for strings, arrays, objects that need quoting)
- `copy_text` - Text for clipboard copy action
- `jsonSchema` - Validates required data before rendering

**Note:** The WidgetTemplateService handles both syntaxes. For simple string values, use `{{variable}}`. For values that need JSON encoding (to preserve quotes, arrays, nested objects), use the json filter.

### Step 2: Register Widget Resource in MCP Server

```ruby
module MyFeatureMCPServer
  class Server < BaseMCPServer
    server_name "my_feature"
    server_version "1.0.0"

    # Register UI widget resource template
    widget_resource "ui://widgets/myWidget/{instance_id}",
      name: "My Widget",
      description: "Displays feature data as a Card widget"

    # Optional: Slack Block Kit resource
    slack_blocks_resource "slack://blocks/myWidget/{instance_id}",
      name: "My Widget Block Kit",
      description: "Displays feature data as Slack Block Kit blocks"

    # Optional: Slack Work Object resource
    slack_work_object_resource "slack://work-objects/myWidget/{instance_id}",
      name: "My Widget Work Object",
      description: "Displays feature data as Slack Work Object entity"

    tool :get_feature_data
  end
end
```

### Step 3: Implement Tool with Widget Hydration

```ruby
def get_feature_data(item_id:)
  # 1. Validate and fetch data
  data = backing_service.fetch(item_id)
  return error_result("Item not found") if data.blank?

  # 2. Build plain text for non-UI clients
  text = "Feature: #{data[:title]} - #{data[:summary]}"

  # 3. Build widget data structure (matches jsonSchema)
  widget_data = {
    title: data[:title],
    description: data[:summary]
  }

  # 4. Hydrate and return
  WidgetTemplateService.hydrate_for_tool_result(
    template: :myWidget,
    data: widget_data,
    text: text,
    tool_name: "myWidget"
  )
end
```

### Step 4: Build Widget Data Structures

Map your service data to widget schema keys:

```ruby
private

def weather_widget_data(weather_data:)
  style = condition_style(weather_data[:condition])

  {
    location: weather_data[:location],
    background: style[:background],
    conditionImage: style[:icon],
    conditionDescription: weather_data[:condition].presence || "Weather unavailable",
    temperature: "#{weather_data[:temperature]}#{weather_data[:unit_symbol]}"
  }
end

def weather_forecast_widget_data(forecast_data:)
  style = condition_style(forecast_data[:condition])

  # Build precomputed children arrays for complex widgets
  forecast_children = Array(forecast_data[:forecast]).map do |entry|
    {
      type: "Col",
      align: "center",
      gap: 0,
      children: [
        { type: "Image", src: entry[:icon] || style[:icon], size: 40 },
        { type: "Text", value: "#{entry[:temperature]}#{forecast_data[:unit_symbol]}" }
      ]
    }
  end

  {
    location: forecast_data[:location],
    background: style[:background],
    conditionImage: forecast_data[:condition_image] || style[:icon],
    conditionDescription: forecast_data[:condition],
    lowTemperature: "#{forecast_data[:low_temperature]}#{forecast_data[:unit_symbol]}",
    highTemperature: "#{forecast_data[:high_temperature]}#{forecast_data[:unit_symbol]}",
    forecastChildren: forecast_children
  }
end
```

## Weather MCP Concrete Example

Full implementation from `app/mcp_servers/weather_mcp_server/server.rb`:

```ruby
def get_current_weather(location:, unit: "celsius")
  unit_str = validate_unit!(unit)
  normalized_location = normalize_location(location)
  return error_result("Invalid location format") unless normalized_location

  # Fetch from external API
  weather_data = openweather_client.current_weather(
    location: normalized_location,
    unit: unit_str
  )

  # Plain text for CLI clients
  text = "Current weather in #{normalized_location}: " \
         "#{weather_data[:temperature]}#{weather_data[:unit_symbol]}, " \
         "#{weather_data[:condition]}"

  # Build widget data for ChatKit
  widget_data = weather_widget_data(weather_data: weather_data)

  # Build Slack-specific data (optional)
  slack_data = slack_weather_current_data(weather_data: weather_data)

  # Hydrate with both UI widget and Slack Block Kit
  WidgetTemplateService.hydrate_for_tool_result(
    template: :weatherCurrent,
    slack_blocks_template: :slackBlockKitWeatherCurrent,
    data: widget_data.merge(slack_data),
    text: text,
    tool_name: "weather"
  )
end
```

## WidgetTemplateService API

### Basic Hydration

```ruby
# Just get the widget structure
widget = WidgetTemplateService.hydrate(:myWidget, {
  title: "Hello",
  description: "World"
})
```

### MCP Tool Result

```ruby
# Full MCP-compliant tool result with embedded resource
result = WidgetTemplateService.hydrate_for_tool_result(
  template: :myWidget,
  data: { title: "Hello", description: "World" },
  text: "Summary: Hello - World",
  tool_name: "myWidget"
)

# Returns:
# {
#   content: [
#     { type: "text", text: "Summary: Hello - World" },
#     {
#       type: "resource",
#       resource: {
#         uri: "ui://widgets/myWidget/abc-123-uuid",
#         mimeType: "application/vnd.ui.widget+json",
#         text: "{\"widget\":{...},\"copy_text\":\"...\"}"
#       }
#     }
#   ],
#   isError: false
# }
```

### Multi-Channel Support (ChatKit + Slack)

```ruby
result = WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,             # ChatKit widget
  slack_blocks_template: :slackBlocks,   # Slack Block Kit (optional)
  slack_template: :slackWorkObject,      # Slack Work Object (optional)
  data: combined_data,
  text: plain_text,
  tool_name: "weather"
)
```

### OpenAI Apps SDK Format

```ruby
result = WidgetTemplateService.hydrate_for_apps_sdk(
  template: :myWidget,
  data: { title: "Hello", description: "World" },
  text: "Summary: Hello - World",
  structured_content: { extra: "data for model" }
)

# Returns Apps SDK format with structuredContent + _meta
```

## Client Rendering Rules (ChatKit)

ChatKit extracts widgets from MCP tool results when:

1. `resource.uri` starts with `ui://`
2. `resource.mimeType` is `application/vnd.ui.widget+json`

Payload structure:

```json
{
  "widget": {
    "type": "Card",
    "theme": "dark",
    "children": [...]
  },
  "copy_text": "Text for clipboard"
}
```

## Directory Structure

```
config/ui_widget_templates/
├── myWidget.widget           # JSON widget template
├── weatherCurrent.widget     # Weather current conditions
├── weatherForecast.widget    # Weather forecast
├── slackBlockKitWeatherCurrent.yml   # Slack Block Kit template
└── slackWeatherForecast.yml  # Slack Work Object template

app/mcp_servers/
└── my_feature_mcp_server/
    └── server.rb             # Tool implementation

app/services/
└── widget_template_service.rb  # Template hydration service
```

## Testing

### Widget Hydration

```ruby
RSpec.describe WidgetTemplateService do
  describe ".hydrate" do
    it "hydrates widget with data" do
      widget = described_class.hydrate(:myWidget, {
        title: "Test Title",
        description: "Test Description"
      })

      expect(widget[:type]).to eq("Card")
      expect(widget[:children].first[:value]).to eq("Test Title")
    end
  end

  describe ".hydrate_for_tool_result" do
    it "returns MCP-compliant structure" do
      result = described_class.hydrate_for_tool_result(
        template: :myWidget,
        data: { title: "Test", description: "..." },
        text: "Plain text",
        tool_name: "myWidget"
      )

      expect(result[:content]).to be_an(Array)
      expect(result[:content].length).to eq(2)

      text_content = result[:content].find { |c| c[:type] == "text" }
      expect(text_content[:text]).to eq("Plain text")

      resource = result[:content].find { |c| c[:type] == "resource" }
      expect(resource[:resource][:uri]).to start_with("ui://widgets/myWidget/")
      expect(resource[:resource][:mimeType]).to eq("application/vnd.ui.widget+json")
    end
  end
end
```

### MCP Server Tool with Widget

```ruby
RSpec.describe MyFeatureMCPServer::Server do
  describe "#get_feature_data" do
    let(:server) { described_class.new(config: {}) }
    let(:service) { instance_double(BackingService) }

    before do
      allow(BackingService).to receive(:new).and_return(service)
      allow(service).to receive(:fetch).and_return({
        title: "Test Feature",
        summary: "Feature description"
      })
    end

    it "returns UI widget resource" do
      result = server.get_feature_data(item_id: "123")

      resource = result[:content].find { |c| c[:type] == "resource" }
      expect(resource).to be_present
      expect(resource[:resource][:uri]).to start_with("ui://widgets/")
    end

    it "includes plain text for CLI clients" do
      result = server.get_feature_data(item_id: "123")

      text = result[:content].find { |c| c[:type] == "text" }
      expect(text[:text]).to include("Test Feature")
    end
  end
end
```

## Common Pitfalls

1. **Missing required schema fields** - Validate data before hydration
2. **Invalid JSON in template** - Test templates with sample data
3. **Forgetting plain text** - Always include text content for CLI clients
4. **Wrong mimeType** - Use `application/vnd.ui.widget+json` for UI widgets
5. **Precomputed arrays** - For complex widgets, build children arrays in Ruby
6. **Template caching** - Call `WidgetTemplateService.clear_cache!` in development

## Next Steps

- [Tools and Schemas](11-tools-and-schemas.md) - Multi-tool server patterns
- [UI Resources](09-ui-resources.md) - MCP resource formats
