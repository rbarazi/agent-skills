# Entity Payload Structure

Work Object entity payloads define how Slack displays the entity.

## Full Structure

```ruby
{
  entity_type: "slack#/entities/item",
  entity_payload: {
    attributes: { ... },
    custom_fields: [ ... ],
    display_order: [ ... ],
    actions: { ... }
  }
}
```

## Attributes

```yaml
attributes:
  title:
    text: "Entity Title"
  display_type: "Type Label"  # Shown as subtitle
  product_name: "App Name"    # Your app's name
  product_icon:
    url: "https://..."        # Icon URL
    alt_text: "Icon description"
```

## Custom Fields

```yaml
custom_fields:
  # String field
  - key: "temperature"
    label: "Temperature"
    value: "-5°C"
    type: "string"
    tag_color: "blue"  # blue, gray, yellow, red, purple

  # Long field (full width)
  - key: "description"
    label: "Description"
    value: "Detailed description here"
    type: "string"
    long: true

  # Timestamp field (Slack renders as relative time)
  - key: "updated_at"
    label: "Last Updated"
    value: 1704067200  # Unix timestamp
    type: "slack#/types/timestamp"
```

## Display Order

```yaml
display_order:
  - temperature
  - condition
  - humidity
  - last_updated
```

## Actions

```yaml
actions:
  primary_actions:
    - text: "Primary Button"
      action_id: "action_primary"
      style: "primary"  # primary or danger
      value: "action_value"

  overflow_actions:
    - text: "External Link"
      action_id: "open_external"
      url: "https://external.com/resource"
    - text: "Refresh"
      action_id: "refresh"
      value: "refresh_value"
```

## Generating Stable External References

```ruby
def generate_external_ref_id(entity_type, identifier)
  # Use parameterize for UTF-8 handling
  # "Québec" → "quebec", "São Paulo" → "sao-paulo"
  normalized = identifier.to_s.parameterize
  "#{entity_type}-#{normalized}"
end

# Examples:
# generate_external_ref_id("weather-current", "Toronto, CA")
# → "weather-current-toronto-ca"
```
