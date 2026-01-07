# LLM Gateway and Factory

## Purpose
Provide a secure factory pattern for creating provider-specific LLM clients with whitelist validation.

## Gateway Implementation

```ruby
# app/models/llm_gateway.rb
class LLMGateway
  # Whitelist of allowed client classes to prevent unsafe reflection
  ALLOWED_CLIENT_CLASSES = %w[
    OpenAIClient
    OpenAIResponsesClient
    AnthropicClient
    GeminiClient
    OllamaClient
    VoyageAIClient
    OpenRouterClient
    GroqClient
  ].freeze

  # Standard client creation by provider
  def self.create(provider:, api_key:, models: nil)
    config = LLMConfig.provider_config(provider)
    client_class_name = config["client_class"]

    unless client_class_name
      raise ArgumentError, "Missing client_class for LLM provider: #{provider}"
    end

    # Validate client class name against whitelist
    unless ALLOWED_CLIENT_CLASSES.include?(client_class_name)
      raise ArgumentError, "Unsupported client class: #{client_class_name}"
    end

    begin
      client_class = Object.const_get(client_class_name)
      client_class.new(api_key: api_key, models: models)
    rescue NameError
      raise ArgumentError, "Unsupported LLM provider: #{provider}"
    rescue StandardError => e
      raise ArgumentError, "Failed to initialize #{provider} client: #{e.message}"
    end
  end

  # Model-aware creation for API type selection
  # Routes to correct client based on model's api_type configuration
  def self.create_for_model(provider:, model_name:, api_key:, models: nil)
    api_type = LLMConfig.get_api_type(provider, model_name)
    client_class_name = determine_client_class(provider, api_type)

    unless client_class_name
      raise ArgumentError, "Could not determine client class for provider: #{provider}"
    end

    unless ALLOWED_CLIENT_CLASSES.include?(client_class_name)
      raise ArgumentError, "Unsupported client class: #{client_class_name}"
    end

    client_class = Object.const_get(client_class_name)
    client_class.new(api_key: api_key, models: models)
  end

  private_class_method def self.determine_client_class(provider, api_type)
    case provider.to_s.downcase
    when "openai"
      api_type == "responses" ? "OpenAIResponsesClient" : "OpenAIClient"
    when "anthropic"
      "AnthropicClient"
    when "gemini"
      "GeminiClient"
    when "ollama"
      "OllamaClient"
    when "openrouter"
      "OpenRouterClient"
    else
      # Fallback to provider config
      LLMConfig.provider_config(provider)["client_class"]
    end
  end
end
```

## Usage Examples

### Basic Provider Creation

```ruby
# Create OpenAI client
openai = LLMGateway.create(
  provider: :openai,
  api_key: ENV['OPENAI_API_KEY']
)

# Create Anthropic client
anthropic = LLMGateway.create(
  provider: :anthropic,
  api_key: ENV['ANTHROPIC_API_KEY']
)

# Create with custom model configuration
client = LLMGateway.create(
  provider: :openai,
  api_key: api_key,
  models: {
    "custom-model" => {
      model: "gpt-4o",
      features: ["vision"],
      token_limit: 4096
    }
  }
)
```

### Model-Aware Creation

```ruby
# For OpenAI, routes to correct API (Chat vs Responses)
client = LLMGateway.create_for_model(
  provider: :openai,
  model_name: "gpt-4o",  # Has api_type: "responses" in config
  api_key: api_key
)
# Returns OpenAIResponsesClient

client = LLMGateway.create_for_model(
  provider: :openai,
  model_name: "gpt-3.5-turbo",  # Uses default "chat_completions"
  api_key: api_key
)
# Returns OpenAIClient
```

### In a Service Context

```ruby
class AIService
  def initialize(account)
    @account = account
  end

  def client
    @client ||= LLMGateway.create(
      provider: @account.llm_provider,
      api_key: @account.llm_api_key
    )
  end

  def chat(prompt, model: nil)
    model ||= @account.default_model

    client.create_message(
      system: "You are a helpful assistant",
      model: model,
      limit: 1000,
      messages: [{ role: "user", content: prompt }]
    )
  end
end
```

## Security Considerations

1. **Whitelist Validation**: Only pre-approved client classes can be instantiated
2. **No Unsafe Reflection**: Class names validated before `const_get`
3. **API Key Isolation**: Each client instance has its own API key
4. **Error Masking**: Internal errors wrapped with safe messages

## Adding New Providers

1. Create the client class (e.g., `NewProviderClient`)
2. Add to `ALLOWED_CLIENT_CLASSES` whitelist
3. Add provider config to `llm_models.yml`
4. Optionally add to `determine_client_class` for special routing

```ruby
# 1. Add to whitelist
ALLOWED_CLIENT_CLASSES = %w[
  # ... existing clients
  NewProviderClient
].freeze

# 2. Add config
# config/llm_models.yml
providers:
  newprovider:
    name: New Provider
    client_class: NewProviderClient
    models:
      # ...
```

## Testing

```ruby
RSpec.describe LLMGateway do
  describe ".create" do
    it "creates the correct client type" do
      client = described_class.create(
        provider: :openai,
        api_key: "test-key"
      )
      expect(client).to be_a(OpenAIClient)
    end

    it "rejects unknown providers" do
      expect {
        described_class.create(provider: :unknown, api_key: "key")
      }.to raise_error(ArgumentError, /Missing client_class/)
    end

    it "rejects unsafe client classes" do
      allow(LLMConfig).to receive(:provider_config)
        .and_return({ "client_class" => "Kernel" })

      expect {
        described_class.create(provider: :evil, api_key: "key")
      }.to raise_error(ArgumentError, /Unsupported client class/)
    end
  end
end
```

## Next Steps

- [Base Client](02-base-client.md) - Abstract client implementation
- [Configuration System](03-configuration.md) - YAML-driven configuration
