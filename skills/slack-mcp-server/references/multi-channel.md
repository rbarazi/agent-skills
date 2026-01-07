# Multi-Channel Tool Results

Return resources for multiple clients (web + Slack) from single tool call.

## Result Structure

```ruby
{
  content: [
    { type: "text", text: "Current weather..." },
    {
      type: "resource",
      resource: {
        uri: "ui://widgets/weather/uuid",
        mimeType: "application/vnd.ui.widget+json",
        text: "{ widget: {...} }"
      }
    },
    {
      type: "resource",
      resource: {
        uri: "slack://work-objects/weather/uuid",
        mimeType: "application/vnd.slack.work-object+json",
        text: "{ entity: {...} }"
      }
    },
    {
      type: "resource",
      resource: {
        uri: "slack://blocks/weather/uuid",
        mimeType: "application/vnd.slack.blocks+json",
        text: "{ blocks: [...] }"
      }
    }
  ],
  isError: false
}
```

## Implementation

```ruby
def get_current_weather(location:, unit: "celsius")
  weather_data = fetch_weather(location, unit)

  widget_data = {
    location: weather_data[:location],
    temperature: "#{weather_data[:temperature]}#{unit_symbol}"
  }

  slack_data = {
    slackTagColor: condition_color(weather_data[:condition]),
    workObjectUrl: work_object_url(weather_data),
    externalRefId: generate_ref_id(weather_data)
  }

  WidgetTemplateService.hydrate_for_tool_result(
    template: :weatherCurrent,
    slack_template: :slackWeatherCurrent,
    slack_blocks_template: :slackBlockKitWeatherCurrent,
    data: widget_data.merge(slack_data),
    text: "Weather in #{location}: #{weather_data[:temperature]}"
  )
end
```

## WidgetTemplateService

```ruby
class WidgetTemplateService
  def self.hydrate_for_tool_result(template:, data:, text:, slack_template: nil, slack_blocks_template: nil)
    result = build_tool_result(template, data, text)

    if slack_template
      slack_resource = build_slack_resource(slack_template, data)
      result[:content] << slack_resource if slack_resource
    end

    if slack_blocks_template
      blocks_resource = build_slack_blocks_resource(slack_blocks_template, data)
      result[:content] << blocks_resource if blocks_resource
    end

    result
  end
end
```

## Resource Extraction

Channels extract their specific resources by URI prefix:

```ruby
# Web client extracts ui://
resource = mcp_content.find { |r| r["resource"]["uri"].start_with?("ui://") }

# Slack extracts slack://work-objects/
resource = mcp_content.find { |r| r["resource"]["uri"].start_with?("slack://work-objects/") }
```
