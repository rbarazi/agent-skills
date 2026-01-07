# YAML Template System

Templates use `{{placeholder}}` syntax for variable substitution.

## Work Object Template

```yaml
# config/ui_widget_templates/slackWeatherCurrent.yml
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
    custom_fields:
      - key: temperature
        label: Temperature
        value: "{{temperature}}"
        type: string
    actions:
      primary_actions:
        - text: Get Forecast
          action_id: weather_get_forecast
          value: "{{location}}"
```

## Block Kit Template

```yaml
# config/ui_widget_templates/slackBlockKitWeatherCurrent.yml
blocks:
  - type: section
    text:
      type: mrkdwn
      text: "*{{location}}*\n{{conditionEmoji}} *{{temperature}}*"
    accessory:
      type: image
      image_url: "{{conditionImage}}"
      alt_text: "{{conditionDescription}}"
```

## Conditional Rendering

```yaml
blocks:
  - type: section
    text:
      type: mrkdwn
      text: "{{mainContent}}"

  # Only render if 'warningMessage' is present
  - type: section
    when: warningMessage
    text:
      type: mrkdwn
      text: ":warning: {{warningMessage}}"
```

## Using Templates

```ruby
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,           # ChatKit widget
  slack_template: :slackWeatherCurrent, # Slack Work Object
  slack_blocks_template: :slackBlockKitWeatherCurrent, # Block Kit
  data: { location: "Toronto", temperature: "-5°C" },
  text: "Current weather in Toronto"
)
```
