---
name: mcp-widget-authoring
description: Create ChatKit UI widgets in MCP servers. Use when building visual components that render in ChatKit from tool results. Covers widget templates with JSON Schema validation, WidgetTemplateService for hydration, BaseMCPServer patterns, and multi-channel support for Slack. Triggers on widget template, MCP widget, tool result widget, or ChatKit Card.
---

# MCP Widget Authoring

Create visual widgets that render in ChatKit from MCP tool results.

## Quick Start

Widgets flow from MCP server → tool result → ChatKit rendering:

```
MCP Server Tool → WidgetTemplateService.hydrate_for_tool_result() → ui:// resource → ChatKit
```

**Key components:**
1. Widget template file (`.widget` or `.yml`)
2. `WidgetTemplateService` for hydration
3. `BaseMCPServer` for tool registration
4. MCP-compliant tool result format

## Widget Template Format

Create templates in `config/ui_widget_templates/`:

```json
{
  "version": "1.0",
  "name": "weatherCurrent",
  "copy_text": "Weather in {{location}}: {{temperature}}",
  "template": "{\"type\":\"Card\",\"children\":[{\"type\":\"Text\",\"value\":\"{{location}}\"}]}",
  "jsonSchema": {
    "type": "object",
    "properties": {
      "location": { "type": "string" },
      "temperature": { "type": "string" }
    },
    "required": ["location", "temperature"]
  }
}
```

## Using in MCP Server

```ruby
class WeatherMCPServer::Server < BaseMCPServer
  server_name "weather"
  widget_resource "ui://widgets/weather/{instance_id}",
    name: "Weather Widget",
    description: "Displays current weather"

  tool :get_current_weather

  def get_current_weather(location:, unit: "celsius")
    weather_data = fetch_weather(location, unit)

    WidgetTemplateService.hydrate_for_tool_result(
      template: :weatherCurrent,
      data: { location: location, temperature: "#{weather_data[:temp]}#{unit_symbol}" },
      text: "Current weather in #{location}: #{weather_data[:temp]}",
      tool_name: "weather"
    )
  end
end
```

## Result Format

The tool result embeds a `ui://` resource:

```json
{
  "content": [
    { "type": "text", "text": "Current weather in Toronto: 72°F" },
    {
      "type": "resource",
      "resource": {
        "uri": "ui://widgets/weather/abc123",
        "mimeType": "application/vnd.ui.widget+json",
        "text": "{\"widget\":{...},\"copy_text\":\"...\"}"
      }
    }
  ],
  "isError": false
}
```

## Reference Files

**For detailed patterns, see:**
- [templates.md](references/templates.md) - Widget template format and JSON Schema
- [hydration.md](references/hydration.md) - WidgetTemplateService usage patterns
- [mcp-server.md](references/mcp-server.md) - BaseMCPServer integration
- [components.md](references/components.md) - Available ChatKit components (Card, Text, Image, etc.)
- [multi-channel.md](references/multi-channel.md) - Slack Work Objects and Block Kit
