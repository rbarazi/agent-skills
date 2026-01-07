# Model Sync

## Purpose
Synchronize LLM model configurations from provider APIs to keep pricing, features, and model lists up-to-date.

## Sync Workflow

### Rake Tasks

```ruby
# lib/tasks/models.rake
namespace :models do
  # Provider configurations
  PROVIDER_CONFIGS = {
    "openai" => {
      client_class: "OpenAIClient",
      api_key_env: ["OPENAI_API_KEY"],
      display_name: "OpenAI"
    },
    "anthropic" => {
      client_class: "AnthropicClient",
      api_key_env: ["ANTHROPIC_API_KEY"],
      display_name: "Anthropic"
    },
    "gemini" => {
      client_class: "GeminiClient",
      api_key_env: ["GEMINI_API_KEY", "GOOGLE_AI_API_KEY"],
      display_name: "Gemini"
    },
    "openrouter" => {
      client_class: "OpenRouterClient",
      api_key_env: ["OPENROUTER_API_KEY"],
      display_name: "OpenRouter"
    }
  }.freeze

  desc "List available models from all configured providers"
  task list: :environment do
    PROVIDER_CONFIGS.each do |provider_key, config|
      api_key = find_api_key(config[:api_key_env])
      next if api_key.blank?

      models = config[:client_class].constantize.list_models(api_key)
      puts "#{config[:display_name]}: #{models.size} models"
    end
  end

  desc "Sync YAML config with OpenRouter API"
  task sync_with_openrouter: :environment do
    prune_stale = ENV["PRUNE"] == "1"
    dry_run = ENV["DRY_RUN"] == "1"

    config_file = Rails.root.join("config", "llm_models.yml")

    # Fetch models from OpenRouter
    response = Faraday.get("https://openrouter.ai/api/v1/models")
    raise "Failed to fetch models" unless response.status == 200

    openrouter_data = JSON.parse(response.body)
    models = openrouter_data["data"]

    # Load existing config
    existing_config = YAML.load_file(config_file)
    updated_config = existing_config.deep_dup

    # Build provider mappings
    provider_mappings = build_provider_mappings(models)

    # Update each provider
    provider_mappings.each do |provider_key, provider_models|
      next unless updated_config.dig("providers", provider_key)

      provider_models.each do |model_data|
        model_key = normalize_model_key(model_data[:id])
        next if model_excluded?(provider_key, model_data[:id])

        existing = updated_config.dig("providers", provider_key, "models", model_key)

        if existing
          updated_config["providers"][provider_key]["models"][model_key] =
            merge_model_data(existing, model_data)
        else
          updated_config["providers"][provider_key]["models"][model_key] =
            build_new_model_config(model_data)
        end
      end
    end

    # Optional pruning
    if prune_stale
      prune_stale_models!(updated_config, provider_mappings, dry_run: dry_run)
    end

    # Write with backup
    unless dry_run
      backup_file = "#{config_file}.backup.#{Time.now.strftime('%Y%m%d_%H%M%S')}"
      FileUtils.cp(config_file, backup_file)
      File.write(config_file, updated_config.to_yaml)
    end
  end

  private

  def find_api_key(api_key_env_vars)
    api_key_env_vars.map { |env| ENV[env] }.find(&:present?)
  end
end
```

## OpenRouter Provider Mapping

Map OpenRouter model IDs to local providers:

```ruby
OPENROUTER_PROVIDER_PATTERNS = {
  "openai" => /^openai\//,
  "anthropic" => /^anthropic\//,
  "gemini" => /^google\//,
  "ollama" => /^(?:meta-llama|mistralai)\//
}.freeze

def build_provider_mappings(models)
  mappings = PROVIDER_CONFIGS.keys.each_with_object({}) { |p, h| h[p] = [] }

  models.each do |model|
    model_id = model["id"]

    OPENROUTER_PROVIDER_PATTERNS.each do |provider, pattern|
      if model_id.match?(pattern)
        mappings[provider] << transform_openrouter_model(model, provider)
        break
      end
    end
  end

  mappings
end

def transform_openrouter_model(model, provider)
  {
    id: extract_model_name(model["id"], provider),
    full_id: model["id"],
    description: model["description"],
    context_length: model.dig("top_provider", "context_length") || model["context_length"],
    max_output_tokens: model.dig("top_provider", "max_completion_tokens"),
    pricing: extract_pricing(model["pricing"]),
    features: extract_features(model)
  }
end

def extract_model_name(full_id, provider)
  # Remove provider prefix (e.g., "openai/gpt-4o" -> "gpt-4o")
  full_id.sub(%r{^#{provider}/}, "").sub(%r{^[^/]+/}, "")
end

def extract_features(model)
  features = []

  # Check architecture for multimodal capabilities
  arch = model.dig("architecture", "modality") || ""
  features << "vision" if arch.include?("image")
  features << "multimodal" if arch.include?("image") || arch.include?("audio")

  # Check for function calling support
  features << "function_calling" if model["supported_parameters"]&.include?("tools")

  # Check for structured outputs
  features << "structured_outputs" if model["supported_parameters"]&.include?("response_format")

  features.uniq
end

def normalize_model_key(model_id)
  model_id.to_s.downcase.gsub(/[^a-z0-9\-]/, "-").gsub(/-+/, "-").gsub(/^-|-$/, "")
end
```

