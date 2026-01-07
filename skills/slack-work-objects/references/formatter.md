# SlackWorkObjectFormatter

Formats Work Object data for flexpane display.

## Implementation

```ruby
class SlackWorkObjectFormatter
  ENTITY_TYPE_ITEM = "slack#/entities/item"

  TAG_COLORS = {
    clear: "yellow",
    cloudy: "gray",
    rain: "blue",
    snow: "blue",
    thunder: "red",
    default: "blue"
  }.freeze

  class << self
    def format_weather_flexpane(weather_data, weather_type:, agent_name:, external_ref: nil)
      base_metadata = weather_type == :forecast ?
        format_forecast_flexpane(weather_data, agent_name) :
        format_current_flexpane(weather_data, agent_name)

      base_metadata[:url] = work_object_url(weather_type, weather_data[:location])

      if external_ref
        base_metadata[:external_ref] = {
          id: external_ref[:id],
          type: external_ref[:type]
        }.compact
      end

      base_metadata
    end

    private

    def format_current_flexpane(data, agent_name)
      {
        entity_type: ENTITY_TYPE_ITEM,
        entity_payload: {
          attributes: {
            title: { text: "Weather in #{data[:location]}" },
            display_type: "Current Weather",
            product_name: agent_name,
            product_icon: {
              url: condition_icon_url(data[:condition]),
              alt_text: data[:condition]
            }
          },
          custom_fields: [
            {
              key: "temperature",
              label: "Temperature",
              value: "#{data[:temperature]}#{data[:unit_symbol]}",
              type: "string",
              long: true
            },
            {
              key: "condition",
              label: "Condition",
              value: data[:condition],
              type: "string",
              tag_color: condition_tag_color(data[:condition])
            },
            {
              key: "last_updated",
              label: "Last Updated",
              value: Time.current.to_i,
              type: "slack#/types/timestamp"
            }
          ].compact,
          display_order: %w[temperature condition last_updated],
          actions: weather_actions(data[:location])
        }
      }
    end

    def weather_actions(location)
      {
        primary_actions: [
          {
            text: "Get Forecast",
            action_id: "weather_get_forecast",
            style: "primary",
            value: location
          }
        ],
        overflow_actions: [
          {
            text: "View on OpenWeather",
            action_id: "weather_open_external",
            url: openweather_url(location)
          },
          {
            text: "Refresh Weather",
            action_id: "weather_refresh",
            value: location
          }
        ]
      }
    end
  end
end
```

## Testing

```ruby
RSpec.describe SlackWorkObjectFormatter do
  describe ".format_weather_flexpane" do
    let(:weather_data) do
      {
        location: "Toronto, CA",
        temperature: -5,
        unit_symbol: "°C",
        condition: "Snow"
      }
    end

    it "returns proper entity structure" do
      result = described_class.format_weather_flexpane(
        weather_data,
        weather_type: :current,
        agent_name: "Weather Agent"
      )

      expect(result[:entity_type]).to eq("slack#/entities/item")
      expect(result[:entity_payload][:attributes][:title][:text]).to include("Toronto")
    end

    it "includes external_ref when provided" do
      result = described_class.format_weather_flexpane(
        weather_data,
        weather_type: :current,
        agent_name: "Weather Agent",
        external_ref: { id: "weather-current-toronto-ca", type: "weather_current" }
      )

      expect(result[:external_ref][:id]).to eq("weather-current-toronto-ca")
    end
  end
end
```
