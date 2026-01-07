# Slack App Manifest Generation

Generate a manifest for easy Slack app creation:

```ruby
def to_slack_manifest_json
  bot_events = [
    "app_mention",
    "message.channels",
    "message.im",
    "reaction_added"
  ]

  if assistant_enabled?
    bot_events += ["assistant_thread_started", "assistant_thread_context_changed"]
  end

  {
    display_information: {
      name: agent.name,
      description: agent.persona,
      background_color: "#000000"
    },
    features: {
      bot_user: {
        display_name: agent.username,
        always_online: true
      }
    },
    oauth_config: {
      redirect_urls: ["https://#{APP_URL}/agents/#{agent.username}/slack_oauth"],
      scopes: { bot: oauth_scopes }
    },
    settings: {
      event_subscriptions: {
        request_url: "https://#{APP_URL}/webhooks/slack/#{agent.username}",
        bot_events: bot_events
      },
      interactivity: {
        is_enabled: true,
        request_url: "https://#{APP_URL}/webhooks/slack/interactivity"
      }
    }
  }
end
```

## Common Bot Events

| Event | Purpose |
|-------|---------|
| `app_mention` | Bot was @mentioned |
| `message.channels` | Message in public channel |
| `message.im` | Direct message |
| `message.groups` | Private channel message |
| `reaction_added` | Emoji reaction added |
| `assistant_thread_started` | Slack Assistant thread opened |
| `entity_details_requested` | Work Object flexpane clicked |
| `link_shared` | URL unfurling request |

## Gotchas

- Username max length: 21 characters
- Signature expires in 300 seconds
- Always check `bot_id` to prevent loops
