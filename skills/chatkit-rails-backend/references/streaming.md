# SSE Streaming Patterns

Patterns for Server-Sent Events streaming with ChatKit.

## Core Streaming

```ruby
def prepare_stream_headers
  response.headers["Content-Type"] = "text/event-stream"
  response.headers["Cache-Control"] = "no-cache"
end

def write_event(payload)
  response.stream.write("data: #{payload.to_json}\n\n")
end
```

**Critical:** Always close stream in `ensure` block:

```ruby
def stream_user_message(req)
  prepare_stream_headers
  # ... streaming logic
rescue => e
  Rails.logger.error("ChatKit stream error: #{e.message}")
  write_event(error_event("stream_error"))
ensure
  response.stream.close  # ALWAYS close
end
```

## Event Types

### Stream Options (first event)

```ruby
def stream_options_event
  { type: "stream_options", stream_options: { allow_cancel: true } }
end
```

### Thread Created

```ruby
def thread_created_event(task)
  { type: "thread.created", thread: thread_response(task) }
end
```

### Item Done (messages/widgets)

```ruby
def thread_item_done_events(task, message)
  return [] unless message
  chatkit_items_for_message(task, message).map do |item|
    { type: "thread.item.done", item: item }
  end
end
```

### Error

```ruby
def error_event(code)
  { type: "error", code: code, allow_retry: true }
end
```

## Progress Updates

Stream progress during LLM processing:

```ruby
def process_task_with_progress(task, seen_ids)
  stream_progress(:analyzing_request, icon: "sparkle")

  # Set callback for tool progress
  task.progress_callback = ->(tool_name, arguments) {
    stream_tool_progress(tool_name, arguments)
  }

  task.process_llm_response
  stream_progress(:preparing_response, icon: "bolt")

  # Stream new messages
  new_messages = task.messages.with_attached_attachments
                     .where.not(id: seen_ids)
                     .order(created_at: :asc)
  new_messages.each do |message|
    thread_item_done_events(task, message).each { |event| write_event(event) }
  end
end

def stream_progress(key, icon: nil)
  write_event(
    type: "progress_update",
    icon: icon,
    text: I18n.t("chatkit.progress.#{key}")
  )
end
```

## Tool Progress

Display contextual progress for different tools:

```ruby
def stream_tool_progress(tool_name, arguments)
  write_event(
    type: "progress_update",
    icon: tool_progress_icon(tool_name),
    text: tool_progress_text(tool_name, arguments)
  )
end

def tool_progress_text(tool_name, arguments)
  arguments = arguments.with_indifferent_access if arguments.is_a?(Hash)
  case tool_name.to_s
  when "search_resources"
    query = arguments[:query].to_s.truncate(50) if arguments[:query].present?
    query.present? ? "Searching for \"#{query}\"..." : "Searching knowledge base..."
  when "find_quotes"
    query = arguments[:query].to_s.truncate(50) if arguments[:query].present?
    query.present? ? "Finding quotes for \"#{query}\"..." : "Finding relevant quotes..."
  when "remember"
    "Saving to memory..."
  when "recall"
    "Recalling from memory..."
  else
    "Executing #{tool_name.to_s.humanize}..."
  end
end

def tool_progress_icon(tool_name)
  case tool_name.to_s
  when "search_resources", "find_quotes" then "search"
  when "remember", "recall" then "bookmark"
  else "tool"
  end
end
```

## Complete Streaming Flow

```ruby
def stream_user_message(req)
  return render(json: { error: "Agent required" }, status: :unprocessable_content) unless requested_agent

  task = task_for(req.dig("params", "thread_id"))
  prepare_stream_headers

  # Check for pending human interaction
  if task.pending_human_interaction?
    system_message = task.messages.create!(
      content: I18n.t("chatkit.messages.pending_human_interaction"),
      role: Message::ROLE_SYSTEM
    )
    write_event(stream_options_event)
    thread_item_done_events(task, system_message).each { |event| write_event(event) }
    return
  end

  # Parse input
  input = req.dig("params", "input") || {}
  text_content = Array(input["content"]).find { |c| c["type"] == "input_text" }
  content = text_content&.dig("text").to_s
  attachment_ids = attachment_ids_from(req.dig("params", "input", "attachments"))

  # Apply model selection
  apply_inference_options(task, input["inference_options"])

  # Create user message
  user_message = task.messages.create!(content: content, role: Message::ROLE_USER)
  attach_blobs(user_message, attachment_ids)

  # Stream events
  write_event(stream_options_event)
  thread_item_done_events(task, user_message).each { |event| write_event(event) }

  seen_ids = task.messages.pluck(:id)
  process_task_with_progress(task, seen_ids)
rescue => e
  Rails.logger.error("ChatKit stream error: #{e.message}\n#{e.backtrace.join("\n")}")
  write_event(error_event("stream_error"))
ensure
  response.stream.close
end
```

## I18n for Progress Messages

```yaml
# config/locales/chatkit.en.yml
en:
  chatkit:
    progress:
      analyzing_request: "Analyzing your request..."
      preparing_response: "Preparing a response..."
      search_resources: "Searching knowledge base..."
      search_resources_with_query: "Searching for \"%{query}\"..."
      find_quotes: "Finding relevant quotes..."
      find_quotes_with_query: "Finding quotes for \"%{query}\"..."
      remember: "Saving to memory..."
      recall: "Recalling from memory..."
      executing_tool: "Executing %{tool_name}..."
    messages:
      pending_human_interaction: "Please submit the form above before sending more messages."
```
