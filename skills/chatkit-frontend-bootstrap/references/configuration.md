# ChatKit Configuration

Configuration model and environment variables for ChatKit integration.

## ChatkitConfig Model

```ruby
# app/models/chatkit_config.rb
class ChatkitConfig
  DEFAULT_SCRIPT_URL = "https://cdn.platform.openai.com/deployments/chatkit/chatkit.js".freeze

  class << self
    # Is ChatKit enabled? (either mode)
    def enabled?
      self_hosted? || hosted?
    end

    # Self-hosted: ChatKit connects to your Rails backend
    def self_hosted?
      api_url.present? && !hosted?
    end

    # Hosted: ChatKit connects to OpenAI's infrastructure
    def hosted?
      client_secret.present?
    end

    # API URL for self-hosted mode
    def api_url
      ENV.fetch("CHATKIT_API_URL", "/chatkit")
    end

    # Domain key for verification
    def domain_key
      ENV.fetch("CHATKIT_PK", ENV.fetch("CHATKIT_DOMAIN_KEY", "local-dev"))
    end

    # Client secret for hosted mode
    def client_secret
      ENV["CHATKIT_CLIENT_SECRET"]
    end

    # ChatKit JS library URL
    def script_url
      ENV.fetch("CHATKIT_SCRIPT_URL", DEFAULT_SCRIPT_URL)
    end

    # Maximum upload file size
    def upload_max_bytes
      ENV.fetch("CHATKIT_UPLOAD_MAX_BYTES", 25.megabytes).to_i
    end

    # Allowed MIME types for uploads
    def allowed_mime_types
      ENV.fetch("CHATKIT_ALLOWED_MIME_TYPES", "").split(",").map(&:strip).reject(&:blank?)
    end
  end
end
```

## Environment Variables

### Self-Hosted Mode (Default)

| Variable | Default | Description |
|----------|---------|-------------|
| `CHATKIT_API_URL` | `/chatkit` | Backend API endpoint |
| `CHATKIT_DOMAIN_KEY` | `local-dev` | Domain verification key |
| `CHATKIT_UPLOAD_MAX_BYTES` | `26214400` (25MB) | Max upload file size |
| `CHATKIT_ALLOWED_MIME_TYPES` | `""` (all allowed) | Comma-separated MIME types |
| `CHATKIT_SCRIPT_URL` | (OpenAI CDN) | ChatKit JS library URL |

### Hosted Mode

| Variable | Required | Description |
|----------|----------|-------------|
| `CHATKIT_CLIENT_SECRET` | Yes | OpenAI-provided client secret |
| `CHATKIT_PK` | Yes | OpenAI-provided domain/project key |

## Example .env

### Self-Hosted Development

```bash
# Self-hosted mode (uses defaults)
# No configuration needed - ChatKit connects to /chatkit

# Optional customizations:
CHATKIT_UPLOAD_MAX_BYTES=52428800  # 50MB
CHATKIT_ALLOWED_MIME_TYPES=image/png,image/jpeg,application/pdf
```

### Hosted Production

```bash
# Hosted mode - connects to OpenAI infrastructure
CHATKIT_CLIENT_SECRET=sk-chatkit-...
CHATKIT_PK=pk-your-project-key
```

## Mode Detection in Views

```erb
<% if ChatkitConfig.enabled? %>
  <% if ChatkitConfig.hosted? %>
    <%# Hosted mode: use client secret endpoint %>
    <% chatkit_data[:chatkit_client_secret_path_value] = chatkit_client_secret_path %>
  <% else %>
    <%# Self-hosted mode: direct API URL %>
    <% chatkit_data[:chatkit_api_url_value] = chatkit_url %>
  <% end %>
<% else %>
  <div class="chatkit-shell__empty">
    <p>ChatKit is not configured.</p>
  </div>
<% end %>
```

## Controller Configuration Builder

