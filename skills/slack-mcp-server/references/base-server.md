# BaseMCPServer DSL

## Constants

```ruby
class BaseMCPServer
  PROTOCOL_VERSION = "2025-03-26"

  # Resource MIME types and URI prefixes
  UI_WIDGET_MIME_TYPE = "application/vnd.ui.widget+json"
  UI_RESOURCE_URI_PREFIX = "ui://"

  SLACK_WORK_OBJECT_MIME_TYPE = "application/vnd.slack.work-object+json"
  SLACK_RESOURCE_URI_PREFIX = "slack://work-objects/"

  SLACK_BLOCKS_MIME_TYPE = "application/vnd.slack.blocks+json"
  SLACK_BLOCKS_URI_PREFIX = "slack://blocks/"
end
```

## DSL Methods

```ruby
class << self
  # Register a tool method
  def tool(method_name_sym)
    @tool_method_names ||= []
    @tool_method_names << method_name_sym
  end

  # Server metadata
  def server_name(name)
    @name = name
  end

  def server_version(version)
    @version = version
  end

  def server_instructions(instructions)
    @instructions = instructions
  end

  # Resource templates
  def widget_resource(uri_template, name:, description:)
    @resource_templates ||= []
    @resource_templates << {
      uri_template: uri_template,
      name: name,
      description: description,
      mime_type: UI_WIDGET_MIME_TYPE
    }
  end

  def slack_work_object_resource(uri_template, name:, description:)
    @resource_templates ||= []
    @resource_templates << {
      uri_template: uri_template,
      name: name,
      description: description,
      mime_type: SLACK_WORK_OBJECT_MIME_TYPE
    }
  end

  def slack_blocks_resource(uri_template, name:, description:)
    @resource_templates ||= []
    @resource_templates << {
      uri_template: uri_template,
      name: name,
      description: description,
      mime_type: SLACK_BLOCKS_MIME_TYPE
    }
  end
end
```

## MCP Protocol Methods

```ruby
def call(method:, params: {})
  case method
  when "initialize"      then initialize_session!(params)
  when "ping"            then {}
  when "tools/list"      then list_available_tools
  when "tools/call"      then call_tool(params[:name], **params[:arguments])
  when "resources/list"  then list_resources
  else
    raise "Unsupported method: #{method}"
  end
end
```

## Result Builders

```ruby
def build_success_result(text:, **metadata)
  {
    content: [{ type: "text", text: text }],
    isError: false,
    metadata: metadata
  }
end

def build_error_result(message)
  {
    content: [{ type: "text", text: "Error: #{message}" }],
    isError: true
  }
end
```
