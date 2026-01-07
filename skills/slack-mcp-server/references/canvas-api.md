# Slack Canvas API

## Full Canvas Server

```ruby
module SlackCanvasMCPServer
  class Server < BaseMCPServer
    server_name "slack_canvas"
    server_version "1.0.0"
    server_instructions <<~INSTRUCTIONS
      MCP Server for creating and managing Slack canvases.
      Canvases are ideal for documentation, meeting notes, and project plans.
    INSTRUCTIONS

    tool :create_canvas
    tool :update_canvas
    tool :get_canvas_sections

    slack_work_object_resource "slack://work-objects/canvas/{canvas_id}",
                               name: "Slack Canvas",
                               description: "A Slack canvas document"

    def initialize(session: nil, config: nil)
      super
    end

    def create_canvas(title:, content:, channel_id: nil)
      with_slack_error_handling do
        client = build_slack_client!

        document_content = JSON.generate({
          type: "markdown",
          markdown: content
        })

        response = if channel_id.present?
          client.conversations_canvases_create(
            channel_id: channel_id,
            document_content: document_content
          )
        else
          client.canvases_create(
            title: title,
            document_content: document_content
          )
        end

        canvas_id = response["canvas_id"]
        share_canvas_with_user(client, canvas_id)

        build_success_result(
          text: "Created canvas '#{title}'",
          canvas_id: canvas_id,
          canvas_url: build_canvas_url(canvas_id)
        )
      end
    end

    def update_canvas(canvas_id:, content: nil, operation: "replace", section_id: nil)
      validate_operation!(operation, section_id)

      with_slack_error_handling do
        client = build_slack_client!
        change = build_change(operation, content, section_id)

        client.canvases_edit(
          canvas_id: canvas_id,
          changes: JSON.generate([change])
        )

        build_success_result(
          text: "Canvas updated: #{operation}",
          canvas_id: canvas_id
        )
      end
    end

    def get_canvas_sections(canvas_id:, criteria: nil)
      with_slack_error_handling do
        client = build_slack_client!

        response = client.canvases_sections_lookup(
          canvas_id: canvas_id,
          criteria: JSON.generate(criteria || { section_types: ["any_header"] })
        )

        build_success_result(
          text: "Found #{response['sections']&.size || 0} section(s)",
          sections: response["sections"]
        )
      end
    end

    private

    VALID_OPERATIONS = %w[replace insert_at_end insert_at_start insert_after insert_before delete].freeze

    def build_slack_client!
      raise "No Slack token" unless config[:slack_token]
      Slack::Web::Client.new(token: config[:slack_token])
    end

    def build_canvas_url(canvas_id)
      "https://app.slack.com/docs/#{config[:team_id]}/#{canvas_id}" if config[:team_id]
    end

    def share_canvas_with_user(client, canvas_id)
      return unless config[:user_slack_id]
      client.canvases_access_set(
        canvas_id: canvas_id,
        access_level: "write",
        user_ids: JSON.generate([config[:user_slack_id]])
      )
    rescue Slack::Web::Api::Errors::SlackError
      # Log but don't fail
    end

    def with_slack_error_handling
      yield
    rescue Slack::Web::Api::Errors::MissingScope => e
      build_error_result("Missing scope: #{e.message}")
    rescue Slack::Web::Api::Errors::SlackError => e
      build_error_result("Slack error: #{e.message}")
    end
  end
end
```

## Gotchas

**JSON encoding**: Complex params must use `JSON.generate`:

```ruby
# WRONG
client.canvases_edit(changes: [{ operation: "replace" }])

# CORRECT
client.canvases_edit(changes: JSON.generate([{ operation: "replace" }]))
```

**Canvas ownership**: Bot tokens own canvases - always share with user.

**Free tier limits**: One channel canvas per channel on free plans.
