# MCP UI Resources

## Purpose
Return UI resources alongside tool results for rich client rendering in MCP-compatible applications.

## Resource Formats

MCP supports returning structured resources that clients can render as rich UI elements:

### Standard Resource Types

| Type | URI Pattern | MIME Type |
|------|-------------|-----------|
| UI Widgets | `ui://widgets/<tool>/<id>` | `application/vnd.ui.widget+json` |
| Slack Blocks | `slack://blocks/<tool>/<id>` | `application/vnd.slack.blocks+json` |
| Slack Work Objects | `slack://work-objects/<tool>/<id>` | `application/vnd.slack.work-object+json` |
| HTML Fragments | `html://fragments/<tool>/<id>` | `text/html` |
| Markdown | `md://content/<tool>/<id>` | `text/markdown` |

## Tool Result Shape

Return `content` array with mixed types:

```ruby
# app/mcp_servers/dashboard_server.rb
class DashboardServer < BaseMCPServer
  tool :get_metrics do
    description "Get dashboard metrics with visualization"

    execute do |args|
      metrics = MetricsService.fetch(args[:period])

      {
        content: [
          # Text content for LLM consumption
          { type: "text", text: format_metrics_text(metrics) },

          # UI widget for rich rendering
          {
            type: "resource",
            resource: {
              uri: "ui://widgets/dashboard/metrics-#{SecureRandom.hex(4)}",
              mimeType: "application/vnd.ui.widget+json",
              text: build_metrics_widget(metrics).to_json
            }
          }
        ]
      }
    end
  end

  private

  def format_metrics_text(metrics)
    "Revenue: #{metrics[:revenue]}, Users: #{metrics[:users]}"
  end

  def build_metrics_widget(metrics)
    {
      type: "stats_grid",
      items: [
        { label: "Revenue", value: metrics[:revenue], trend: metrics[:revenue_trend] },
        { label: "Active Users", value: metrics[:users], trend: metrics[:users_trend] }
      ]
    }
  end
end
```

## Widget Template System

### Template Storage

Store widget templates in YAML for reusability:

```yaml
# config/ui_widget_templates/stats_card.yml
type: stats_card
version: "1.0"
schema:
  title: { type: string, required: true }
  value: { type: string, required: true }
  subtitle: { type: string }
  trend: { type: string, enum: [up, down, neutral] }
  icon: { type: string }
template:
  component: StatsCard
  props:
    title: "{{title}}"
    value: "{{value}}"
    subtitle: "{{subtitle}}"
    trend: "{{trend}}"
    icon: "{{icon}}"
```

### Template Loader

```ruby
# app/services/ui_widget_template_loader.rb
class UIWidgetTemplateLoader
  TEMPLATES_PATH = Rails.root.join("config/ui_widget_templates")

  def self.load(template_name)
    path = TEMPLATES_PATH.join("#{template_name}.yml")
    raise ArgumentError, "Template not found: #{template_name}" unless path.exist?

    YAML.load_file(path).with_indifferent_access
  end

  def self.render(template_name, variables)
    template = load(template_name)
    hydrate(template[:template], variables)
  end

  private

  def self.hydrate(obj, variables)
    case obj
    when Hash
      obj.transform_values { |v| hydrate(v, variables) }
    when Array
      obj.map { |v| hydrate(v, variables) }
    when String
      obj.gsub(/\{\{(\w+)\}\}/) { variables[$1.to_sym] || variables[$1] || '' }
    else
      obj
    end
  end
end
```

## Slack Block Kit Integration

### Block Kit Resources

```ruby
# app/mcp_servers/slack_server.rb
class SlackServer < BaseMCPServer
  tool :create_task_summary do
    description "Create a task summary with Slack blocks"

    execute do |args|
      task = Task.find(args[:task_id])
      blocks = build_task_blocks(task)

      {
        content: [
          { type: "text", text: "Task: #{task.title}" },
          {
            type: "resource",
            resource: {
              uri: "slack://blocks/task/#{task.id}",
              mimeType: "application/vnd.slack.blocks+json",
              text: { blocks: blocks }.to_json
            }
          }
        ]
      }
    end
  end

  private

  def build_task_blocks(task)
    [
      {
        type: "header",
        text: { type: "plain_text", text: task.title }
      },
      {
        type: "section",
        fields: [
          { type: "mrkdwn", text: "*Status:*\n#{task.status}" },
          { type: "mrkdwn", text: "*Assignee:*\n#{task.assignee&.name || 'Unassigned'}" }
        ]
      },
      {
        type: "actions",
        elements: [
          {
            type: "button",
            text: { type: "plain_text", text: "View Task" },
            url: task_url(task),
            action_id: "view_task_#{task.id}"
          }
        ]
      }
    ]
  end
end
```

