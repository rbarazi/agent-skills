# Testing ChatKit Integration

RSpec patterns for testing ChatKit controller and flows.

## Test Setup

```ruby
RSpec.describe "ChatKit", type: :request do
  let(:account) { create(:account) }
  let(:account_llm) { create(:account_llm, :with_openai, account: account) }
  let(:agent) { create(:agent, account: account, account_llm: account_llm) }
  let(:account_channel) { create(:account_channel, account: account) }
  let(:agent_channel) { create(:web_channel, agent: agent, account_channel: account_channel) }
  let(:user) { create(:user, account: account) }
  let(:session) { create(:session, user: user) }
  let!(:task) { create(:task, agent: agent, agent_channel: agent_channel, user: user) }

  let(:auth_headers) { { "Authorization" => "Bearer #{session.id}", "User-Agent" => "RSpec" } }
end
```

## Thread Creation

```ruby
describe "POST /chatkit (threads.create)" do
  it "creates a task for the agent and streams events" do
    payload = {
      type: "threads.create",
      params: {
        input: {
          content: [{ type: "input_text", text: "Hello ChatKit" }],
          attachments: [],
          inference_options: {}
        }
      }
    }

    expect {
      post "#{chatkit_path}?agent_id=#{agent.id}", params: payload, headers: auth_headers, as: :json
    }.to change { agent.tasks.count }.by(1)

    body = response.body
    expect(body).to include("thread.created")
    expect(body).to include("thread.item.done")
  end
end
```

## Thread Listing

```ruby
describe "POST /chatkit (threads.list)" do
  it "scopes threads to the requested agent" do
    other_agent = create(:agent, account: account, account_llm: account_llm)
    other_channel = create(:web_channel, agent: other_agent, account_channel: account_channel)
    create(:task, agent: other_agent, agent_channel: other_channel, user: user)

    post "#{chatkit_path}?agent_id=#{agent.id}", params: {
      type: "threads.list",
      params: { limit: 50, order: "desc" }
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    ids = JSON.parse(response.body).dig("data").map { |t| t["id"] }
    expect(ids).to include(task.id.to_s)
    expect(ids).not_to include(other_agent.tasks.first.id.to_s)
  end

  it "returns error when agent is missing" do
    post chatkit_path, params: {
      type: "threads.list",
      params: { limit: 50, order: "desc" }
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:unprocessable_content)
  end
end
```

## Message Streaming

```ruby
describe "POST /chatkit (threads.add_user_message)" do
  it "streams user and assistant events" do
    payload = {
      type: "threads.add_user_message",
      params: {
        thread_id: task.id,
        input: {
          content: [{ type: "input_text", text: "Ping" }],
          attachments: [],
          inference_options: {}
        }
      }
    }

    post chatkit_path(agent_id: agent.id), params: payload, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    expect(response.body).to include("thread.item.done")
  end

  it "attaches uploaded blobs to the message" do
    blob = ActiveStorage::Blob.create_and_upload!(
      io: StringIO.new("hello"),
      filename: "hello.txt",
      content_type: "text/plain"
    )
    ChatkitAttachment.create!(blob: blob, account: account, agent: agent, user: user)

    payload = {
      type: "threads.add_user_message",
      params: {
        thread_id: task.id,
        input: {
          content: [{ type: "input_text", text: "Ping" }],
          attachments: [{ id: blob.signed_id, type: "file", name: "hello.txt", mimeType: "text/plain" }],
          inference_options: {}
        }
      }
    }

    post chatkit_path(agent_id: agent.id), params: payload, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    user_message = task.messages.where(role: Message::ROLE_USER).last
    expect(user_message.attachments).to be_attached
  end
end
```

## Widget Testing

