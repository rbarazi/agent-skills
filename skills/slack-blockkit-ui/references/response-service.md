# SlackTaskResponseService

Orchestrates Slack response delivery, combining Block Kit with text.

## Core Logic

```ruby
class SlackTaskResponseService
  def self.call(user_slack_channel:, channel_id:, thread_ts:, task:, response_message:, after:)
    new(...).call
  end

  def call
    tool_result_messages = task.messages
      .where(role: Message::ROLE_TOOL_RESULT)
      .where("created_at >= ?", after)
      .order(created_at: :asc)

    blocks = extract_slack_blocks_from_messages(tool_result_messages)
    work_objects = extract_slack_work_objects_from_messages(tool_result_messages)
    text = response_message&.content.to_s.presence || "Done."

    if blocks && work_objects.present?
      send_combined_message(blocks, work_objects, text)
    elsif work_objects.present?
      send_work_objects_message(work_objects, text)
    elsif blocks
      send_blocks_message(blocks, text)
    else
      send_plain_text_message(text)
    end
  end

  private

  def extract_slack_blocks_from_messages(messages)
    block_sets = messages.filter_map do |msg|
      next unless SlackResourceExtractor.has_blocks?(msg)
      SlackResourceExtractor.extract_blocks(msg)&.dig(:blocks)
    end

    return nil if block_sets.empty?

    # Combine multiple block sets with dividers
    block_sets.each_with_index.flat_map do |blocks, index|
      index < block_sets.length - 1 ? blocks + [{ type: "divider" }] : blocks
    end.presence
  end

  def send_blocks_message(blocks, text)
    blocks_with_intro = prepend_llm_intro(blocks, text)

    user_slack_channel.client.chat_postMessage(
      channel: channel_id,
      thread_ts: thread_ts,
      text: text,  # Fallback for notifications
      blocks: blocks_with_intro,
      unfurl_links: false,
      unfurl_media: false
    )
  rescue Slack::Web::Api::Errors::SlackError => e
    Rails.logger.warn "[Block Kit Fallback] #{e.message}"
    send_plain_text_message(text)
  end

  def prepend_llm_intro(blocks, llm_response)
    return blocks if llm_response.blank?
    return blocks if llm_response.length < 20

    intro_block = {
      type: "section",
      text: {
        type: "mrkdwn",
        text: SlackMrkdwnFormatter.format(llm_response)
      }
    }

    [intro_block] + blocks
  end
end
```

## Key Patterns

**Combine multiple tool results**: Multiple Block Kit resources are joined with dividers.

**Prepend LLM intro**: LLM's text response is added as intro section before blocks.

**Graceful fallback**: On Block Kit errors, falls back to plain text.
