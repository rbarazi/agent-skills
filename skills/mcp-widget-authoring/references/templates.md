# Widget Template Format

Templates define widget structure with placeholder substitution.

## File Location

Store templates in `config/ui_widget_templates/`:

```
config/ui_widget_templates/
├── weather.widget
├── weatherCurrent.widget
├── weatherForecast.widget
└── slackWeatherCurrent.yml
```

## Template Formats

### JSON Widget Format (`.widget`)

```json
{
  "version": "1.0",
  "name": "weatherCurrent",
  "copy_text": "Weather in {{location}}: {{temperature}} - {{conditionDescription}}",
  "template": "{\"type\":\"Card\",\"theme\":\"dark\",\"children\":[...]}",
  "jsonSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "location": { "type": "string" },
      "temperature": { "type": "string" },
      "conditionDescription": { "type": "string" }
    },
    "required": ["location", "temperature", "conditionDescription"],
    "additionalProperties": false
  },
  "outputJsonPreview": {
    "type": "Card",
    "children": [...]
  }
}
```

### YAML Format (`.yml`)

```yaml
version: "1.0"
name: weather
copy_text: "Weather in {{location}} — {{temperature}}{{unit_symbol}} — {{condition}}"
widget:
  type: Card
  children:
    - type: Text
      value: "Weather in {{location}}"
      weight: semibold
      size: lg
    - type: Text
      value: "{{temperature}}{{unit_symbol}}"
      size: xl
      weight: bold
    - type: Text
      value: "{{condition}}"
      color: secondary
      when: condition  # Conditional rendering
```

## Placeholder Syntax

### Simple Placeholders

```
{{variable}}
```

Replaced with `data[variable].to_s`.

### JSON-Safe Placeholders

```
{{ (variable) | tojson }}
```

Outputs JSON-encoded value, handling quotes and escaping.

### Conditional Rendering

```yaml
- type: Text
  value: "Feels like {{feels_like}}"
  when: feels_like  # Only rendered if feels_like is present
```

## JSON Schema Validation

Define required fields and types:

```json
{
  "jsonSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "location": { "type": "string" },
      "temperature": { "type": "string" },
      "background": { "type": "string" },
      "conditionImage": { "type": "string" }
    },
    "required": ["location", "temperature"],
    "additionalProperties": false
  }
}
```

Service validates data against schema before hydration.

## Complete Weather Example

```json
{
  "version": "1.0",
  "name": "weatherCurrent",
  "copy_text": "Weather in {{location}}: {{temperature}} - {{conditionDescription}}",
  "template": "{\"type\":\"Card\",\"theme\":\"dark\",\"size\":\"sm\",\"padding\":{\"y\":8,\"x\":4},\"background\":{{ (background) | tojson }},\"children\":[{\"type\":\"Col\",\"align\":\"center\",\"gap\":2,\"children\":[{\"type\":\"Row\",\"align\":\"center\",\"gap\":2,\"children\":[{\"type\":\"Image\",\"src\":{{ (conditionImage) | tojson }},\"size\":80},{\"type\":\"Title\",\"value\":{{ (temperature) | tojson }},\"size\":\"3xl\",\"weight\":\"normal\",\"color\":\"white\"}]},{\"type\":\"Col\",\"align\":\"center\",\"gap\":4,\"children\":[{\"type\":\"Caption\",\"value\":{{ (location) | tojson }},\"color\":\"white\",\"size\":\"lg\"},{\"type\":\"Text\",\"value\":{{ (conditionDescription) | tojson }},\"color\":\"white\",\"textAlign\":\"center\"}]}]}]}",
  "jsonSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "location": { "type": "string" },
      "background": { "type": "string" },
      "conditionImage": { "type": "string" },
      "conditionDescription": { "type": "string" },
      "temperature": { "type": "string" }
    },
    "required": ["location", "background", "conditionImage", "conditionDescription", "temperature"],
    "additionalProperties": false
  }
}
```

## Simpler YAML Alternative

```yaml
version: "1.0"
name: weather
copy_text: "Weather in {{location}} — {{temperature}}{{unit_symbol}} — {{condition}}"
widget:
  type: Card
  children:
    - type: Text
      value: "Weather in {{location}}"
      weight: semibold
      size: lg
    - type: Text
      value: "{{temperature}}{{unit_symbol}}"
      size: xl
      weight: bold
    - type: Text
      value: "{{condition}}"
      color: secondary
      when: condition
    - type: Text
      value: "Feels like {{feels_like}}{{unit_symbol}}"
      color: secondary
      size: sm
      when: feels_like
    - type: Text
      value: "Humidity: {{humidity}}"
      color: secondary
      size: sm
      when: humidity
    - type: Text
      value: "Wind: {{wind}}"
      color: secondary
      size: sm
      when: wind
```

## Template with Precomputed Children

For complex nested structures, precompute in the server:

```ruby
# In MCP server
def forecast_widget_data(forecast_data)
  forecast_children = forecast_data[:forecast].map do |entry|
    {
      type: "Col",
      align: "center",
      gap: 0,
      children: [
        { type: "Image", src: entry[:icon], size: 40 },
        { type: "Text", value: entry[:temperature] }
      ]
    }
  end

  {
    location: forecast_data[:location],
    forecastChildren: forecast_children  # Pass precomputed array
  }
end
```

Template uses JSON placeholder for array:

```json
{
  "template": "{\"type\":\"Card\",\"children\":[{\"type\":\"Row\",\"children\":{{ (forecastChildren) | tojson }}}]}"
}
```

## Best Practices

1. **Use JSON Schema** - Enforce required fields and catch errors early
2. **JSON-safe placeholders for strings** - Use `{{ (var) | tojson }}` for string values
3. **Simple placeholders for numbers** - Use `{{var}}` for numeric values
4. **Conditional rendering** - Use `when` key for optional fields
5. **Precompute complex structures** - Build nested arrays in server code
6. **Include outputJsonPreview** - Shows expected output for documentation
