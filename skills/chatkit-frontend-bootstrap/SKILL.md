---
name: chatkit-frontend-bootstrap
description: Embed and initialize OpenAI's ChatKit widget in Rails views. Use when adding ChatKit to a page, configuring the openai-chatkit custom element via data attributes, syncing themes with dark/light mode, handling Turbo navigation, or setting up attachment uploads. Triggers on ChatKit embed, openai-chatkit element, chat widget initialization, or theme sync.
---

# ChatKit Frontend Bootstrap

Embed and initialize OpenAI's ChatKit widget in Rails views.

## When to Use

- Embedding ChatKit as a custom `<openai-chatkit>` element
- Configuring ChatKit options (API URL, attachments, theme)
- Theme synchronization with app-wide dark/light mode
- Building both embedded and standalone ChatKit pages

## Quick Start

### 1. Add Bootstrap Partial to Head

```erb
<% content_for :head do %>
  <%= render "shared/chatkit_bootstrap" %>
<% end %>
```

### 2. Create Container with Data Attributes

```erb
<div class="chatkit-shell__frame"
     data-chatkit-api-url-value="<%= chatkit_url %>?agent_id=<%= @agent.id %>"
     data-chatkit-domain-key-value="<%= @chatkit_settings[:domain_key] %>"
     data-chatkit-upload-url-value="<%= chatkit_upload_url(agent_id: @agent.id) %>"
     data-chatkit-upload-max-size-value="<%= ChatkitConfig.upload_max_bytes %>"
     data-chatkit-upload-accept-value="<%= ChatkitConfig.allowed_mime_types.join(',') %>">
</div>
```

### 3. Add Required CSS

```css
.chatkit-shell__frame {
  min-height: 520px;
  height: 100%;
  flex: 1 1 auto;
  display: flex;
}

.chatkit-shell__frame > openai-chatkit {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
}
```

## Key Patterns

### Data Attribute Configuration

The bootstrap JavaScript reads options from container data attributes:

| Attribute | Purpose |
|-----------|---------|
| `data-chatkit-api-url-value` | Backend API endpoint |
| `data-chatkit-domain-key-value` | Domain verification key |
| `data-chatkit-client-secret-path-value` | Endpoint for hosted mode secrets |
| `data-chatkit-upload-url-value` | File upload endpoint |
| `data-chatkit-upload-max-size-value` | Max upload size in bytes |
| `data-chatkit-upload-accept-value` | Allowed MIME types (comma-separated) |
| `data-chatkit-initial-thread-value` | Thread ID to load on init |
| `data-chatkit-header-title-value` | Header title text |

### Theme Sync

ChatKit automatically syncs with `document.documentElement.dataset.theme`:

```javascript
const observer = new MutationObserver((mutations) => {
  if (mutations.some((m) => m.attributeName === "data-theme")) {
    syncTheme()
  }
})
observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] })
```

### Turbo Integration

Works with Turbo by listening to both events:

```javascript
document.addEventListener("turbo:load", applyOptions)
document.addEventListener("DOMContentLoaded", applyOptions)
```

## Reference Files

For detailed implementation patterns, see:

- [embedding.md](references/embedding.md) - View integration patterns
- [initialization.md](references/initialization.md) - JavaScript setup and options
- [theming.md](references/theming.md) - Theme synchronization
- [configuration.md](references/configuration.md) - ChatkitConfig and environment
- [styling.md](references/styling.md) - CSS patterns

## File Locations

| Component | Path |
|-----------|------|
| Bootstrap partial | `app/views/shared/_chatkit_bootstrap.html.erb` |
| Agent ChatKit view | `app/views/agents/chatkit.html.erb` |
| Standalone view | `app/views/agents/chatkit_standalone.html.erb` |
| CSS | `app/assets/stylesheets/components/chatkit.css` |
| Configuration | `app/models/chatkit_config.rb` |

## Two Modes

### Self-Hosted Mode (Default)
ChatKit connects to your Rails backend. No external dependencies.

```ruby
# Environment (optional - uses defaults)
CHATKIT_API_URL="/chatkit"
```

### Hosted Mode (OpenAI Infrastructure)
ChatKit connects to OpenAI servers, requires client secret.

```ruby
# Environment (required)
CHATKIT_CLIENT_SECRET="sk-..."
CHATKIT_PK="your-domain-key"
```

## Example Controller Setup

```ruby
def chatkit
  @chatkit_settings = {
    api_url: "#{chatkit_url}?agent_id=#{@agent.id}",
    domain_key: ChatkitConfig.domain_key,
    upload_url: chatkit_upload_url(agent_id: @agent.id),
    upload_max_bytes: ChatkitConfig.upload_max_bytes,
    allowed_mime_types: ChatkitConfig.allowed_mime_types,
    header_title: @agent.name,
    initial_thread: params[:thread_id]
  }

  if ChatkitConfig.hosted?
    @chatkit_settings[:client_secret_path] = chatkit_client_secret_path
  end
end
```
