# Handling Block Actions

When users interact with buttons in Block Kit messages.

## Controller Handler

```ruby
# app/controllers/webhooks/slack_controller.rb
def handle_block_actions(payload)
  actions = payload["actions"] || []
  trigger_id = payload["trigger_id"]
  team_id = payload.dig("team", "id")

  actions.each do |action|
    action_id = action["action_id"]
    value = action["value"]

    case action_id
    when "weather_get_forecast"
      handle_forecast_request(value)
    when "weather_refresh"
      handle_refresh_request(trigger_id, value)
    when /^custom\./
      handle_custom_action(action_id, value)
    end
  end

  head :ok
end
```

## Action Payload Structure

```ruby
{
  "type" => "block_actions",
  "trigger_id" => "123.456.abc",
  "user" => { "id" => "U123", "name" => "user" },
  "team" => { "id" => "T123" },
  "channel" => { "id" => "C123" },
  "message" => { "ts" => "1234567890.123456" },
  "actions" => [{
    "action_id" => "weather_get_forecast",
    "value" => "Toronto",
    "type" => "button"
  }]
}
```

## Best Practices

**Unique action IDs**: Each button needs a unique `action_id` within the message.

**Namespaced IDs**: Use prefixes like `weather_`, `task_` to categorize actions.

**Stateless values**: Store entity identifiers in `value`, not full state.

**Quick response**: Return `head :ok` immediately, process async if needed.