```ruby
describe "MCP-UI widget resources" do
  def mcp_widget_metadata(widget:, copy_text:, tool_name: "test_tool")
    widget_payload = { widget: widget, copy_text: copy_text }.to_json
    {
      name: tool_name,
      mcp_content: [
        { type: "text", text: copy_text },
        {
          type: "resource",
          resource: {
            uri: "ui://widgets/#{tool_name}/#{SecureRandom.uuid}",
            mimeType: "application/vnd.ui.widget+json",
            text: widget_payload
          }
        }
      ]
    }
  end

  def weather_widget
    {
      type: "Card",
      children: [
        { type: "Text", value: "Weather in Seattle, WA", weight: "semibold", size: "lg" },
        { type: "Text", value: "55°F", size: "xl", weight: "bold" },
        { type: "Text", value: "Rainy", color: "secondary" }
      ]
    }
  end

  it "serializes MCP tool results with embedded widgets" do
    metadata = mcp_widget_metadata(
      widget: weather_widget,
      copy_text: "Weather in Seattle, WA — 55°F — Rainy",
      tool_name: "get_current_weather"
    )

    task.messages.create!(
      role: Message::ROLE_TOOL_RESULT,
      content: "Weather in Seattle, WA: 55°F, Rainy",
      metadata: metadata
    )

    post chatkit_path, params: {
      agent_id: agent.id,
      type: "threads.get_by_id",
      params: { thread_id: task.id }
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    json = JSON.parse(response.body)
    widget_item = json.dig("items", "data").find { |item| item["type"] == "widget" }
    expect(widget_item).to be_present
    expect(widget_item.dig("widget", "type")).to eq("Card")
    expect(widget_item["copy_text"]).to include("Weather in")
  end

  it "ignores tool results without embedded widget resources" do
    task.messages.create!(
      role: Message::ROLE_TOOL_RESULT,
      content: { result: "some data" }.to_json,
      metadata: { name: "legacy_tool" }
    )

    post chatkit_path, params: {
      agent_id: agent.id,
      type: "threads.get_by_id",
      params: { thread_id: task.id }
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:ok)
    json = JSON.parse(response.body)
    widget_item = json.dig("items", "data").find { |item| item["type"] == "widget" }
    expect(widget_item).to be_nil
  end
end
```

## File Upload Testing

```ruby
describe "POST /chatkit/upload" do
  let(:file) { fixture_file_upload("spec/fixtures/files/sample.txt", "text/plain") }

  it "uploads and registers the attachment for the agent" do
    expect {
      post chatkit_upload_path(agent_id: agent.id), params: { file: file }, headers: auth_headers
    }.to change { ChatkitAttachment.where(agent: agent, account: account).count }.by(1)

    expect(response).to have_http_status(:created)
    json = JSON.parse(response.body)
    expect(json["id"]).to be_present
    expect(json["type"]).to eq("file")
    expect(json["name"]).to eq("sample.txt")
  end

  it "rejects files that exceed the configured limit" do
    allow(ChatkitConfig).to receive(:upload_max_bytes).and_return(1)

    post chatkit_upload_path(agent_id: agent.id), params: { file: file }, headers: auth_headers

    expect(response).to have_http_status(:unprocessable_content)
    expect(JSON.parse(response.body)["error"]).to eq("Attachment too large")
  end
end
```

## Error Handling

```ruby
describe "POST /chatkit error handling" do
  it "returns 404 for non-existent thread" do
    post chatkit_path, params: {
      agent_id: agent.id,
      type: "threads.get_by_id",
      params: { thread_id: 999999 }
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:not_found)
  end

  it "returns 400 for invalid JSON" do
    post chatkit_path(agent_id: agent.id),
         params: "invalid json{",
         headers: auth_headers.merge("Content-Type" => "application/json")

    expect(response).to have_http_status(:bad_request)
  end

  it "returns error for unsupported request type" do
    post chatkit_path(agent_id: agent.id), params: {
      type: "unsupported.type",
      params: {}
    }, headers: auth_headers, as: :json

    expect(response).to have_http_status(:unprocessable_content)
  end
end
```

## Authentication Testing

```ruby
describe "POST /chatkit/client_secret" do
  it "returns a client secret when hosted mode is enabled" do
    allow(ChatkitConfig).to receive_messages(hosted?: true, client_secret: "abc123")

    post chatkit_client_secret_path, params: { current_client_secret: "stale" }, headers: auth_headers

    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to include("client_secret" => "abc123")
  end

  it "requires authentication" do
    allow(ChatkitConfig).to receive_messages(hosted?: true, client_secret: "abc123")

    post chatkit_client_secret_path

    expect(response).to have_http_status(:unauthorized)
  end
end
```
