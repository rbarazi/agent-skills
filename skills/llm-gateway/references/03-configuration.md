# LLM Configuration System

## Purpose
Provide a centralized YAML-driven configuration system for LLM models with feature detection, pricing, and model selection utilities.

## Configuration Loader

```ruby
# app/models/llm_config.rb
class LLMConfig
  CONFIG_FILE = Rails.root.join("config", "llm_models.yml").freeze

  def self.load_config
    @config ||= YAML.load_file(CONFIG_FILE)
  end

  def self.providers
    load_config["providers"]
  end

  def self.provider_config(provider_name)
    providers[provider_name.to_s.downcase] || {}
  end

  def self.models_for_provider(provider_name)
    provider_config(provider_name)["models"] || {}
  end

  def self.model_config(provider_name, model_name)
    models_for_provider(provider_name)[model_name.to_s] || {}
  end

  def self.default_model_for_provider(provider_name)
    load_config.dig("defaults", provider_name.to_s.downcase)
  end

  # Get all models across all providers
  def self.all_models
    providers.flat_map do |provider_name, provider_config|
      models = provider_config["models"] || {}
      models.map do |model_name, model_config|
        {
          provider: provider_name,
          model_key: model_name,
          model_name: model_config["model"],
          features: model_config["features"] || [],
          context_length: model_config["context_length"] || 4096,
          max_output_tokens: model_config["max_output_tokens"],
          pricing: model_config["pricing"] || { input: 0, output: 0 },
          description: model_config["description"] || ""
        }
      end
    end
  end

  # Find models with specific feature
  def self.models_with_feature(feature)
    all_models.select do |model|
      model[:features].include?(feature.to_s)
    end
  end

  # Generate model configs for client initialization
  def self.generate_default_models_for_client(provider_name)
    models = models_for_provider(provider_name)

    models.transform_values do |model_config|
      {
        model: model_config["model"],
        features: model_config["features"] || [],
        token_limit: model_config["context_length"] || 4096,
        max_output_tokens: model_config["max_output_tokens"],
        pricing: model_config["pricing"] || { input: 0, output: 0 }
      }
    end
  end
end
```

## Feature Detection Methods

```ruby
class LLMConfig
  # Vision/image support
  def self.supports_vision?(provider_name, model_name)
    model_config(provider_name, model_name)["features"]&.include?("vision") || false
  end

  # Reasoning/thinking mode
  def self.supports_reasoning?(provider_name, model_name)
    model_config(provider_name, model_name)["features"]&.include?("reasoning") || false
  end

  # Audio/video support
  def self.supports_multimodal?(provider_name, model_name)
    model_config(provider_name, model_name)["features"]&.include?("multimodal") || false
  end

  # Tool/function calling
  def self.supports_function_calling?(provider_name, model_name)
    model_config(provider_name, model_name)["features"]&.include?("function_calling") || false
  end

  # Get context window size
  def self.get_context_length(provider_name, model_name)
    model_config(provider_name, model_name)["context_length"] || 4096
  end

  # Get pricing info
  def self.get_pricing(provider_name, model_name)
    model_config(provider_name, model_name)["pricing"] || { input: 0, output: 0 }
  end
end
```

## Model Selection Utilities

```ruby
class LLMConfig
  # Find cheapest model with required features
  def self.cheapest_model_with_features(provider_name, required_features = [])
    models = models_for_provider(provider_name)

    suitable_models = models.select do |_, config|
      features = config["features"] || []
      required_features.all? { |feature| features.include?(feature.to_s) }
    end

    return nil if suitable_models.empty?

    cheapest = suitable_models.min_by do |_, config|
      pricing = config["pricing"] || { "input" => 999, "output" => 999 }
      pricing["input"] + pricing["output"]
    end

    cheapest&.first
  end

  # API type detection (e.g., OpenAI responses vs chat_completions)
  def self.get_api_type(provider_name, model_name)
    config = model_config(provider_name, model_name)
    config["api_type"] || "chat_completions"
  end

  def self.supports_responses_api?(provider_name, model_name)
    get_api_type(provider_name, model_name) == "responses"
  end
end
```

## YAML Configuration Structure

