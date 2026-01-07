# Block Kit YAML Templates

Templates use `{{placeholder}}` syntax for variable substitution.

## Basic Template

```yaml
# config/ui_widget_templates/slackBlockKitWeatherCurrent.yml
blocks:
  - type: section
    text:
      type: mrkdwn
      text: "*{{location}}*\n{{conditionEmoji}} *{{temperature}}* · {{conditionDescription}}"
    accessory:
      type: image
      image_url: "{{conditionImage}}"
      alt_text: "{{conditionDescription}}"
```

## Block Types

### Header

```yaml
- type: header
  text:
    type: plain_text
    text: "{{title}}"
```

### Section with Fields

```yaml
- type: section
  fields:
    - type: mrkdwn
      text: "*Status:*\n{{status}}"
    - type: mrkdwn
      text: "*Priority:*\n{{priority}}"
```

### Divider

```yaml
- type: divider
```

### Context (Metadata)

```yaml
- type: context
  elements:
    - type: mrkdwn
      text: "Last updated: {{timestamp}}"
```

### Buttons and Actions

```yaml
- type: actions
  elements:
    - type: button
      text:
        type: plain_text
        text: "Approve"
      style: primary
      action_id: "approve"
      value: "{{requestId}}"
    - type: button
      text:
        type: plain_text
        text: "Reject"
      style: danger
      action_id: "reject"
      value: "{{requestId}}"
```

### Section with Button Accessory

```yaml
- type: section
  text:
    type: mrkdwn
    text: "{{message}}"
  accessory:
    type: button
    text:
      type: plain_text
      text: "View Details"
    action_id: "view_details"
    value: "{{entityId}}"
```

## Conditional Rendering

```yaml
blocks:
  - type: section
    text:
      type: mrkdwn
      text: "{{mainContent}}"

  # Only render if 'warningMessage' is present
  - type: section
    when: warningMessage
    text:
      type: mrkdwn
      text: ":warning: {{warningMessage}}"
```

## Using Templates

```ruby
WidgetTemplateService.hydrate_for_tool_result(
  template: :weatherCurrent,
  slack_blocks_template: :slackBlockKitWeatherCurrent,
  data: { location: "Toronto", temperature: "-5°C" },
  text: "Current weather in Toronto"
)
```

## WidgetTemplateService Rendering

```ruby
class WidgetTemplateService
  def self.build_slack_blocks_resource(template:, data:, tool_name:)
    template_config = load_template(template)
    return nil unless template_config

    blocks_payload = render_slack_blocks(template_config, data)
    return nil unless blocks_payload

    instance_id = SecureRandom.uuid
    uri = "#{BaseMCPServer::SLACK_BLOCKS_URI_PREFIX}#{tool_name}/#{instance_id}"

    {
      type: "resource",
      resource: {
        uri: uri,
        mimeType: BaseMCPServer::SLACK_BLOCKS_MIME_TYPE,
        text: blocks_payload.to_json
      }
    }
  end
end
```
