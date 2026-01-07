# Embedding ChatKit in Views

Patterns for integrating ChatKit into Rails views.

## Embedded View (Within App Layout)

For ChatKit embedded within the application layout:

```erb
<%# app/views/agents/chatkit.html.erb %>
<% content_for :title, t("agents.chatkit.title", agent: @agent.name) %>

<% content_for :head do %>
  <%= render "shared/chatkit_bootstrap" %>
<% end %>

<%= render "shared/page_header",
           title: t("agents.chatkit.header_title", agent: @agent.name),
           back_path: agents_path,
           back_label: t("agents.chatkit.back_to_agents"),
           actions: link_to(t("agents.chatkit.view_tasks"), tasks_path, class: "button button--ghost button--sm") %>

<div class="chatkit-page">
  <div class="chatkit-shell">
    <% if ChatkitConfig.enabled? %>
      <% chatkit_data = {
           chatkit_header_title_value: @chatkit_settings[:header_title],
           chatkit_upload_url_value: chatkit_upload_url(agent_id: @agent.id),
           chatkit_upload_max_size_value: ChatkitConfig.upload_max_bytes,
           chatkit_upload_accept_value: ChatkitConfig.allowed_mime_types.join(",")
         } %>
      <% chatkit_data[:chatkit_api_url_value] = "#{chatkit_url}?agent_id=#{@agent.id}" %>
      <% chatkit_data[:chatkit_domain_key_value] = @chatkit_settings[:domain_key] %>
      <% chatkit_data[:chatkit_client_secret_path_value] = @chatkit_settings[:client_secret_path] if @chatkit_settings[:client_secret_path].present? %>
      <% chatkit_data[:chatkit_initial_thread_value] = @chatkit_settings[:initial_thread] if @chatkit_settings[:initial_thread].present? %>

      <%= content_tag :div, class: "chatkit-shell__frame", data: chatkit_data do %>
        <div class="chatkit-shell__error" role="alert" hidden></div>
      <% end %>
    <% else %>
      <div class="chatkit-shell__empty">
        <p><%= t("tasks.chatkit.missing_config") %></p>
        <p class="chatkit-shell__hint">
          <%= t("tasks.chatkit.configure_hint",
                api_url: "CHATKIT_API_URL",
                client_secret: "CHATKIT_CLIENT_SECRET") %>
        </p>
      </div>
    <% end %>
  </div>
</div>
```

## Standalone View (Full Page)

For ChatKit as a standalone page without app layout:

```erb
<%# app/views/agents/chatkit_standalone.html.erb %>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><%= @agent.name %> · ChatKit</title>
  <script src="<%= ChatkitConfig.script_url %>" defer></script>
  <style nonce="<%= content_security_policy_nonce %>">
    html, body {
      height: 100%;
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    /* Dark mode default */
    html, body {
      color: #f8f8f8;
      background: #0e0e0e;
    }
    /* Light mode override */
    html[data-theme="light"], body[data-theme="light"] {
      color: #1c1c1c;
      background: #f7f7f7;
    }
    .ck-standalone {
      height: 100vh;
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      box-sizing: border-box;
    }
    .ck-standalone__title {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }
    #chatkit-host {
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
    }
    #chatkit-host openai-chatkit {
      display: block;
      width: 100%;
      height: 100%;
      flex: 1 1 auto;
      min-height: 0;
    }
  </style>
</head>
<body>
  <div class="ck-standalone">
    <h1 class="ck-standalone__title"><%= @agent.name %></h1>
    <div id="chatkit-host"></div>
  </div>

  <script nonce="<%= content_security_policy_nonce %>">
    // Inline initialization (see INITIALIZATION.md for full script)
  </script>
</body>
</html>
```

## Data Attribute Building Pattern

Build data attributes dynamically based on configuration:

