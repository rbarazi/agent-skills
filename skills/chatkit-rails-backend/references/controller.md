# ChatKit Controller Implementation

Complete controller patterns for ChatKit Rails integration.

## Protocol Events

ChatKit sends JSON requests with a `type` field. Handle each:

| Event | Description | Response |
|-------|-------------|----------|
| `threads.create` | Create thread, stream response | SSE stream |
| `threads.add_user_message` | Add message, stream response | SSE stream |
| `threads.get_by_id` | Get thread with items | JSON |
| `threads.list` | List user's threads | JSON |
| `items.list` | Get messages for thread | JSON |
| `attachments.create` | Prepare file upload | JSON |
| `attachments.delete` | Remove uploaded file | JSON |
| `items.feedback` | Record feedback | JSON `{}` |
| `threads.retry_after_item` | Retry from point | JSON |
| `threads.custom_action` | Custom actions (forms) | SSE stream |

## Complete Entry Point

```ruby
class ChatkitController < ApplicationController
  UI_WIDGET_MIME_TYPE = "application/vnd.ui.widget+json".freeze
  UI_RESOURCE_URI_PREFIX = "ui://".freeze

  include ActionController::Live
  skip_before_action :require_authentication, only: [:entry, :client_secret]
  skip_before_action :verify_authenticity_token, only: [:entry, :client_secret, :upload]
  before_action :authenticate_chatkit_user, only: [:entry, :upload, :client_secret]

  def entry
    req = JSON.parse(request.raw_post.presence || "{}")
    type = req["type"]

    case type
    when "threads.create"
      unless requested_agent
        return render(json: { error: I18n.t("chatkit.errors.agent_required") }, status: :unprocessable_content)
      end
      stream_new_thread(req)
    when "threads.get_by_id"
      render json: thread_response(task_for(req.dig("params", "thread_id")))
    when "threads.list"
      unless requested_agent
        return render(json: { error: I18n.t("chatkit.errors.agent_required") }, status: :unprocessable_content)
      end
      render json: threads_list_response
    when "items.list"
      render json: items_list_response(req.dig("params", "thread_id"))
    when "threads.add_user_message"
      stream_user_message(req)
    when "attachments.create"
      handle_attachment_create(req)
    when "attachments.delete"
      handle_attachment_delete(req)
    when "items.feedback"
      render json: {}
    when "threads.retry_after_item"
      render json: thread_response(task_for(req.dig("params", "thread_id")))
    when "threads.custom_action"
      stream_custom_action(req)
    else
      render json: { error: I18n.t("chatkit.errors.unsupported_request") }, status: :unprocessable_content
    end
  rescue ActiveRecord::RecordNotFound
    render json: { error: I18n.t("chatkit.errors.thread_not_found") }, status: :not_found
  rescue JSON::ParserError
    render json: { error: I18n.t("chatkit.errors.invalid_json") }, status: :bad_request
  end
end
```

## Thread Creation

```ruby
def stream_new_thread(req)
  agent = requested_agent
  prepare_stream_headers

  input = req.dig("params", "input") || {}
  text_content = Array(input["content"]).find { |c| c["type"] == "input_text" }
  content = text_content&.dig("text").to_s
  attachment_ids = attachment_ids_from(input["attachments"])

  task = create_thread(agent, content, attachment_ids)

  # Apply model selection from inference_options
  apply_inference_options(task, input["inference_options"])

  write_event(stream_options_event)
  write_event(thread_created_event(task))

  user_message = task.messages.find_by(role: Message::ROLE_USER)
  thread_item_done_events(task, user_message).each { |event| write_event(event) } if user_message

  seen_ids = task.messages.pluck(:id)
  process_task_with_progress(task, seen_ids)
rescue => e
  Rails.logger.error("ChatKit stream error: #{e.message}\n#{e.backtrace.join("\n")}")
  write_event(error_event("stream_error"))
ensure
  response.stream.close
end

def create_thread(agent, content, attachment_ids = [])
  agent_channel = agent_channel_for(agent)
  task = agent.tasks.create!(
    user: Current.user,
    agent_channel: agent_channel,
    context: content.presence || ""
  )
  if content.present?
    msg = task.messages.create!(content: content, role: Message::ROLE_USER)
    attach_blobs(msg, attachment_ids)
  end
  task
end
```

## Authentication