## Price Conversion

OpenRouter returns per-token pricing; convert to per-1K tokens:

```ruby
def extract_pricing(pricing_data)
  return {} unless pricing_data

  {
    "input" => per_1k_token_price(pricing_data["prompt"]),
    "output" => per_1k_token_price(pricing_data["completion"])
  }.compact
end

def per_1k_token_price(per_token_price)
  return nil if per_token_price.blank?

  (BigDecimal(per_token_price.to_s) * 1000).round(8).to_f
end
```

## Model Exclusion

Exclude deprecated/preview models:

```ruby
EXCLUDED_MODELS = {
  "openai" => %w[
    gpt-4-turbo-preview
    gpt-3.5-turbo
    chatgpt-4o-latest
  ],
  "anthropic" => %w[
    claude-3-opus-20240229
    claude-3-haiku-20240307
  ],
  "gemini" => %w[
    gemini-pro
    gemini-pro-vision
  ]
}.freeze

def model_excluded?(provider_key, model_id)
  excluded = EXCLUDED_MODELS[provider_key] || []
  normalized = normalize_model_key(model_id)
  excluded.any? { |e| normalize_model_key(e) == normalized }
end
```

## Merge Strategy

Preserve custom features while updating pricing:

```ruby
def merge_model_data(existing, new_data)
  merged = existing.deep_dup

  # Update pricing
  merged["pricing"] = new_data[:pricing] if new_data[:pricing].present?

  # Update context/tokens
  merged["context_length"] = new_data[:context_length] if new_data[:context_length]
  merged["max_output_tokens"] = new_data[:max_output_tokens] if new_data[:max_output_tokens]

  # Preserve custom features, add new ones
  existing_features = merged["features"] || []
  new_features = new_data[:features] || []
  merged["features"] = (existing_features + new_features).uniq

  # Add description if missing
  merged["description"] ||= new_data[:description]

  merged
end

def build_new_model_config(model_data)
  {
    "model" => model_data[:id],
    "description" => model_data[:description],
    "context_length" => model_data[:context_length],
    "max_output_tokens" => model_data[:max_output_tokens],
    "pricing" => model_data[:pricing],
    "features" => model_data[:features] || []
  }.compact
end
```

## Stale Model Pruning

Remove models no longer in provider API:

```ruby
def prune_stale_models!(config, provider_mappings, dry_run:)
  provider_mappings.each do |provider_key, synced_models|
    models_config = config.dig("providers", provider_key, "models")
    next unless models_config

    synced_keys = synced_models.map { |m| normalize_model_key(m[:id]) }.uniq
    stale_keys = models_config.keys - synced_keys

    # Skip embeddings models
    stale_keys.reject! do |key|
      features = models_config.dig(key, "features") || []
      features.include?("embeddings")
    end

    stale_keys.each do |key|
      if dry_run
        puts "Would remove: #{provider_key}/#{key}"
      else
        models_config.delete(key)
      end
    end
  end
end
```

## Safety Features

### Backup Before Write

```ruby
def write_config_with_backup(config_file, updated_config)
  backup = "#{config_file}.backup.#{Time.now.strftime('%Y%m%d_%H%M%S')}"
  FileUtils.cp(config_file, backup)
  File.write(config_file, updated_config.to_yaml)
  puts "Backup created: #{backup}"
end
```

### Dry Run Mode

```bash
# Preview changes without writing
DRY_RUN=1 rake models:sync_with_openrouter

# Sync and prune stale models
PRUNE=1 rake models:sync_with_openrouter
```

## Usage

```bash
# List all available models
rake models:list

# List models for specific provider
rake models:list_provider[openai]

# Sync with OpenRouter
rake models:sync_with_openrouter

# Sync with pruning (removes stale models)
PRUNE=1 rake models:sync_with_openrouter

# Dry run (preview only)
DRY_RUN=1 PRUNE=1 rake models:sync_with_openrouter

# Update specific model name
rake models:update_config[gemini,old-model-name,new-model-name]
```

## Next Steps

- [Usage and Cost](07-usage-cost.md) - Token tracking and cost calculation
- [Rails Adapter](08-rails-adapter.md) - Rails-specific integration
