---
name: slack-work-objects
description: Create trackable Work Objects in Slack with link unfurling and flexpane details. Use when building agents that need persistent, interactive entities.
---

# Slack Work Objects

Create trackable, interactive Work Objects in Slack that persist across conversations.

## Problem Statement

Agents often create entities (reports, tasks, documents) that users need to track and interact with later. Work Objects provide persistent, unfurlable links with expandable details panels.

## When to Use

- Creating persistent entities users can reference across conversations
- Building links that unfurl with rich previews
- Providing expandable detail panels (flexpane) for entities
- Keywords: work objects, link unfurling, flexpane, slack entities, persistent objects

## Quick Start

```ruby
# MCP tool returns Work Object as resource
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,
  slack_template: :slackWeatherCurrent,
  data: {
    location: "Toronto",
    workObjectUrl: "https://app.example.com/work-objects/weather/toronto",
    externalRefId: "weather-current-toronto-ca"
  },
  text: "Current weather in Toronto"
)
```

## What Are Work Objects?

- **Link Unfurling**: Rich previews when URLs are shared
- **Flexpane Details**: Expanded view when clicked
- **Cross-Conversation Tracking**: Same entity recognized everywhere
- **Actions**: Buttons for common operations

## Architecture

```
MCP Tool Result → slack://work-objects/ resource
    ↓
Message posted with Work Object URLs
    ↓
Slack triggers link_shared event → App responds with chat.unfurl
    ↓
User clicks → entity_details_requested → App shows flexpane
```

## Resource Format

```ruby
{
  type: "resource",
  resource: {
    uri: "slack://work-objects/weather/uuid",
    mimeType: "application/vnd.slack.work-object+json",
    text: JSON.generate({
      event_type: "weather_report",
      entity: {
        url: "https://app.example.com/work-objects/...",
        external_ref: { id: "weather-current-toronto", type: "weather_current" },
        entity_type: "slack#/entities/item",
        entity_payload: { ... }
      }
    })
  }
}
```

## Testing Strategy

```ruby
RSpec.describe SlackWorkObjectFormatter do
  it "formats entity with required fields" do
    result = described_class.format_weather_flexpane(data, weather_type: :current)

    expect(result[:entity_type]).to eq("slack#/entities/item")
    expect(result[:entity_payload][:attributes]).to be_present
  end
end

RSpec.describe "link_shared webhook", type: :request do
  it "unfurls work object URLs" do
    post "/webhooks/slack", params: link_shared_event
    expect(slack_client).to have_received(:chat_unfurl)
  end
end
```

## Common Pitfalls

- **Stable external_ref IDs**: Use location-based, not timestamp-based
- **URL must match**: `url` and `app_unfurl_url` must match unfurled URLs
- **Trigger expiry**: Flexpane `trigger_id` expires after 3 seconds
- **UTF-8 handling**: Use `parameterize` for special characters

## Reference Files

- [entity-format.md](references/entity-format.md) - Entity payload structure
- [unfurling.md](references/unfurling.md) - Handling link_shared events
- [flexpane.md](references/flexpane.md) - Handling entity_details_requested
- [formatter.md](references/formatter.md) - SlackWorkObjectFormatter
- [templates.md](references/templates.md) - YAML Work Object templates
