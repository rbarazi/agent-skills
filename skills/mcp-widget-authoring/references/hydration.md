# WidgetTemplateService

Service for loading and hydrating widget templates.

## Basic Usage

### Hydrate for Tool Result (MCP)

```ruby
result = WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,
  data: {
    location: "Toronto",
    temperature: "72°F",
    background: "linear-gradient(111deg, #1769C8 0%, #31A3F8 100%)",
    conditionImage: "https://example.com/sunny.png",
    conditionDescription: "Sunny and warm"
  },
  text: "Current weather in Toronto: 72°F, Sunny",
  tool_name: "weather"
)
```

Returns MCP-compliant structure:

```ruby
{
  content: [
    { type: "text", text: "Current weather in Toronto: 72°F, Sunny" },
    {
      type: "resource",
      resource: {
        uri: "ui://widgets/weather/abc123-uuid",
        mimeType: "application/vnd.ui.widget+json",
        text: "{\"widget\":{...},\"copy_text\":\"...\"}"
      }
    }
  ],
  isError: false
}
```

### Just Hydrate Widget

```ruby
widget = WidgetTemplateService.hydrate(:weather, {
  location: "Toronto",
  temperature: "72",
  unit_symbol: "°F",
  condition: "Sunny"
})
# Returns: { type: "Card", children: [...] }
```

## Multi-Channel Support

### With Slack Block Kit

```ruby
result = WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,
  slack_blocks_template: :slackBlockKitWeatherCurrent,
  data: widget_data.merge(slack_data),
  text: "Current weather in Toronto: 72°F",
  tool_name: "weather"
)
```

### With Slack Work Objects

```ruby
result = WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherForecast,
  slack_template: :slackWeatherForecast,
  data: widget_data.merge(slack_data),
  text: "Forecast for Toronto...",
  tool_name: "weatherForecast"
)
```

## OpenAI Apps SDK Format

```ruby
result = WidgetTemplateService.hydrate_for_apps_sdk(
  template: :weather,
  data: {
    location: "Toronto",
    temperature: "42",
    unit_symbol: "°C"
  },
  text: "Current weather in Toronto: 42°C",
  structured_content: { location: "Toronto", temp: 42 }
)
```

Returns:

```ruby
{
  structuredContent: { location: "Toronto", temp: 42 },
  content: [{ type: "text", text: "..." }],
  _meta: {
    widget: { ... },
    copy_text: "...",
    template: "weather",
    format: "ui_widget",
    version: "1.0"
  }
}
```

## Service Methods

### List Available Templates

```ruby
WidgetTemplateService.available_templates
# => ["weather", "weatherCurrent", "weatherForecast", "slackWeatherForecast"]
```

### Clear Cache (Development)

```ruby
WidgetTemplateService.clear_cache!
```

## Implementation Details

### Template Loading

```ruby
def load_template(name)
  @template_cache ||= {}
  key = name.to_s
  @template_cache[key] ||= begin
    path = find_template_path(key)
    raise ArgumentError, "Template not found: #{name}" unless path

    {
      name: key,
      path: path,
      format: template_format(path),  # :yaml or :widget
      content: parse_template(path, format)
    }
  end
end
```

### Placeholder Substitution

```ruby
PLACEHOLDER_PATTERN = /\{\{(\w+)\}\}/
JSON_TEMPLATE_PATTERN = /\{\{\s*\(?([\w-]+)\)?\s*\|\s*tojson\s*\}\}/

def hydrate_string(template, data)
  template.gsub(PLACEHOLDER_PATTERN) do |_match|
    key = ::Regexp.last_match(1)
    data[key].to_s
  end
end

def render_json_widget(template, data)
  rendered = template.to_s.dup

  # JSON-safe substitution
  rendered.gsub!(JSON_TEMPLATE_PATTERN) do
    key = ::Regexp.last_match(1)
    value = data[key]
    value.nil? ? "null" : value.to_json
  end

  # Simple substitution
  rendered.gsub!(PLACEHOLDER_PATTERN) do |_match|
    key = ::Regexp.last_match(1)
    data[key].to_s
  end

  JSON.parse(rendered).deep_symbolize_keys
end
```

### Conditional Rendering

```ruby
def apply_when_filters(structure, data)
  case structure
  when Array
    structure.filter_map { |item| apply_when_filters(item, data) }
  when Hash
    condition_key = structure[:when] || structure["when"]
    return nil if condition_key.present? && data[condition_key.to_s].blank?

    filtered = {}
    structure.each do |key, value|
      next if key.to_s == "when"
      pruned_value = apply_when_filters(value, data)
      filtered[key] = pruned_value unless pruned_value.nil?
    end
    filtered
  else
    structure
  end
end
```

### Building Tool Result

```ruby
def build_tool_result(text:, widget:, copy_text:, tool_name:)
  instance_id = SecureRandom.uuid
  uri = "ui://widgets/#{tool_name}/#{instance_id}"

  widget_payload = { widget: widget, copy_text: copy_text }

  {
    content: [
      { type: "text", text: text },
      {
        type: "resource",
        resource: {
          uri: uri,
          mimeType: BaseMCPServer::UI_WIDGET_MIME_TYPE,
          text: widget_payload.to_json
        }
      }
    ],
    isError: false
  }
end
```

## Error Handling

### Missing Required Fields

```ruby
def validate_required_data!(schema, data)
  return unless schema.respond_to?(:[])

  schema = schema.with_indifferent_access
  required_keys = schema[:required] || []
  missing = required_keys.select { |key| data[key].blank? }

  return if missing.empty?

  raise ArgumentError, "Missing required data for widget template: #{missing.join(', ')}"
end
```

### Invalid JSON

```ruby
def render_json_widget(template, data)
  # ... substitution logic
  JSON.parse(rendered).deep_symbolize_keys
rescue JSON::ParserError => e
  raise ArgumentError, "Widget template produced invalid JSON: #{e.message}"
end
```
