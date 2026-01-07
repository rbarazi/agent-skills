# Markdown to mrkdwn Conversion

Slack uses "mrkdwn" format, not standard Markdown.

## Key Differences

| Standard Markdown | Slack mrkdwn |
|-------------------|--------------|
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `~~strikethrough~~` | `~strikethrough~` |
| `[text](url)` | `<url\|text>` |
| `# Header` | `*Header*` (bold) |
| `---` | `────────` (unicode) |

## SlackMrkdwnFormatter

```ruby
class SlackMrkdwnFormatter
  class << self
    def format(text)
      return text if text.blank?

      result = text.dup
      result = convert_headers(result)
      result = convert_horizontal_rules(result)
      result = Slack::Messages::Formatting.markdown(result)
      result
    end

    def convert_headers(text)
      text.gsub(/^(\#{1,6})\s+(.+)$/) { "**#{$2.strip}**" }
    end

    def convert_horizontal_rules(text)
      text.gsub(/^[-*_]{3,}$/, "─" * 20)
    end
  end
end
```

## Testing

```ruby
RSpec.describe SlackMrkdwnFormatter do
  describe ".format" do
    it "converts headers to bold" do
      expect(described_class.format("# Title")).to eq("*Title*")
    end

    it "converts links to mrkdwn format" do
      input = "[Click here](https://example.com)"
      expect(described_class.format(input)).to eq("<https://example.com|Click here>")
    end
  end
end
```

## Special Characters

Escape in mrkdwn: `&amp;`, `&lt;`, `&gt;`