```yaml
# config/llm_models.yml
---
providers:
  openai:
    name: OpenAI
    client_class: OpenAIClient
    base_url: https://api.openai.com
    api_type: openai
    models:
      gpt-4o:
        model: gpt-4o
        api_type: responses
        features:
          - vision
          - function_calling
          - multimodal
          - stateful_conversations
        context_length: 128000
        pricing:
          input: 0.0025
          output: 0.01
        description: Real-time multimodal, improved speed and cost
        max_output_tokens: 16384

      gpt-4o-mini:
        model: gpt-4o-mini
        api_type: responses
        features:
          - vision
          - function_calling
          - multimodal
        context_length: 128000
        pricing:
          input: 0.00015
          output: 0.0006
        description: Lightweight, cost-efficient
        max_output_tokens: 16384

  anthropic:
    name: Anthropic
    client_class: AnthropicClient
    base_url: https://api.anthropic.com
    models:
      claude-3-5-sonnet:
        model: claude-3-5-sonnet-20241022
        features:
          - vision
          - function_calling
        context_length: 200000
        pricing:
          input: 0.003
          output: 0.015
        description: Best balance of intelligence and speed
        max_output_tokens: 8192

  gemini:
    name: Google Gemini
    client_class: GeminiClient
    base_url: https://generativelanguage.googleapis.com
    models:
      gemini-pro:
        model: gemini-1.5-pro
        features:
          - vision
          - function_calling
          - multimodal
        context_length: 1048576
        pricing:
          input: 0.00125
          output: 0.005
        description: Google's most capable model

  voyageai:
    name: Voyage AI
    client_class: VoyageAIClient
    base_url: https://api.voyageai.com
    models:
      voyage-3:
        model: voyage-3
        features:
          - embeddings
        context_length: 32000
        pricing:
          input: 0.00006
          output: 0
        description: High-quality embeddings

defaults:
  openai: gpt-4o
  anthropic: claude-3-5-sonnet
  gemini: gemini-pro
```

## Usage Examples

### Feature-Based Model Selection

```ruby
# Find vision-capable models
vision_models = LLMConfig.models_with_feature(:vision)
# => [{ provider: "openai", model_key: "gpt-4o", ... }, ...]

# Get cheapest model with vision + function_calling
model = LLMConfig.cheapest_model_with_features(:openai, ["vision", "function_calling"])
# => "gpt-4o-mini"
```

### In Application Code

```ruby
class AgentService
  def initialize(agent)
    @agent = agent
    @provider = agent.account.llm_provider
    @model = agent.llm_model
  end

  def can_process_images?
    LLMConfig.supports_vision?(@provider, @model)
  end

  def can_use_tools?
    LLMConfig.supports_function_calling?(@provider, @model)
  end

  def context_limit
    LLMConfig.get_context_length(@provider, @model)
  end

  def estimated_cost(input_tokens, output_tokens)
    pricing = LLMConfig.get_pricing(@provider, @model)
    (input_tokens * pricing["input"] / 1000.0) +
      (output_tokens * pricing["output"] / 1000.0)
  end
end
```

### Client Configuration Generation

```ruby
# Used in client initialization
class GeminiClient < LLMClient
  def default_models
    LLMConfig.generate_default_models_for_client(:gemini)
  end
end
```

## Testing

```ruby
RSpec.describe LLMConfig do
  describe ".supports_vision?" do
    it "returns true for vision-capable models" do
      expect(described_class.supports_vision?(:openai, "gpt-4o")).to be true
    end

    it "returns false for non-vision models" do
      expect(described_class.supports_vision?(:voyageai, "voyage-3")).to be false
    end
  end

  describe ".cheapest_model_with_features" do
    it "finds the cheapest matching model" do
      model = described_class.cheapest_model_with_features(
        :openai,
        ["vision", "function_calling"]
      )
      expect(model).to eq("gpt-4o-mini")
    end

    it "returns nil when no model matches" do
      model = described_class.cheapest_model_with_features(
        :voyageai,
        ["chat"]  # VoyageAI only supports embeddings
      )
      expect(model).to be_nil
    end
  end
end
```

## Next Steps

- [Provider Implementations](04-provider-clients.md) - Specific provider clients
- [Error Handling](05-error-handling.md) - Error handling patterns
