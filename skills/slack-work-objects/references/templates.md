# Work Object YAML Templates

Templates use `{{placeholder}}` syntax for variable substitution.

## Full Template Example

```yaml
# config/ui_widget_templates/slackWeatherCurrent.yml

# Data inputs:
#   - location: "Toronto,CA"
#   - temperature: "-5°C"
#   - conditionDescription: "snow"
#   - conditionImage: "https://openweathermap.org/img/wn/13d@2x.png"
#   - slackTagColor: "blue"
#   - workObjectUrl: "https://app.example.com/work-objects/weather/..."
#   - externalRefId: "weather-current-toronto-ca"
#   - agentName: "Weather Agent"

event_type: weather_report

entity:
  app_unfurl_url: "{{workObjectUrl}}"
  url: "{{workObjectUrl}}"
  external_ref:
    id: "{{externalRefId}}"
    type: weather_current
  entity_type: "slack#/entities/item"
  entity_payload:
    attributes:
      title:
        text: "Weather in {{location}}"
      display_type: Weather
      product_name: "{{agentName}}"
      product_icon:
        url: "{{conditionImage}}"
    custom_fields:
      - key: temperature
        label: Temperature
        value: "{{temperature}}"
        type: string
      - key: condition
        label: Condition
        value: "{{conditionDescription}}"
        type: string
        tag_color: "{{slackTagColor}}"
    display_order:
      - temperature
      - condition
    actions:
      primary_actions:
        - text: Get Forecast
          action_id: weather_get_forecast
          style: primary
          value: "{{location}}"
      overflow_actions:
        - text: View on OpenWeather
          action_id: weather_open_external
          url: "{{openweatherUrl}}"
        - text: Refresh Weather
          action_id: weather_refresh
          value: "{{location}}"
```

## Using Templates

```ruby
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,           # ChatKit widget
  slack_template: :slackWeatherCurrent, # Slack Work Object
  slack_blocks_template: :slackBlockKitWeatherCurrent, # Block Kit
  data: {
    location: "Toronto",
    temperature: "-5°C",
    workObjectUrl: work_object_url,
    externalRefId: generate_external_ref_id("weather-current", "Toronto")
  },
  text: "Current weather in Toronto"
)
```

## Template Location

Templates are stored in `config/ui_widget_templates/`:
- `slackWeatherCurrent.yml` - Work Object template
- `slackBlockKitWeatherCurrent.yml` - Block Kit template
