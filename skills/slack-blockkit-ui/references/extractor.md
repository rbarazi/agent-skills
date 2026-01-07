# SlackResourceExtractor

Extracts Block Kit resources from MCP tool result messages.

## Detection and Extraction

```ruby
class SlackResourceExtractor
  class << self
    def has_blocks?(message)
      has_resource?(
        message,
        uri_prefix: BaseMCPServer::SLACK_BLOCKS_URI_PREFIX,
        mime_type: BaseMCPServer::SLACK_BLOCKS_MIME_TYPE
      )
    end

    def extract_blocks(message)
      extract_resource(
        message,
        uri_prefix: BaseMCPServer::SLACK_BLOCKS_URI_PREFIX,
        mime_type: BaseMCPServer::SLACK_BLOCKS_MIME_TYPE
      )
    end

    private

    def has_resource?(message, uri_prefix:, mime_type:)
      mcp_content = message.metadata&.dig("mcp_content")
      return false unless mcp_content.is_a?(Array)

      mcp_content.any? do |item|
        next unless item.is_a?(Hash) && item["type"] == "resource"
        resource = item["resource"]
        next unless resource.is_a?(Hash)

        resource["uri"].to_s.start_with?(uri_prefix) &&
          resource["mimeType"].to_s == mime_type
      end
    end

    def extract_resource(message, uri_prefix:, mime_type:)
      mcp_content = message.metadata&.dig("mcp_content")
      return nil unless mcp_content.is_a?(Array)

      slack_resource = mcp_content.find do |item|
        next unless item.is_a?(Hash) && item["type"] == "resource"
        resource = item["resource"]
        next unless resource.is_a?(Hash)

        resource["uri"].to_s.start_with?(uri_prefix) &&
          resource["mimeType"].to_s == mime_type
      end

      return nil unless slack_resource

      content = slack_resource.dig("resource", "text")
      return nil if content.blank?

      JSON.parse(content).with_indifferent_access
    rescue JSON::ParserError => e
      Rails.logger.error "[SlackResourceExtractor] Parse error: #{e.message}"
      nil
    end
  end
end
```

## Testing

```ruby
RSpec.describe SlackResourceExtractor do
  let(:message) do
    create(:message, metadata: {
      "mcp_content" => [{
        "type" => "resource",
        "resource" => {
          "uri" => "slack://blocks/test/123",
          "mimeType" => "application/vnd.slack.blocks+json",
          "text" => '{"blocks":[{"type":"section"}]}'
        }
      }]
    })
  end

  describe ".has_blocks?" do
    it "detects block kit resources" do
      expect(described_class.has_blocks?(message)).to be true
    end
  end

  describe ".extract_blocks" do
    it "parses blocks JSON" do
      result = described_class.extract_blocks(message)
      expect(result[:blocks]).to be_an(Array)
      expect(result[:blocks].first[:type]).to eq("section")
    end
  end
end
```
