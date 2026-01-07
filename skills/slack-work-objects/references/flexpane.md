# Flexpane Details

When users click on Work Objects, Slack triggers `entity_details_requested`.

## Controller Handler

```ruby
def handle_entity_details_requested
  event_data = params[:event]
  trigger_id = event_data[:trigger_id]
  external_ref = event_data[:external_ref]

  entity_type = external_ref[:type]
  ref_id = external_ref[:id]
  identifier = extract_identifier_from_ref(ref_id)

  data = fetch_entity_data(entity_type, identifier)

  metadata = SlackWorkObjectFormatter.format_flexpane(
    data,
    entity_type: entity_type,
    external_ref: external_ref
  )

  user_slack_channel.client.entity_presentDetails(
    trigger_id: trigger_id,
    metadata: metadata
  )

  head :ok
rescue Slack::Web::Api::Errors::SlackError => e
  send_error_flexpane(trigger_id, e.message)
end
```

## Error Handling

```ruby
def send_error_flexpane(trigger_id, message:, title: "Error")
  error_payload = {
    status: "custom_partial_view",
    custom_title: title,
    custom_message: message,
    message_format: "markdown"
  }

  user_slack_channel.client.entity_presentDetails(
    trigger_id: trigger_id,
    error: error_payload.to_json  # Must be JSON string
  )
end
```

## Trigger ID Expiry

Flexpane `trigger_id` expires after 3 seconds:

```ruby
rescue Slack::Web::Api::Errors::InvalidTrigger
  Rails.logger.warn "Trigger expired for entity details"
end
```

## Slack App Configuration

Subscribe to `entity_details_requested` bot event in your app settings.
