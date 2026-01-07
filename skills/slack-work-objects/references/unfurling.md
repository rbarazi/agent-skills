# Link Unfurling

When Work Object URLs are shared, Slack triggers `link_shared` events.

## Controller Handler

```ruby
def handle_link_shared
  event_data = params[:event]
  links = event_data[:links] || []
  unfurl_id = event_data[:unfurl_id]
  source = event_data[:source]

  unfurls = {}
  links.each do |link|
    url = link[:url]
    next unless work_object_url?(url)

    entity_type, identifier = parse_work_object_url(url)
    next unless entity_type

    data = fetch_entity_data(entity_type, identifier)
    unfurls[url] = build_unfurl_content(data)
  end

  return head :ok if unfurls.empty?

  metadata = build_link_unfurl_metadata(unfurls)

  user_slack_channel.client.chat_unfurl(
    unfurl_id: unfurl_id,
    source: source,
    metadata: metadata
  )
end
```

## Building Unfurl Metadata

```ruby
def build_link_unfurl_metadata(unfurls)
  entities = unfurls.map do |url, _content|
    entity_type, identifier = parse_work_object_url(url)
    data = fetch_entity_data(entity_type, identifier)

    {
      app_unfurl_url: url,
      url: url,
      external_ref: {
        id: generate_external_ref_id(entity_type, identifier),
        type: entity_type
      },
      entity_type: "slack#/entities/item",
      entity_payload: build_entity_payload(data)
    }
  end.compact

  { entities: entities }
end
```

## Important: Flat Metadata Structure

Work Objects use flat metadata, not nested event_type/event_payload:

```ruby
# CORRECT for link unfurling
{ entities: [{ entity_type: "...", entity_payload: {...} }] }

# WRONG (old documentation format)
{ event_type: "...", event_payload: {...} }
```

## URL Must Match

The `url` and `app_unfurl_url` must match the URLs you're unfurling:

```ruby
entity = {
  url: original_url,          # Must match
  app_unfurl_url: original_url,  # Must match
  external_ref: {...},
  entity_type: "slack#/entities/item",
  entity_payload: {...}
}
```

## Slack App Configuration

1. Enable Work Object Previews in your app settings
2. Subscribe to `link_shared` bot event
3. Register URL patterns for unfurling (e.g., `https://yourapp.com/work-objects/*`)
