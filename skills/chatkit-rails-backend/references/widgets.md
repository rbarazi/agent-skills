# Widget Extraction from Tool Results

Extract and render ChatKit widgets from MCP tool results.

## Widget Resource Format

MCP servers embed widgets using this structure in tool results:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Plain text summary for non-UI clients"
    },
    {
      "type": "resource",
      "resource": {
        "uri": "ui://widgets/weatherCurrent/abc123",
        "mimeType": "application/vnd.ui.widget+json",
        "text": "{\"widget\":{...},\"copy_text\":\"...\"}"
      }
    }
  ]
}
```

**Key identifiers:**
- URI prefix: `ui://`
- MIME type: `application/vnd.ui.widget+json`

## Extraction Flow

### 1. Message Role Check

Only extract from tool result messages:

```ruby
def chatkit_items_for_message(task, message)
  case message.role
  when Message::ROLE_USER
    [chatkit_user_item(task, message)].compact
  when Message::ROLE_ASSISTANT
    [chatkit_assistant_item(task, message)].compact
  when Message::ROLE_TOOL_RESULT
    widget_item = embedded_widget_item(task, message)
    widget_item ? [widget_item] : []
  else
    [chatkit_assistant_item(task, message)].compact
  end
end
```

### 2. Extract Widget Resource

```ruby
UI_WIDGET_MIME_TYPE = "application/vnd.ui.widget+json".freeze
UI_RESOURCE_URI_PREFIX = "ui://".freeze

def extract_widget_resource(message)
  metadata = message.metadata
  return unless metadata.is_a?(Hash)

  mcp_content = metadata.with_indifferent_access[:mcp_content]
  return unless mcp_content.is_a?(Array)

  # Find first embedded resource with ui:// URI and widget MIME type
  mcp_content.find do |item|
    item = item.with_indifferent_access if item.is_a?(Hash)
    next unless item[:type] == "resource"

    resource = item[:resource]
    next unless resource.is_a?(Hash)

    resource = resource.with_indifferent_access
    uri = resource[:uri].to_s
    mime_type = resource[:mimeType].to_s

    uri.start_with?(UI_RESOURCE_URI_PREFIX) && mime_type == UI_WIDGET_MIME_TYPE
  end
end
```

### 3. Parse Widget Payload

```ruby
def parse_widget_payload(resource_item)
  resource_item = resource_item.with_indifferent_access if resource_item.is_a?(Hash)
  resource = resource_item[:resource]
  return unless resource.is_a?(Hash)

  resource = resource.with_indifferent_access
  content = resource[:text] || resource[:blob]
  return unless content.present?

  # Decode base64 if blob format
  if resource[:blob].present?
    begin
      content = Base64.decode64(content)
    rescue ArgumentError => e
      Rails.logger.warn("Failed to decode base64 widget blob: #{e.message}")
    end
  end

  # Parse JSON payload
  payload = JSON.parse(content).with_indifferent_access
  { widget: payload[:widget], copy_text: payload[:copy_text] }
rescue JSON::ParserError => e
  Rails.logger.warn("Failed to parse widget payload: #{e.message}")
  nil
end
```

### 4. Build Widget Item

```ruby
def embedded_widget_item(task, message)
  return unless message.role == Message::ROLE_TOOL_RESULT

  widget_resource = extract_widget_resource(message)
  return unless widget_resource

  widget_payload = parse_widget_payload(widget_resource)
  return unless widget_payload

  {
    id: message.id.to_s,
    type: "widget",
    thread_id: task.id.to_s,
    created_at: message.created_at.iso8601,
    copy_text: widget_payload[:copy_text],
    widget: widget_payload[:widget]
  }
end
```

## Widget JSON Structure

The `widget` key contains a ChatKit component tree:

```json
{
  "type": "Card",
  "children": [
    {
      "type": "Text",
      "value": "Weather in Toronto",
      "size": "lg",
      "weight": "semibold"
    },
    {
      "type": "Text",
      "value": "72°F, Sunny"
    }
  ]
}
```

## Storing Widget Metadata

When creating tool result messages, store MCP content in metadata:

```ruby
# In Task model or message creation
def create_tool_result_message(tool_name, result)
  messages.create!(
    role: Message::ROLE_TOOL_RESULT,
    content: result[:content].find { |c| c[:type] == "text" }&.dig(:text) || "",
    metadata: {
      name: tool_name,
      mcp_content: result[:content]  # Store full MCP content array
    }
  )
end
```

## Testing Widget Extraction

```ruby
RSpec.describe "MCP-UI widget resources" do
  def mcp_widget_metadata(widget:, copy_text:, tool_name: "test_tool")
    widget_payload = { widget: widget, copy_text: copy_text }.to_json
    {
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

  it "serializes MCP tool results with embedded widgets" do
    task.messages.create!(
      role: Message::ROLE_TOOL_RESULT,
      content: "Weather data",
      metadata: mcp_widget_metadata(
        widget: { type: "Card", children: [{ type: "Text", value: "72°F" }] },
        copy_text: "Weather: 72°F"
      )
    )

    post chatkit_path, params: {
      agent_id: agent.id,
      type: "threads.get_by_id",
      params: { thread_id: task.id }
    }, headers: auth_headers, as: :json

    json = JSON.parse(response.body)
    widget_item = json.dig("items", "data").find { |item| item["type"] == "widget" }
    expect(widget_item.dig("widget", "type")).to eq("Card")
  end
end
```

## Debugging

1. Check message metadata contains `mcp_content` array
2. Verify resource URI starts with `ui://`
3. Verify MIME type is `application/vnd.ui.widget+json`
4. Parse widget JSON and validate structure