```ruby
class AgentsController < ApplicationController
  def chatkit
    @agent = current_account.agents.find(params[:id])
    @chatkit_settings = build_chatkit_settings
  end

  private

  def build_chatkit_settings
    settings = {
      domain_key: ChatkitConfig.domain_key,
      upload_max_bytes: ChatkitConfig.upload_max_bytes,
      allowed_mime_types: ChatkitConfig.allowed_mime_types,
      header_title: @agent.name
    }

    if ChatkitConfig.hosted?
      # Hosted mode: provide secret endpoint
      settings[:client_secret_path] = chatkit_client_secret_path
    else
      # Self-hosted mode: direct API and upload URLs
      settings[:api_url] = "#{chatkit_url}?agent_id=#{@agent.id}"
      settings[:upload_url] = chatkit_upload_url(agent_id: @agent.id)
    end

    # Optional: initial thread for resuming conversations
    settings[:initial_thread] = params[:thread_id] if params[:thread_id].present?

    settings
  end
end
```

## Upload Configuration

### Setting MIME Types

```bash
# Allow specific types
CHATKIT_ALLOWED_MIME_TYPES=image/png,image/jpeg,image/gif,application/pdf

# Allow all types (empty)
CHATKIT_ALLOWED_MIME_TYPES=
```

### JavaScript Accept Format

The bootstrap converts comma-separated types to ChatKit format:

```javascript
// Input: "image/png,image/jpeg,application/pdf"

const parseAccept = (raw) => {
  if (!raw) return undefined;
  const list = raw.split(",").map((v) => v.trim()).filter(Boolean);
  if (list.length === 0) return undefined;
  return list.reduce((acc, type) => {
    acc[type] = [];  // Empty array = any extension
    return acc;
  }, {});
};

// Output:
// {
//   "image/png": [],
//   "image/jpeg": [],
//   "application/pdf": []
// }
```

## Script URL Override

For testing or custom deployments:

```bash
# Use local or custom ChatKit build
CHATKIT_SCRIPT_URL=http://localhost:3001/chatkit.js

# Use specific version
CHATKIT_SCRIPT_URL=https://cdn.platform.openai.com/deployments/chatkit/v2.1.0/chatkit.js
```

## Testing Configuration

```ruby
# spec/support/chatkit_config_helper.rb
module ChatkitConfigHelper
  def stub_chatkit_self_hosted
    allow(ChatkitConfig).to receive(:enabled?).and_return(true)
    allow(ChatkitConfig).to receive(:hosted?).and_return(false)
    allow(ChatkitConfig).to receive(:self_hosted?).and_return(true)
    allow(ChatkitConfig).to receive(:api_url).and_return("/chatkit")
  end

  def stub_chatkit_hosted
    allow(ChatkitConfig).to receive(:enabled?).and_return(true)
    allow(ChatkitConfig).to receive(:hosted?).and_return(true)
    allow(ChatkitConfig).to receive(:self_hosted?).and_return(false)
    allow(ChatkitConfig).to receive(:client_secret).and_return("test-secret")
  end

  def stub_chatkit_disabled
    allow(ChatkitConfig).to receive(:enabled?).and_return(false)
    allow(ChatkitConfig).to receive(:hosted?).and_return(false)
    allow(ChatkitConfig).to receive(:self_hosted?).and_return(false)
  end
end

RSpec.configure do |config|
  config.include ChatkitConfigHelper
end
```

## Configuration Validation

```ruby
# config/initializers/chatkit.rb
Rails.application.config.after_initialize do
  if Rails.env.production?
    unless ChatkitConfig.enabled?
      Rails.logger.warn "ChatKit is not configured. Set CHATKIT_API_URL or CHATKIT_CLIENT_SECRET"
    end

    if ChatkitConfig.hosted? && ChatkitConfig.domain_key == "local-dev"
      Rails.logger.warn "ChatKit hosted mode enabled but CHATKIT_PK not set"
    end
  end
end
```

## Routes for Configuration Endpoints

```ruby
# config/routes.rb
Rails.application.routes.draw do
  # ChatKit protocol endpoint
  post "/chatkit", to: "chatkit#entry", as: :chatkit

  # File upload endpoint
  post "/chatkit/upload", to: "chatkit#upload", as: :chatkit_upload

  # Client secret endpoint (hosted mode)
  post "/chatkit/client_secret", to: "chatkit#client_secret", as: :chatkit_client_secret
end
```
