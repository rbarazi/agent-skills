# Multi-Channel Widget Support

Return widgets for ChatKit and Slack simultaneously.

## Overview

A single tool result can contain multiple embedded resources:
- `ui://` resource for ChatKit
- `slack://blocks/` resource for Slack Block Kit
- `slack://work-objects/` resource for Slack Work Objects

## Usage Pattern

```ruby
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,           # ChatKit UI template
  slack_blocks_template: :slackBlockKitWeatherCurrent,  # Slack Block Kit
  slack_template: :slackWeatherForecast,  # Slack Work Object
  data: widget_data.merge(slack_data),
  text: "Current weather in Toronto: 72°F",
  tool_name: "weather"
)
```

## Result Structure

```ruby
{
  content: [
    { type: "text", text: "..." },
    {
      type: "resource",
      resource: {
        uri: "ui://widgets/weather/abc123",
        mimeType: "application/vnd.ui.widget+json",
        text: "..."
      }
    },
    {
      type: "resource",
      resource: {
        uri: "slack://blocks/weather/def456",
        mimeType: "application/vnd.slack.blocks+json",
        text: "..."
      }
    }
  ],
  isError: false
}
```

## Slack Block Kit Templates

### Template Format (YAML)

```yaml
# config/ui_widget_templates/slackBlockKitWeatherCurrent.yml
version: "1.0"
name: slackBlockKitWeatherCurrent
blocks:
  - type: section
    text:
      type: mrkdwn
      text: "*Weather in {{location}}*"
  - type: section
    fields:
      - type: mrkdwn
        text: "*Temperature:*\n{{temperature}}"
      - type: mrkdwn
        text: "*Condition:*\n{{conditionDescription}}"
  - type: context
    elements:
      - type: mrkdwn
        text: "{{conditionEmoji}} _Updated just now_"
```

### Building Slack Data

```ruby
def slack_weather_current_data(weather_data:)
  {
    slackTagColor: slack_tag_color(weather_data[:condition]),
    conditionEmoji: condition_emoji(weather_data[:condition]),
    # Include any Slack-specific fields
  }
end

def condition_emoji(condition)
  case condition.to_s.downcase
  when /thunder|storm/ then ":zap:"
  when /snow/ then ":snowflake:"
  when /rain|drizzle/ then ":rain_cloud:"
  when /cloud/ then ":cloud:"
  when /sun|clear/ then ":sunny:"
  else ":partly_sunny:"
  end
end
```

## Slack Work Objects

For richer Slack integrations with entities:

### Template Format

```yaml
# config/ui_widget_templates/slackWeatherForecast.yml
version: "1.0"
name: slackWeatherForecast
event_type: weather.forecast
entity:
  type: weather_forecast
  external_ref:
    id: "{{externalRefId}}"
    url: "{{workObjectUrl}}"
  fields:
    location:
      value: "{{location}}"
      type: string
    high_temperature:
      value: "{{highTemperature}}"
      type: string
    low_temperature:
      value: "{{lowTemperature}}"
      type: string
    condition:
      value: "{{conditionDescription}}"
      type: string
  tag:
    text: "{{conditionDescription}}"
    color: "{{slackTagColor}}"
  links:
    openweather:
      url: "{{openweatherUrl}}"
      text: "View on OpenWeather"
```

### Building Work Object Data

```ruby
def slack_weather_forecast_data(forecast_data:)
  location = forecast_data[:location]
  {
    slackTagColor: slack_tag_color(forecast_data[:condition]),
    workObjectUrl: work_object_url("forecast", location),
    openweatherUrl: openweather_url(location),
    externalRefId: external_ref_id("forecast", location),
    agentName: "Weather Agent",
    forecastSummary: build_forecast_summary(forecast_data)
  }
end

# Generate stable external_ref ID for Slack tracking
def external_ref_id(weather_type, location)
  "weather-#{weather_type}-#{location.to_s.parameterize}"
end

def work_object_url(weather_type, location)
  ref_id = external_ref_id(weather_type, location)
  base_url = ENV.fetch("APP_URL", "agentify.rida.me")
  base_url = "https://#{base_url}" unless base_url.start_with?("http")
  "#{base_url}/work-objects/weather/#{ref_id}"
end
```

## MCP Server Registration

```ruby
class WeatherMCPServer::Server < BaseMCPServer
  # ChatKit widgets
  widget_resource "ui://widgets/weather/{instance_id}",
    name: "Weather Widget",
    description: "Displays current weather"

  # Slack Block Kit
  slack_blocks_resource "slack://blocks/weather/{instance_id}",
    name: "Weather Block Kit",
    description: "Displays weather as Slack blocks"

  # Slack Work Objects
  slack_work_object_resource "slack://work-objects/weatherForecast/{instance_id}",
    name: "Weather Forecast Work Object",
    description: "Displays forecast as Slack entity"
end
```

## Complete Multi-Channel Tool

```ruby
def get_current_weather(location:, unit: "celsius")
  weather_data = openweather_client.current_weather(
    location: normalize_location(location),
    unit: unit
  )

  text = "Current weather in #{location}: #{weather_data[:temperature]}#{weather_data[:unit_symbol]}, #{weather_data[:condition]}"

  # ChatKit widget data
  widget_data = {
    location: weather_data[:location],
    temperature: "#{weather_data[:temperature]}#{weather_data[:unit_symbol]}",
    background: condition_style(weather_data[:condition])[:background],
    conditionImage: condition_style(weather_data[:condition])[:icon],
    conditionDescription: weather_data[:condition]
  }

  # Slack-specific data
  slack_data = {
    slackTagColor: slack_tag_color(weather_data[:condition]),
    conditionEmoji: condition_emoji(weather_data[:condition]),
    workObjectUrl: work_object_url("current", weather_data[:location]),
    externalRefId: external_ref_id("current", weather_data[:location])
  }

  # Hydrate both templates
  WidgetTemplateService.hydrate_for_tool_result(
    template: :weatherCurrent,
    slack_blocks_template: :slackBlockKitWeatherCurrent,
    data: widget_data.merge(slack_data),
    text: text,
    tool_name: "weather"
  )
end
```

## MIME Types Reference

| Channel | URI Prefix | MIME Type |
|---------|------------|-----------|
| ChatKit | `ui://` | `application/vnd.ui.widget+json` |
| Slack Block Kit | `slack://blocks/` | `application/vnd.slack.blocks+json` |
| Slack Work Object | `slack://work-objects/` | `application/vnd.slack.work-object+json` |