### Work Objects

```ruby
# Slack Work Objects for structured data
def build_work_object(entity)
  {
    type: "resource",
    resource: {
      uri: "slack://work-objects/#{entity.class.name.underscore}/#{entity.id}",
      mimeType: "application/vnd.slack.work-object+json",
      text: {
        object_type: entity.class.name.underscore,
        id: entity.id,
        title: entity.title,
        fields: entity_fields(entity),
        actions: entity_actions(entity)
      }.to_json
    }
  }
end
```

## Resource Builder Helper

```ruby
# app/helpers/mcp_resource_helper.rb
module MCPResourceHelper
  def text_content(text)
    { type: "text", text: text }
  end

  def ui_widget(tool_name, id, widget_data)
    {
      type: "resource",
      resource: {
        uri: "ui://widgets/#{tool_name}/#{id}",
        mimeType: "application/vnd.ui.widget+json",
        text: widget_data.to_json
      }
    }
  end

  def slack_blocks(tool_name, id, blocks)
    {
      type: "resource",
      resource: {
        uri: "slack://blocks/#{tool_name}/#{id}",
        mimeType: "application/vnd.slack.blocks+json",
        text: { blocks: blocks }.to_json
      }
    }
  end

  def html_fragment(tool_name, id, html)
    {
      type: "resource",
      resource: {
        uri: "html://fragments/#{tool_name}/#{id}",
        mimeType: "text/html",
        text: html
      }
    }
  end

  def markdown_content(tool_name, id, markdown)
    {
      type: "resource",
      resource: {
        uri: "md://content/#{tool_name}/#{id}",
        mimeType: "text/markdown",
        text: markdown
      }
    }
  end
end
```

## Client-Side Rendering

### Resource Router

```javascript
// app/javascript/controllers/mcp_resource_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  renderResource(resource) {
    const { uri, mimeType, text } = resource
    const data = typeof text === 'string' ? JSON.parse(text) : text

    switch (mimeType) {
      case 'application/vnd.ui.widget+json':
        return this.renderWidget(data)
      case 'application/vnd.slack.blocks+json':
        return this.renderSlackBlocks(data.blocks)
      case 'text/html':
        return this.renderHTML(text)
      case 'text/markdown':
        return this.renderMarkdown(text)
      default:
        console.warn(`Unknown resource type: ${mimeType}`)
        return null
    }
  }

  renderWidget(data) {
    // Dispatch to component registry
    const component = this.widgetRegistry[data.type]
    if (component) {
      return component.render(data)
    }
  }
}
```

## Testing

```ruby
RSpec.describe MCPResourceHelper do
  include MCPResourceHelper

  describe "#ui_widget" do
    it "builds correct resource structure" do
      result = ui_widget("dashboard", "123", { type: "chart", data: [1, 2, 3] })

      expect(result[:type]).to eq("resource")
      expect(result[:resource][:uri]).to eq("ui://widgets/dashboard/123")
      expect(result[:resource][:mimeType]).to eq("application/vnd.ui.widget+json")

      parsed = JSON.parse(result[:resource][:text])
      expect(parsed["type"]).to eq("chart")
    end
  end
end

RSpec.describe UIWidgetTemplateLoader do
  describe ".render" do
    it "hydrates template with variables" do
      allow(described_class).to receive(:load).and_return({
        template: { title: "{{name}}", value: "{{count}}" }
      })

      result = described_class.render("stats_card", { name: "Users", count: "100" })

      expect(result[:title]).to eq("Users")
      expect(result[:value]).to eq("100")
    end
  end
end
```

## Next Steps

- [Testing](10-testing.md) - Comprehensive test strategies
