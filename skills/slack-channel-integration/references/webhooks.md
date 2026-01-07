# Slack Webhook Processing

## Controller Setup

```ruby
class Webhooks::SlackController < ApplicationController
  allow_unauthenticated_access only: %i[create interactivity]
  skip_before_action :verify_authenticity_token
  before_action :verify_slack_signature, only: :create

  def create
    # URL verification challenge
    if params["type"] == "url_verification"
      render json: { challenge: params["challenge"] }
      return
    end

    return head :ok if bot_message?
    return head :ok if duplicate_event?

    event = Webhooks::SlackEvent.create!(
      data: request.body.read,
      agent_channel: slack_channel
    )
    event.process!
    head :ok
  end

  private

  def verify_slack_signature
    Slack::Events::Request.new(
      request,
      signing_secret: slack_channel.signing_secret,
      signature_expires_in: 300
    ).verify!
  rescue Slack::Events::Request::TimestampExpired
    head :unauthorized
  end

  def bot_message?
    params.dig(:event, :bot_id).present?
  end

  def duplicate_event?
    Webhooks::SlackEvent.with_team_id_and_ts(
      params[:team_id],
      params.dig(:event, :ts)
    ).exists?
  end
end
```

## SlackEvent Model

```ruby
class Webhooks::SlackEvent < Webhooks::Event
  RECEIVED_REACTION = "eyes"
  PROCESSED_REACTION = "white_check_mark"
  FAILED_REACTION = "x"

  has_one :message, as: :source
  validate :unique_event_id, :unique_message_ts, on: :create

  def process!
    react(RECEIVED_REACTION)

    thread_id = event[:event][:thread_ts] || event[:event][:ts]
    task = agent.tasks.find_or_create_by!(
      name: "slack-#{thread_id}",
      user: team.user
    )

    attachments = download_files(event[:event][:files])
    response = task.process_message(
      content: event[:event][:text],
      attachments: attachments,
      role: Message::ROLE_USER,
      source: self
    )

    send_slack_response(task, response, thread_id)
    react(PROCESSED_REACTION)
  rescue StandardError => e
    react(FAILED_REACTION)
    failed!
  end

  private

  def react(reaction)
    team.client.reactions_add(
      channel: event[:event][:channel],
      timestamp: event[:event][:ts],
      name: reaction
    )
  end

  def send_slack_response(task, response, thread_ts)
    team.client.chat_postMessage(
      channel: event[:event][:channel],
      thread_ts: thread_ts,
      text: SlackMrkdwnFormatter.format(response.content)
    )
  end
end
```

## Duplicate Prevention

```ruby
scope :with_event_id, ->(event_id) {
  where("callback_params->>'event_id' = ?", event_id)
}

scope :with_team_id_and_ts, ->(team_id, ts) {
  where("callback_params->>'team_id' = ?", team_id)
    .where("callback_params->'event'->>'ts' = ?", ts)
}
```

## File Attachments

```ruby
def download_slack_file(slack_file, token)
  uri = URI.parse(slack_file["url_private"])
  request = Net::HTTP::Get.new(uri)
  request["Authorization"] = "Bearer #{token}"

  Net::HTTP.start(uri.hostname, uri.port, use_ssl: true) do |http|
    response = http.request(request)
    File.binwrite(tempfile.path, response.body)
  end
end

def filter_and_download_files(agent, files)
  if agent.account_llm.supports_feature?(:vision, agent.model)
    download_all_files(files)
  else
    download_non_image_files(files)
  end
end
```
