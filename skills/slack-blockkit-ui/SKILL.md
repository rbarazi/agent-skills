---
name: slack-blockkit-ui
description: Render rich Block Kit messages in Slack from AI agent tool results. Use when building agents that display formatted responses with sections, images, and buttons.
---

# Slack Block Kit UI Responses

Render rich, interactive Block Kit messages in Slack from AI agent tool results.

## Problem Statement

Plain text responses limit how agents can present information. Block Kit enables rich formatting - headers, sections, images, buttons - making agent responses more useful and actionable.

## When to Use

- Displaying structured data (weather, reports, dashboards) in Slack
- Adding interactive buttons to agent responses
- Rendering multi-section content with formatting
- Keywords: block kit, slack blocks, rich messages, interactive messages, slack ui

## Quick Start

```ruby
# MCP tool returns Block Kit as resource
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,
  slack_blocks_template: :slackBlockKitWeatherCurrent,
  data: { location: "Toronto", temperature: "-5°C" },
  text: "Current weather in Toronto"
)
```

## Architecture

```
Tool Call → MCP Server → Tool Result with slack://blocks/ resource
    ↓
SlackResourceExtractor detects blocks
    ↓
SlackTaskResponseService sends chat_postMessage with blocks
```

## Resource Format

```ruby
{
  type: "resource",
  resource: {
    uri: "slack://blocks/weather/uuid",
    mimeType: "application/vnd.slack.blocks+json",
    text: '{ "blocks": [...] }'
  }
}
```

## Key Constants

```ruby
# app/mcp_servers/base_mcp_server.rb
SLACK_BLOCKS_MIME_TYPE = "application/vnd.slack.blocks+json"
SLACK_BLOCKS_URI_PREFIX = "slack://blocks/"
```

## Testing Strategy

```ruby
RSpec.describe SlackResourceExtractor do
  let(:message) { create(:message, metadata: block_kit_metadata) }

  it "detects block kit resources" do
    expect(described_class.has_blocks?(message)).to be true
  end

  it "extracts blocks array" do
    result = described_class.extract_blocks(message)
    expect(result[:blocks]).to be_an(Array)
  end
end
```

## Block Kit Limits

- Maximum 50 blocks per message
- Maximum 3000 characters per text field
- Maximum 10 elements per actions block

## Common Pitfalls

- **Text fallback required**: Always provide `text:` for notifications
- **Text type matters**: Use `mrkdwn` for formatting, `plain_text` for buttons
- **Image URLs**: Must be HTTPS and publicly accessible
- **Action IDs**: Must be unique within the message

## Reference Files

- [extractor.md](references/extractor.md) - SlackResourceExtractor for detecting/extracting blocks
- [response-service.md](references/response-service.md) - SlackTaskResponseService orchestration
- [mrkdwn.md](references/mrkdwn.md) - Markdown to mrkdwn conversion
- [templates.md](references/templates.md) - YAML Block Kit template patterns
- [actions.md](references/actions.md) - Handling button interactions
