# Human-in-the-Loop Interactions

Handle blocking form interactions via ChatKit custom actions.

## Overview

When an LLM tool requests human input (e.g., `human_request`), ChatKit renders a form widget. Users submit via custom actions, which your controller handles.

## Custom Action Handling

```ruby
def stream_custom_action(req)
  task = task_for(req.dig("params", "thread_id"))
  prepare_stream_headers

  action = req.dig("params", "action") || {}
  action_type = action["type"].to_s
  action_payload = action["payload"] || {}

  write_event(stream_options_event)

  seen_ids = task.messages.pluck(:id)
  submission_result = nil

  if action_type.start_with?("human.")
    begin
      submission_result = HumanInteractionSubmissionService.handle_chatkit_action!(
        task: task,
        action_type: action_type,
        payload: action_payload
      )
    rescue HumanInteractionSubmissionService::Error => e
      unless e.message.include?("not pending")
        task.messages.create!(
          content: "Please complete the form and try again.\n\nError: #{e.message}",
          role: Message::ROLE_SYSTEM
        )
      end
    end
  end

  # Stream tool result if submission created one
  if submission_result&.dig(:tool_result_message)
    tool_result_message = submission_result[:tool_result_message]
    thread_item_done_events(task, tool_result_message).each { |event| write_event(event) }
    seen_ids << tool_result_message.id
  end

  # Stream any new messages
  new_messages = task.messages.with_attached_attachments
                     .where.not(id: seen_ids)
                     .order(created_at: :asc)
  new_messages.each do |message|
    thread_item_done_events(task, message).each { |event| write_event(event) }
  end
rescue StandardError => e
  Rails.logger.error("ChatKit custom_action stream error: #{e.message}")
  write_event(error_event("custom_action_error"))
ensure
  response.stream.close
end
```

## Blocking Messages During Pending Interaction

```ruby
def stream_user_message(req)
  task = task_for(req.dig("params", "thread_id"))
  prepare_stream_headers

  # Block new messages while form is pending
  if task.pending_human_interaction?
    system_message = task.messages.create!(
      content: I18n.t("chatkit.messages.pending_human_interaction"),
      role: Message::ROLE_SYSTEM
    )

    write_event(stream_options_event)
    thread_item_done_events(task, system_message).each { |event| write_event(event) }
    return
  end

  # ... normal message handling
end
```

## Custom Action Types

| Action Type | Description |
|-------------|-------------|
| `human.form_submit` | User submitted form answers |
| `human.best_judgement` | User chose "use your best judgement" |
| `human.cancel` | User cancelled the interaction |

## HumanInteractionSubmissionService

The following is a **simplified, illustrative example** of a service for handling human interaction submissions. The actual implementation in the codebase uses additional features including an `ACTION_TYPE_MAP` for action routing, `interaction_id` handling from payloads, and a more robust `handle_submission!` method. See `app/services/human_interaction_submission_service.rb` for the complete implementation.

```ruby
class HumanInteractionSubmissionService
  class Error < StandardError; end

  class << self
    def handle_chatkit_action!(task:, action_type:, payload:)
      unless task.pending_human_interaction?
        raise Error, "Task is not pending human interaction"
      end

      case action_type
      when "human.form_submit"
        handle_form_submit(task, payload)
      when "human.best_judgement"
        handle_best_judgement(task)
      when "human.cancel"
        handle_cancel(task)
      else
        raise Error, "Unknown action type: #{action_type}"
      end
    end

    private

    def handle_form_submit(task, payload)
      # Validate required fields
      pending_interaction = task.pending_human_interaction
      answers = payload["answers"] || {}

      # Create tool result message with submitted answers
      tool_result_message = task.messages.create!(
        role: Message::ROLE_TOOL_RESULT,
        content: format_answers(answers),
        metadata: {
          name: pending_interaction.tool_name,
          answers: answers,
          submission_type: "form_submit"
        }
      )

      # Mark interaction as resolved
      pending_interaction.update!(resolved_at: Time.current)

      # Continue LLM processing
      task.process_llm_response

      { tool_result_message: tool_result_message }
    end

    def handle_best_judgement(task)
      pending_interaction = task.pending_human_interaction

      tool_result_message = task.messages.create!(
        role: Message::ROLE_TOOL_RESULT,
        content: "User requested: use your best judgement",
        metadata: {
          name: pending_interaction.tool_name,
          submission_type: "best_judgement"
        }
      )

      pending_interaction.update!(resolved_at: Time.current)
      task.process_llm_response

      { tool_result_message: tool_result_message }
    end

    def handle_cancel(task)
      pending_interaction = task.pending_human_interaction

      tool_result_message = task.messages.create!(
        role: Message::ROLE_TOOL_RESULT,
        content: "User cancelled the interaction",
        metadata: {
          name: pending_interaction.tool_name,
          submission_type: "cancel"
        }
      )

      pending_interaction.update!(resolved_at: Time.current, cancelled: true)
      task.process_llm_response

      { tool_result_message: tool_result_message }
    end

    def format_answers(answers)
      answers.map { |k, v| "#{k}: #{v}" }.join("\n")
    end
  end
end
```

## Testing Human Interactions

```ruby
RSpec.describe "POST /chatkit (threads.custom_action)" do
  it "handles human form submission" do
    allow_any_instance_of(Task).to receive(:pending_human_interaction?).and_return(false)

    payload = {
      type: "threads.custom_action",
      params: {
        thread_id: task.id,
        action: {
          type: "human.form_submit",
          payload: { field: "value" }
        }
      }
    }

    post chatkit_path(agent_id: agent.id), params: payload, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
  end

  it "handles errors in custom action" do
    allow(HumanInteractionSubmissionService).to receive(:handle_chatkit_action!)
      .and_raise(HumanInteractionSubmissionService::Error.new("Form invalid"))

    payload = {
      type: "threads.custom_action",
      params: {
        thread_id: task.id,
        action: { type: "human.form_submit", payload: {} }
      }
    }

    post chatkit_path(agent_id: agent.id), params: payload, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    expect(response.body).to include("thread.item.done")
  end
end
```

## I18n

```yaml
en:
  chatkit:
    messages:
      pending_human_interaction: "Please submit the form above before sending more messages."
```
