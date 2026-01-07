---
name: slack-mcp-server
description: Create MCP servers that interact with Slack APIs. Use when building agent tools for Slack canvases, posting messages, or other Slack operations via Model Context Protocol.
---

# Slack MCP Server Tools

Build MCP servers that enable AI agents to interact with Slack APIs.

## Problem Statement

AI agents need to perform actions in Slack beyond just sending messages - creating canvases, managing channels, posting rich content. MCP servers provide a standardized way to expose these capabilities as tools.

## When to Use

- Building agent tools that create/update Slack canvases
- Exposing Slack API operations as MCP tools
- Returning rich resources (Block Kit, Work Objects) from tool calls
- Keywords: mcp server, slack tools, slack canvas, agent tools, model context protocol

## Quick Start

```ruby
module SlackCanvasMCPServer
  class Server < BaseMCPServer
    server_name "slack_canvas"
    server_version "1.0.0"

    tool :create_canvas
    tool :update_canvas

    def create_canvas(title:, content:, channel_id: nil)
      client = Slack::Web::Client.new(token: config[:slack_token])

      response = client.canvases_create(
        title: title,
        document_content: JSON.generate({ type: "markdown", markdown: content })
      )

      build_success_result(
        text: "Created canvas '#{title}'",
        canvas_id: response["canvas_id"]
      )
    end
  end
end
```

## Architecture

```
Agent → Task → LLM → Tool Call → MCP Server → Slack API
                                      ↓
                              Tool Result with Resources
```

## Key Patterns

**Tool registration**: Use `tool :method_name` DSL

**Config injection**: Credentials via `config[:slack_token]`, `config[:team_id]`

**Multi-channel results**: Return `ui://` + `slack://` resources for different clients

## Testing Strategy

```ruby
RSpec.describe SlackCanvasMCPServer::Server do
  let(:server) { described_class.new(config: { slack_token: "xoxb-test" }) }

  it "creates canvas with valid content" do
    stub_slack_api(:canvases_create).to_return(canvas_id: "C123")

    result = server.create_canvas(title: "Test", content: "# Hello")

    expect(result[:canvas_id]).to eq("C123")
  end
end
```

## Common Pitfalls

1. **Token scopes**: Ensure bot token has required scopes (canvases:write, etc.)
2. **Rate limits**: Handle Slack API rate limiting gracefully
3. **Content format**: Canvas content must be valid markdown or document JSON

## Reference Files

- [base-server.md](references/base-server.md) - BaseMCPServer DSL and constants
- [canvas-api.md](references/canvas-api.md) - Canvas create/update/sections operations
- [templates.md](references/templates.md) - YAML template system for resources
- [multi-channel.md](references/multi-channel.md) - Returning resources for multiple channels
