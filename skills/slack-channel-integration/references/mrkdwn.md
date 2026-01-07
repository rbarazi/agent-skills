# Markdown to mrkdwn Conversion

Slack uses `mrkdwn`, not standard markdown.

## Conversion Table

| Markdown | Slack mrkdwn |
|----------|--------------|
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `~~strike~~` | `~strike~` |
| `[text](url)` | `<url\|text>` |
| `# Header` | `*Header*` (bold) |
| `---` | `────────` (unicode) |

## Formatter

```ruby
class SlackMrkdwnFormatter
  class << self
    def format(text)
      return text if text.blank?

      result = text.dup
      result = convert_headers(result)
      result = convert_horizontal_rules(result)
      Slack::Messages::Formatting.markdown(result)
    end

    def convert_headers(text)
      text.gsub(/^(\#{1,6})\s+(.+)$/) { "**#{$2.strip}**" }
    end

    def convert_horizontal_rules(text)
      text.gsub(/^[-*_]{3,}$/, "─" * 20)
    end

    def format_work_object_links(work_objects, default_title: "View Details")
      work_objects.filter_map do |wo|
        entity = wo[:entity]
        url = entity[:url]
        next unless url

        title = entity.dig(:entity_payload, :attributes, :title, :text) || default_title
        "<#{url}|#{title}>"
      end
    end
  end
end
```

## Usage

```ruby
# In SlackEvent response
team.client.chat_postMessage(
  channel: channel_id,
  thread_ts: thread_ts,
  text: SlackMrkdwnFormatter.format(response.content)
)
```
