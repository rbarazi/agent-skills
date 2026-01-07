# Rails Adapter

## Purpose
Rails-specific integration patterns for the LLM Gateway, including ActiveRecord models, caching, and multi-tenancy support.

## Account-Level LLM Configuration

Store per-account LLM settings:

```ruby
# app/models/llm.rb
class LLM < ApplicationRecord
  has_many :account_llms
  has_many :accounts, through: :account_llms

  validates :name, presence: true, uniqueness: true

  store_accessor :config,
    :default_model,
    :models  # Override or extend models from YAML

  def client_class
    LLMConfig.provider_config(name)["client_class"]&.constantize
  end
end

# app/models/account_llm.rb
class AccountLLM < ApplicationRecord
  belongs_to :account
  belongs_to :llm

  encrypts :api_key

  validates :account_id, uniqueness: { scope: :llm_id }

  store_accessor :config,
    :default_model,
    :custom_models

  def provider
    llm.name
  end

  # Get client for specific model, handling API type routing
  def llm_client_for_model(model_name)
    api_type = LLMConfig.get_api_type(provider, model_name)
    @llm_clients_by_api_type ||= {}
    @llm_clients_by_api_type[api_type] ||= LLMGateway.create_for_model(
      provider: provider,
      model_name: model_name,
      api_key: api_key,
      models: merged_models
    )
  end

  # Merge YAML models with account-specific overrides
  def merged_models
    base = LLMConfig.generate_default_models_for_client(provider)
    (custom_models || {}).each do |key, config|
      base[key] = base[key]&.merge(config) || config
    end
    base
  end
end
```

## Agent Integration

Wire LLM to agents:

```ruby
# app/models/agent.rb
class Agent < ApplicationRecord
  belongs_to :account
  belongs_to :account_llm

  validates :model, presence: true

  def llm_client
    account_llm.llm_client_for_model(model)
  end

  def effective_model
    model.presence || account_llm.default_model
  end

  def supports_feature?(feature)
    LLMConfig.model_config(account_llm.provider, effective_model)
      .dig("features")&.include?(feature.to_s)
  end

  def context_length
    LLMConfig.get_context_length(account_llm.provider, effective_model)
  end
end
```

## Configuration Caching

Cache YAML config for performance:

```ruby
# app/models/llm_config.rb
class LLMConfig
  CONFIG_FILE = Rails.root.join("config", "llm_models.yml").freeze

  def self.load_config
    @config ||= begin
      Rails.cache.fetch("llm_config", expires_in: 1.hour) do
        YAML.load_file(CONFIG_FILE)
      end
    end
  end

  def self.reload!
    Rails.cache.delete("llm_config")
    @config = nil
  end

  # Rest of methods...
end

# Clear cache on deploy
# config/initializers/llm_config.rb
Rails.application.config.after_initialize do
  LLMConfig.reload! if Rails.env.production?
end
```

## Multi-Tenancy Support

Scope LLM usage per account:

```ruby
# app/controllers/concerns/llm_context.rb
module LLMContext
  extend ActiveSupport::Concern

  included do
    before_action :set_llm_context
  end

  private

  def set_llm_context
    Current.account = current_account
    Current.account_llm = current_account.default_account_llm
  end

  def llm_client
    Current.account_llm&.llm_client_for_model(current_model)
  end

  def current_model
    params[:model] || Current.account_llm&.default_model
  end
end
```

## Database Migrations

```ruby
# db/migrate/create_llm_tables.rb
class CreateLLMTables < ActiveRecord::Migration[7.0]
  def change
    create_table :llms, id: :uuid do |t|
      t.string :name, null: false, index: { unique: true }
      t.string :display_name
      t.string :default_model
      t.jsonb :config, null: false, default: {}
      t.boolean :active, null: false, default: true

      t.timestamps
    end

    create_table :account_llms, id: :uuid do |t|
      t.references :account, type: :uuid, null: false, foreign_key: true
      t.references :llm, type: :uuid, null: false, foreign_key: true
      t.string :api_key  # Encrypted
      t.string :default_model
      t.jsonb :config, null: false, default: {}
      t.jsonb :usage_stats, null: false, default: {}

      t.timestamps

      t.index [:account_id, :llm_id], unique: true
    end
  end
end
```

## Seed Data