```ruby
# In view or helper
def chatkit_data_attributes(agent:, settings:)
  data = {
    chatkit_header_title_value: settings[:header_title],
    chatkit_upload_url_value: chatkit_upload_url(agent_id: agent.id),
    chatkit_upload_max_size_value: ChatkitConfig.upload_max_bytes,
    chatkit_upload_accept_value: ChatkitConfig.allowed_mime_types.join(","),
    chatkit_api_url_value: "#{chatkit_url}?agent_id=#{agent.id}",
    chatkit_domain_key_value: settings[:domain_key]
  }

  # Conditional attributes
  if settings[:client_secret_path].present?
    data[:chatkit_client_secret_path_value] = settings[:client_secret_path]
  end

  if settings[:initial_thread].present?
    data[:chatkit_initial_thread_value] = settings[:initial_thread]
  end

  data
end
```

```erb
<%= content_tag :div, class: "chatkit-shell__frame", data: chatkit_data_attributes(agent: @agent, settings: @chatkit_settings) do %>
  <div class="chatkit-shell__error" role="alert" hidden></div>
<% end %>
```

## Container Structure

### Page Layout

```
.chatkit-page
└── .chatkit-shell
    └── .chatkit-shell__frame (data attributes here)
        └── openai-chatkit (created by JS)
```

### Error States

```erb
<%# Configuration missing %>
<div class="chatkit-shell__empty">
  <p>ChatKit is not configured.</p>
  <p class="chatkit-shell__hint">Set CHATKIT_API_URL or CHATKIT_CLIENT_SECRET.</p>
</div>

<%# Runtime error container (hidden initially) %>
<div class="chatkit-shell__error" role="alert" hidden></div>
```

## Controller Setup

```ruby
class AgentsController < ApplicationController
  def chatkit
    @agent = current_account.agents.find(params[:id])

    @chatkit_settings = {
      api_url: "#{chatkit_url}?agent_id=#{@agent.id}",
      domain_key: ChatkitConfig.domain_key,
      upload_url: chatkit_upload_url(agent_id: @agent.id),
      upload_max_bytes: ChatkitConfig.upload_max_bytes,
      allowed_mime_types: ChatkitConfig.allowed_mime_types,
      header_title: @agent.name
    }

    # Optional: Resume existing thread
    @chatkit_settings[:initial_thread] = params[:thread_id] if params[:thread_id].present?

    # Hosted mode: provide secret endpoint
    if ChatkitConfig.hosted?
      @chatkit_settings[:client_secret_path] = chatkit_client_secret_path
    end
  end

  def chatkit_standalone
    @agent = current_account.agents.find(params[:id])

    @chatkit_settings = {
      api_url: "#{chatkit_url}?agent_id=#{@agent.id}",
      domain_key: ChatkitConfig.domain_key,
      upload_url: chatkit_upload_url(agent_id: @agent.id),
      upload_max_bytes: ChatkitConfig.upload_max_bytes,
      allowed_mime_types: ChatkitConfig.allowed_mime_types
    }

    render layout: false
  end
end
```

## Routes

```ruby
# config/routes.rb
resources :agents do
  member do
    get :chatkit
    get :chatkit_standalone
  end
end

# ChatKit protocol endpoint
post "/chatkit", to: "chatkit#entry"
post "/chatkit/upload", to: "chatkit#upload", as: :chatkit_upload
post "/chatkit/client_secret", to: "chatkit#client_secret", as: :chatkit_client_secret
```

## Bootstrap Script Loading

### Async Loading (Embedded)

```erb
<script src="<%= ChatkitConfig.script_url %>" async data-chatkit-script></script>
```

### Deferred Loading (Standalone)

```erb
<script src="<%= ChatkitConfig.script_url %>" defer></script>
```

## CSP Considerations

When using inline scripts, ensure nonce is applied:

```erb
<%= javascript_tag nonce: true do %>
  // Your script here
<% end %>
```

For standalone views with inline styles:

```erb
<style nonce="<%= content_security_policy_nonce %>">
  /* Your styles here */
</style>
```
