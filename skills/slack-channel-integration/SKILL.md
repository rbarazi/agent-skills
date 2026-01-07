---
name: slack-channel-integration
description: Build Slack as a communication channel for AI agents. Use when implementing Slack OAuth, webhooks, event processing, or creating agent-to-Slack messaging pipelines.
---

# Slack Channel Integration

Build Slack as a channel for AI agents - users interact with agents via mentions, DMs, and threads.

## Problem Statement

AI agents need to communicate with users through familiar platforms. Slack provides a natural interface where users can @mention agents, receive responses in threads, and see real-time status through reactions.

## When to Use

- Building a Slack bot that connects to an AI agent backend
- Implementing OAuth v2 flow for Slack workspace installation
- Processing Slack events (mentions, DMs, reactions)
- Mapping Slack threads to agent conversations/tasks
- Keywords: slack bot, slack integration, slack oauth, slack webhooks, agent channel

## Quick Start

```ruby
class SlackChannel < AgentChannel
  include ChannelClient
  include ChannelOAuth

  OAUTH_SCOPES = %w[app_mentions:read chat:write users:read].freeze

  has_many :user_slack_channels, foreign_key: :agent_channel_id
end
```

Process events in `Webhooks::SlackEvent#process!`:

```ruby
def process!
  react("eyes")  # Received
  task = agent.tasks.find_or_create_by!(name: "slack-#{thread_ts}")
  response = task.process_message(content: event[:event][:text])
  send_slack_response(response)
  react("white_check_mark")  # Done
end
```

## Architecture

```
Channel → AccountChannel → AgentChannel → UserAgentChannel
                              ↓
                         SlackChannel
                              ↓
                      UserSlackChannel (OAuth tokens)
```

## Key Patterns

**Reaction-based status**: `eyes` (received) → `white_check_mark` (done) → `x` (failed)

**Thread mapping**: `thread_ts || ts` → Task name for conversation continuity

**Duplicate prevention**: Validate unique `event_id` and `team_id + ts` combination

## Testing Strategy

```ruby
RSpec.describe SlackChannel do
  it "stores OAuth tokens securely" do
    channel = create(:slack_channel)
    expect(channel.access_token).to be_encrypted
  end
end

RSpec.describe "Slack webhooks", type: :request do
  it "verifies signature before processing" do
    post "/webhooks/slack", headers: invalid_signature
    expect(response).to have_http_status(:unauthorized)
  end
end
```

## Common Pitfalls

1. **Signature verification**: Always verify `X-Slack-Signature` before processing
2. **Duplicate events**: Slack may retry - use `event_id` for idempotency
3. **3-second timeout**: Respond quickly, process async if needed

## Reference Files

- [oauth.md](references/oauth.md) - OAuth flow, scopes, and token management
- [webhooks.md](references/webhooks.md) - Event processing and controller setup
- [manifest.md](references/manifest.md) - Slack app manifest generation
- [mrkdwn.md](references/mrkdwn.md) - Markdown to mrkdwn conversion