```ruby
# db/seeds.rb
llms = [
  { name: "openai", display_name: "OpenAI", default_model: "gpt-4o" },
  { name: "anthropic", display_name: "Anthropic", default_model: "claude-3-5-sonnet" },
  { name: "gemini", display_name: "Google Gemini", default_model: "gemini-pro" }
]

llms.each do |attrs|
  LLM.find_or_create_by!(name: attrs[:name]) do |llm|
    llm.display_name = attrs[:display_name]
    llm.default_model = attrs[:default_model]
  end
end
```

## Admin Interface

```ruby
# app/controllers/admin/llms_controller.rb
module Admin
  class LLMsController < ApplicationController
    def index
      @llms = LLM.all.includes(:accounts)
    end

    def show
      @llm = LLM.find(params[:id])
      @models = LLMConfig.models_for_provider(@llm.name)
    end

    def sync_models
      # Use a background job to avoid long-running requests and timeouts
      ModelSyncJob.perform_later
      redirect_to admin_llms_path, notice: "Model sync has been started."
    end
  end
end
```

## API Endpoints

```ruby
# app/controllers/api/v1/llm_controller.rb
module Api
  module V1
    class LLMController < ApplicationController
      include LLMContext

      def models
        models = LLMConfig.all_models.select do |m|
          m[:provider] == params[:provider] || params[:provider].blank?
        end

        render json: { models: models }
      end

      def chat
        response = llm_client.create_message(
          system: params[:system],
          model: current_model,
          limit: params[:max_tokens] || 1000,
          messages: params[:messages]
        )

        render json: {
          content: response.content,
          usage: response.usage,
          model: current_model
        }
      end
    end
  end
end
```

## Background Jobs

```ruby
# app/jobs/llm_request_job.rb
class LLMRequestJob < ApplicationJob
  queue_as :llm

  def perform(task_id, message_content)
    task = Task.find(task_id)
    client = task.agent.llm_client

    response = client.create_message(
      system: task.agent.system_prompt,
      model: task.agent.effective_model,
      limit: task.agent.context_length / 2,
      messages: task.formatted_messages
    )

    task.messages.create!(
      role: "assistant",
      content: response.content,
      metadata: { usage: response.usage }
    )

    UsageTrackingService.track(task.messages.last, response)
  end
end
```

## Testing Helpers

```ruby
# spec/support/llm_helpers.rb
module LLMHelpers
  def stub_llm_response(content: "Hello!", usage: {})
    response = LLMClient::LLMResponse.new(
      content,
      [],
      "stop",
      usage.presence || { "total_tokens" => 10 }
    )

    allow_any_instance_of(LLMClient).to receive(:create_message)
      .and_return(response)
  end

  def with_llm_provider(provider, api_key: "test-key")
    llm = create(:llm, name: provider)
    account_llm = create(:account_llm, llm: llm, api_key: api_key)

    yield account_llm
  end
end

RSpec.configure do |config|
  config.include LLMHelpers
end
```

## Environment Configuration

```ruby
# config/environments/production.rb
Rails.application.configure do
  # Cache LLM config in Redis
  config.cache_store = :redis_cache_store, { url: ENV["REDIS_URL"] }

  # Background queue for LLM requests
  config.active_job.queue_adapter = :sidekiq
end

# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
```

## Best Practices

1. **Encrypt API keys**: Always use Rails `encrypts` for API keys
2. **Cache config**: Cache YAML loading, clear on deploy
3. **Background jobs**: Use jobs for long-running LLM requests
4. **Usage tracking**: Track all requests for billing/analytics
5. **Model validation**: Validate model exists before creating agents
6. **Rate limiting**: Implement per-account rate limits

## Testing

```ruby
RSpec.describe AccountLLM do
  describe "#llm_client_for_model" do
    let(:account_llm) { create(:account_llm, llm: create(:llm, name: "openai")) }

    it "creates client for model" do
      client = account_llm.llm_client_for_model("gpt-4o")
      expect(client).to be_a(OpenAIClient)
    end

    it "caches clients by API type" do
      client1 = account_llm.llm_client_for_model("gpt-4o")
      client2 = account_llm.llm_client_for_model("gpt-4o-mini")

      # Same API type, same client instance
      expect(client1).to eq(client2)
    end
  end
end
```
