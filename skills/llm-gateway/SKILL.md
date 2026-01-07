---
name: llm-gateway
description: Build a multi-provider LLM client abstraction layer for Rails applications. Use when integrating multiple LLM providers (OpenAI, Anthropic, Gemini, Ollama), implementing provider switching, feature-based model routing, or standardizing LLM responses across providers.
license: MIT
metadata:
  author: agentify
  version: "1.0"
  source: https://github.com/rbarazi/agentify
compatibility: Requires Rails 7+, Ruby 3.2+, Faraday gem.
---

# LLM Gateway

A unified interface for working with multiple LLM providers through a factory pattern, YAML-driven configuration, and provider-specific client implementations.

## Key Capabilities

- **Factory Pattern**: Create provider-specific clients through a unified gateway
- **YAML Configuration**: Centralized model definitions with features, pricing, and context limits
- **Provider Abstraction**: Common interface across OpenAI, Anthropic, Gemini, Ollama, etc.
- **Feature Detection**: Query model capabilities (vision, function_calling, embeddings)
- **Standardized Response**: Consistent response structure across all providers
- **Error Handling**: Structured errors with retry logic for rate limits
- **Embeddings Support**: Unified embeddings API with batch support

## Architecture

```
                    ┌─────────────────────┐
                    │     LLMGateway      │
                    │   (Factory Class)   │
                    └─────────┬───────────┘
                              │ create(provider:, api_key:)
                              ▼
                    ┌─────────────────────┐
                    │     LLMConfig       │
                    │   (YAML Loader)     │
                    └─────────┬───────────┘
                              │
        ┌───────────┬─────────┴─────────┬───────────┐
        ▼           ▼                   ▼           ▼
   ┌─────────┐ ┌──────────┐       ┌──────────┐ ┌─────────┐
   │ OpenAI  │ │Anthropic │  ...  │  Gemini  │ │ Ollama  │
   │ Client  │ │  Client  │       │  Client  │ │ Client  │
   └────┬────┘ └────┬─────┘       └────┬─────┘ └────┬────┘
        │           │                  │            │
        └───────────┴────────┬─────────┴────────────┘
                             ▼
                    ┌─────────────────────┐
                    │     LLMClient       │
                    │   (Base Class)      │
                    │   - LLMResponse     │
                    │   - FEATURES        │
                    │   - Retry Logic     │
                    └─────────────────────┘
```

## Quick Start

```ruby
# 1. Create a client through the gateway
client = LLMGateway.create(provider: :openai, api_key: ENV['OPENAI_API_KEY'])

# 2. Send a message
response = client.create_message(
  system: "You are a helpful assistant",
  model: "gpt-4o",
  limit: 1000,
  messages: [{ role: "user", content: "Hello!" }]
)

# 3. Access the standardized response
puts response.content        # "Hello! How can I help you?"
puts response.finish_reason  # "stop"
puts response.usage          # { "prompt_tokens" => 10, "completion_tokens" => 8 }
```

## Core Components

### Factory Pattern

```ruby
# Simple creation
client = LLMGateway.create(provider: :anthropic, api_key: api_key)

# Model-aware creation (routes to correct API variant)
client = LLMGateway.create_for_model(
  provider: :openai,
  model_name: "gpt-4o",
  api_key: api_key
)
```

### Configuration System

```yaml
# config/llm_models.yml
providers:
  openai:
    name: OpenAI
    client_class: OpenAIClient
    models:
      gpt-4o:
        model: gpt-4o
        features: [vision, function_calling, multimodal]
        context_length: 128000
        pricing: { input: 0.0025, output: 0.01 }
```

### Feature Detection

```ruby
# Check model features
LLMConfig.supports_vision?(:openai, "gpt-4o")  # => true
LLMConfig.supports_function_calling?(:openai, "gpt-4o")  # => true

# Find models by feature
LLMConfig.models_with_feature(:embeddings)
LLMConfig.cheapest_model_with_features(:openai, ["vision", "function_calling"])
```

## When to Use This Pattern

**Ideal for:**
- Applications requiring multiple LLM providers
- Cost optimization through model selection
- Feature-based routing (e.g., vision-capable models)
- Consistent error handling across providers

**Consider alternatives if:**
- Single provider only (use official SDK directly)
- Streaming-only workloads (add streaming layer)
- Very high throughput (consider async patterns)

## Output Checklist

When implementation is complete, verify:

- [ ] LLMGateway creates correct client for each provider
- [ ] Client whitelist prevents unsafe reflection attacks
- [ ] YAML config loads with all model metadata (features, pricing, context)
- [ ] Feature detection works: `supports_vision?`, `supports_function_calling?`
- [ ] LLMResponse struct returned consistently across all providers
- [ ] Rate limit errors trigger automatic retry with backoff
- [ ] API errors include structured `error_type`, `error_code` fields
- [ ] Model sync rake task updates pricing from OpenRouter
- [ ] Usage tracking records tokens and calculates costs
- [ ] Multi-tenant support with per-account API keys

## Common Pitfalls

1. **Unsafe reflection**: Always whitelist allowed client classes
2. **Sending internal metadata to APIs**: Filter `pricing`, `features`, `description` before API calls
3. **Provider-specific token params**: OpenAI o-series uses `max_completion_tokens`, not `max_tokens`
4. **Missing feature arrays in seeds**: Model config must include `features` array for detection
5. **Rate limit without retry**: Always implement exponential backoff for 429 responses
6. **Inconsistent usage keys**: Normalize `prompt_tokens` vs `input_tokens` vs `promptTokenCount`
7. **Price conversion errors**: OpenRouter returns per-token, config expects per-1K tokens

## Testing Notes

### Gateway Testing
- Test client creation for each provider
- Verify whitelist rejects unknown client classes
- Test model-aware routing (e.g., OpenAI responses vs chat API)

### Client Testing
- Test standardized LLMResponse across providers
- Verify message formatting for each provider's API format
- Test tool call formatting (different for OpenAI vs Anthropic vs Gemini)

### Error Handling Testing
- Test rate limit detection and retry
- Verify structured APIError with type/code
- Test timeout handling

### Configuration Testing
- Test YAML loading and caching
- Verify feature detection methods
- Test `cheapest_model_with_features` selection

### Integration Testing
- End-to-end request through gateway
- Usage tracking and cost calculation
- Multi-tenant isolation

## References

Detailed implementation guides:

- [Gateway and Factory](references/01-gateway-factory.md) - LLMGateway and client creation
- [Base Client](references/02-base-client.md) - LLMClient abstract class
- [Configuration System](references/03-configuration.md) - YAML-driven model config
- [Provider Implementations](references/04-provider-clients.md) - OpenAI, Anthropic, Gemini
- [Error Handling](references/05-error-handling.md) - Structured errors and retry logic
- [Model Sync](references/06-model-sync.md) - Syncing models from provider APIs
- [Usage and Cost](references/07-usage-cost.md) - Token tracking and cost calculation
- [Rails Adapter](references/08-rails-adapter.md) - Rails-specific integration patterns