```ruby
def authenticate_chatkit_user
  session = Session.find_by(id: bearer_session_id || cookie_session_id)
  if session
    Current.session = session
    Current.user = session.user
    Current.account = session.user.account
    return
  end
  render json: { error: "unauthorized" }, status: :unauthorized
end

def bearer_session_id
  auth_header = request.headers["Authorization"].to_s
  return unless auth_header.start_with?("Bearer ")
  auth_header.split(" ", 2).last
end

def cookie_session_id
  cookies.signed[:session_id]
end

def requested_agent
  return @requested_agent if defined?(@requested_agent)
  agent_id = params[:agent_id] || request.query_parameters["agent_id"]
  @requested_agent = Current.account.agents.find_by(id: agent_id) if agent_id.present?
end
```

## Response Formats

### Thread Response

```ruby
def thread_response(task)
  {
    id: task.id.to_s,
    title: task.context.presence || task.agent.name,
    created_at: task.created_at.iso8601,
    status: { type: task.archived? ? "closed" : "active" },
    items: {
      data: thread_items(task),
      has_more: false,
      after: nil
    }
  }
end

def threads_list_response
  scope = Current.account.tasks.where(user: Current.user)
  scope = scope.where(agent: requested_agent) if requested_agent
  threads = scope.order(updated_at: :desc).limit(50)
  {
    data: threads.map { |task| thread_summary(task) },
    has_more: false,
    after: nil
  }
end
```

### Message Serialization

```ruby
def chatkit_user_item(task, message)
  {
    id: message.id.to_s,
    type: "user_message",
    thread_id: task.id.to_s,
    created_at: message.created_at.iso8601,
    content: [{ type: "input_text", text: message.content }],
    attachments: serialized_attachments(message),
    inference_options: {}
  }
end

def chatkit_assistant_item(task, message)
  return if message.role == Message::ROLE_TOOL_CALL || message.role == Message::ROLE_TOOL_RESULT
  {
    id: message.id.to_s,
    type: "assistant_message",
    thread_id: task.id.to_s,
    created_at: message.created_at.iso8601,
    content: [{ type: "output_text", text: message.content, annotations: [] }],
    attachments: serialized_attachments(message)
  }
end
```

## Configuration Model

```ruby
# app/models/chatkit_config.rb
class ChatkitConfig
  DEFAULT_SCRIPT_URL = "https://cdn.platform.openai.com/deployments/chatkit/chatkit.js".freeze

  class << self
    def enabled?
      self_hosted? || hosted?
    end

    def self_hosted?
      api_url.present? && !hosted?
    end

    def hosted?
      client_secret.present?
    end

    def api_url
      ENV.fetch("CHATKIT_API_URL", "/chatkit")
    end

    def domain_key
      ENV.fetch("CHATKIT_PK", ENV.fetch("CHATKIT_DOMAIN_KEY", "local-dev"))
    end

    def client_secret
      ENV["CHATKIT_CLIENT_SECRET"]
    end

    def script_url
      ENV.fetch("CHATKIT_SCRIPT_URL", DEFAULT_SCRIPT_URL)
    end

    def upload_max_bytes
      ENV.fetch("CHATKIT_UPLOAD_MAX_BYTES", 25.megabytes).to_i
    end

    def allowed_mime_types
      ENV.fetch("CHATKIT_ALLOWED_MIME_TYPES", "").split(",").map(&:strip).reject(&:blank?)
    end
  end
end
```

## Routes

```ruby
# config/routes.rb
post "chatkit" => "chatkit#entry", as: :chatkit
post "chatkit/upload" => "chatkit#upload", as: :chatkit_upload
post "chatkit/client_secret", to: "chatkit#client_secret", as: :chatkit_client_secret

resources :agents do
  member do
    get :chatkit
    get :chatkit_standalone
  end
end
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CHATKIT_API_URL` | Backend API URL | `/chatkit` |
| `CHATKIT_CLIENT_SECRET` | OpenAI client secret (hosted mode) | - |
| `CHATKIT_PK` | Domain key | `local-dev` |
| `CHATKIT_SCRIPT_URL` | CDN URL for ChatKit script | OpenAI CDN |
| `CHATKIT_UPLOAD_MAX_BYTES` | Max file upload size | 25MB |
| `CHATKIT_ALLOWED_MIME_TYPES` | Comma-separated allowed types | (all) |
