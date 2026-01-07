# BaseMCPServer Integration

Register and implement tools that return ChatKit widgets.

## Server Structure

```ruby
module WeatherMCPServer
  class Server < BaseMCPServer
    # Server metadata
    server_name "weather"
    server_version "1.0.0"
    server_instructions "MCP Server provides tools for weather forecasting."

    # Register widget resource templates
    widget_resource "ui://widgets/weather/{instance_id}",
      name: "Weather Widget",
      description: "Displays current weather information"

    widget_resource "ui://widgets/weatherForecast/{instance_id}",
      name: "Weather Forecast Widget",
      description: "Displays upcoming weather forecast"

    # Register tools
    tool :get_current_weather
    tool :get_weather_forecast

    # Implement tools...
  end
end
```

## Resource Registration

### ChatKit Widgets

```ruby
widget_resource "ui://widgets/{tool_name}/{instance_id}",
  name: "Human-readable name",
  description: "What this widget displays"
```

### Slack Work Objects

```ruby
slack_work_object_resource "slack://work-objects/{tool_name}/{instance_id}",
  name: "Slack Work Object Name",
  description: "Description"
```

### Slack Block Kit

```ruby
slack_blocks_resource "slack://blocks/{tool_name}/{instance_id}",
  name: "Block Kit Name",
  description: "Description"
```

## Tool Implementation

### Basic Widget Tool

```ruby
# Get the current weather in a given location
#
# @param [String] location City and country code (e.g., "Toronto,CA")
# @param [String] unit Temperature unit ("celsius" or "fahrenheit")
# @return [Hash] Weather information with UI widget
def get_current_weather(location:, unit: "celsius")
  # 1. Validate input
  normalized_location = normalize_location(location)
  return error_result("Invalid location format") unless normalized_location

  # 2. Fetch data
  weather_data = openweather_client.current_weather(
    location: normalized_location,
    unit: unit
  )

  # 3. Build plain text for non-UI clients
  text = "Current weather in #{normalized_location}: #{weather_data[:temperature]}#{weather_data[:unit_symbol]}, #{weather_data[:condition]}"

  # 4. Build widget data
  widget_data = {
    location: weather_data[:location],
    temperature: "#{weather_data[:temperature]}#{weather_data[:unit_symbol]}",
    background: condition_style(weather_data[:condition])[:background],
    conditionImage: condition_style(weather_data[:condition])[:icon],
    conditionDescription: weather_data[:condition]
  }

  # 5. Hydrate and return
  WidgetTemplateService.hydrate_for_tool_result(
    template: :weatherCurrent,
    data: widget_data,
    text: text,
    tool_name: "weather"
  )
end
```

### Error Result Helper

```ruby
def error_result(message)
  {
    content: [{ type: "text", text: message }],
    isError: true
  }
end
```

### Multi-Channel Tool

```ruby
def get_current_weather(location:, unit: "celsius")
  weather_data = fetch_weather(location, unit)
  text = format_text(weather_data)

  # Build data for both ChatKit and Slack
  widget_data = weather_widget_data(weather_data)
  slack_data = slack_weather_data(weather_data)

  WidgetTemplateService.hydrate_for_tool_result(
    template: :weatherCurrent,
    slack_blocks_template: :slackBlockKitWeatherCurrent,  # Slack Block Kit
    data: widget_data.merge(slack_data),
    text: text,
    tool_name: "weather"
  )
end
```

## BaseMCPServer Constants

```ruby
class BaseMCPServer
  PROTOCOL_VERSION = "2025-03-26"

  # ChatKit/UI Widget resource format
  UI_WIDGET_MIME_TYPE = "application/vnd.ui.widget+json".freeze
  UI_RESOURCE_URI_PREFIX = "ui://".freeze

  # Slack Work Object resource format
  SLACK_WORK_OBJECT_MIME_TYPE = "application/vnd.slack.work-object+json".freeze
  SLACK_RESOURCE_URI_PREFIX = "slack://work-objects/".freeze

  # Slack Block Kit resource format
  SLACK_BLOCKS_MIME_TYPE = "application/vnd.slack.blocks+json".freeze
  SLACK_BLOCKS_URI_PREFIX = "slack://blocks/".freeze
end
```

## Helper Methods in BaseMCPServer

### Build Widget Result Directly

```ruby
protected

def tool_result_with_widget(text:, widget:, copy_text: nil, tool_name: nil)
  instance_id = SecureRandom.uuid
  tool_identifier = tool_name || self.class.name.demodulize.underscore
  uri = "ui://widgets/#{tool_identifier}/#{instance_id}"

  widget_payload = {
    widget: widget,
    copy_text: copy_text || text
  }

  {
    content: [
      { type: "text", text: text },
      {
        type: "resource",
        resource: {
          uri: uri,
          mimeType: UI_WIDGET_MIME_TYPE,
          text: widget_payload.to_json
        }
      }
    ],
    isError: false
  }
end
```

### UI Component Helpers

```ruby
def ui_card(children:)
  { type: "Card", children: children }
end

def ui_text(value, **options)
  { type: "Text", value: value }.merge(options)
end
```

## Style Management

```ruby
STYLE_PRESETS = {
  clear: {
    background: "linear-gradient(130deg, #F6D365 0%, #FDA085 100%)",
    icon: "https://openweathermap.org/img/wn/01d@2x.png"
  },
  cloudy: {
    background: "linear-gradient(140deg, #536976 0%, #292E49 100%)",
    icon: "https://openweathermap.org/img/wn/03d@2x.png"
  },
  rain: {
    background: "linear-gradient(120deg, #4B79A1 0%, #283E51 100%)",
    icon: "https://openweathermap.org/img/wn/10d@2x.png"
  },
  default: {
    background: "linear-gradient(111deg, #1769C8 0%, #31A3F8 100%)",
    icon: "https://openweathermap.org/img/wn/01d@2x.png"
  }
}.freeze

def condition_style(condition)
  key = case condition.to_s.downcase
  when /thunder|storm/ then :thunder
  when /snow/ then :snow
  when /rain|drizzle/ then :rain
  when /cloud/ then :cloudy
  when /sun|clear/ then :clear
  else :default
  end
  STYLE_PRESETS[key]
end
```

## Configuration Access

```ruby
def openweather_api_key
  config.dig(:env, "OPENWEATHER_API_KEY").presence || ENV["OPENWEATHER_API_KEY"]
end

def openweather_client
  @openweather_client ||= OpenweatherClient.new(api_key: openweather_api_key)
end
```

## Testing Tools

```ruby
RSpec.describe WeatherMCPServer::Server do
  let(:server) { described_class.new(config: { env: { "OPENWEATHER_API_KEY" => "test" } }) }

  describe "#get_current_weather" do
    it "returns widget with weather data" do
      allow_any_instance_of(OpenweatherClient).to receive(:current_weather).and_return({
        location: "Toronto,CA",
        temperature: 72,
        unit_symbol: "°F",
        condition: "Sunny"
      })

      result = server.get_current_weather(location: "Toronto,CA", unit: "fahrenheit")

      expect(result[:isError]).to be false
      expect(result[:content]).to include(hash_including(type: "text"))
      expect(result[:content]).to include(hash_including(type: "resource"))

      resource = result[:content].find { |c| c[:type] == "resource" }
      expect(resource[:resource][:uri]).to start_with("ui://widgets/weather/")
      expect(resource[:resource][:mimeType]).to eq("application/vnd.ui.widget+json")
    end
  end
end
```
