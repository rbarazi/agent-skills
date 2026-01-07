---
name: chatkit-rails-backend
description: Integrate OpenAI ChatKit with a Rails backend using SSE streaming. Use when building conversational AI with thread management, message streaming, widget rendering from MCP tool results, file attachments, and human-in-the-loop form interactions. Triggers on ChatKit, chat widget, thread streaming, or widget from tool result.
---

# ChatKit Rails Backend Integration

Integrate OpenAI's ChatKit JavaScript widget with your Rails backend using Server-Sent Events (SSE).

## Quick Start

ChatKit communicates via JSON requests to your Rails controller. The core flow:

```
User → ChatKit.js → Rails Controller (SSE) → Task/LLM → Tools → Stream Response
```

**Required components:**
1. `ChatkitController` - Handles protocol requests via SSE
2. `ChatkitConfig` - Environment-driven configuration model
3. `ChatkitAttachment` - Tracks uploaded files per account/agent

## Core Controller Pattern

```ruby
class ChatkitController < ApplicationController
  include ActionController::Live  # Required for SSE

  def entry
    req = JSON.parse(request.raw_post.presence || "{}")
    case req["type"]
    when "threads.create"       then stream_new_thread(req)
    when "threads.add_user_message" then stream_user_message(req)
    when "threads.get_by_id"    then render json: thread_response(task)
    when "threads.list"         then render json: threads_list_response
    # ... handle other events
    end
  end
end
```

## SSE Streaming

```ruby
def prepare_stream_headers
  response.headers["Content-Type"] = "text/event-stream"
  response.headers["Cache-Control"] = "no-cache"
end

def write_event(payload)
  response.stream.write("data: #{payload.to_json}\n\n")
end
# Always close stream in ensure block
```

## Widget Extraction from Tool Results

Extract widgets from MCP tool results containing `ui://` resources:

```ruby
def embedded_widget_item(task, message)
  return unless message.role == Message::ROLE_TOOL_RESULT
  widget_resource = extract_widget_resource(message)
  widget_payload = parse_widget_payload(widget_resource)
  { type: "widget", widget: widget_payload[:widget], copy_text: widget_payload[:copy_text] }
end
```

**Key detection:** URI starts with `ui://` + MIME type `application/vnd.ui.widget+json`

## Reference Files

**For detailed patterns, see:**
- [controller.md](references/controller.md) - Complete controller implementation
- [streaming.md](references/streaming.md) - SSE streaming and progress updates
- [widgets.md](references/widgets.md) - Widget extraction from tool results
- [attachments.md](references/attachments.md) - File upload handling
- [human-interaction.md](references/human-interaction.md) - Form-based human-in-the-loop
- [testing.md](references/testing.md) - RSpec testing patterns
