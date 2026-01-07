# LLM Base Client

## Purpose
Provide an abstract base class with standardized response structure, feature detection, and common HTTP handling for all LLM providers.

## Base Client Implementation

```ruby
# app/models/llm_client.rb
class LLMClient
  include Loggable

  class RateLimitError < StandardError; end
  class APIError < StandardError
    attr_reader :error_type, :error_code, :error_param

    def initialize(message, error_type: nil, error_code: nil, error_param: nil)
      super(message)
      @error_type = error_type
      @error_code = error_code
      @error_param = error_param
    end
  end

  RETRY_LIMIT = 2
  RETRY_DELAY = 1

  # Standardized response structure
  LLMResponse = Struct.new(:content, :tool_calls, :finish_reason, :usage)

  DEFAULT_TOKEN_LIMIT = 4000
  DEFAULT_MODEL_TOKEN_LIMIT = 4096

  # Normalized finish reasons
  FINISH_REASON_STOP = ["stop", "end_turn", "STOP", "completed"].freeze
  FINISH_REASON_TOOL_USE = ["tool_calls", "tool_use"].freeze

  # Feature constants for capability detection
  FEATURES = {
    chat: :chat,
    embeddings: :embeddings,
    function_calling: :function_calling,
    vision: :vision,
    rerank: :rerank,
    speech_to_text: :speech_to_text,
    text_to_speech: :text_to_speech
  }.freeze

  attr_reader :api_key, :models

  def initialize(api_key:, models: nil)
    @api_key = api_key
    @models = normalize_models(models || default_models)
  end

  # Feature detection (class method)
  def self.supports_feature?(feature)
    supported_features.include?(feature)
  end

  # Override in subclasses
  def self.supported_features
    Set.new
  end

  # Main chat interface
  def create_message(system: nil, model:, limit: DEFAULT_MODEL_TOKEN_LIMIT, messages: [], tools: [])
    raise NotImplementedError, "#{self.class.name} does not support chat" unless self.class.supports_feature?(:chat)

    request_data = prepare_request(system, model, limit, messages, tools)
    execute_request_with_retry(request_data)
  end

  # Override in subclasses for provider-specific defaults
  def default_models
    {}
  end

  # Embeddings batch limit (provider-specific)
  def max_embedding_batch_size
    nil
  end

  protected

  # Must be implemented by subclasses
  def provider_config
    raise NotImplementedError, "Subclasses must implement provider_config"
  end

  def build_parameters_for_provider(system, model_config, limit, messages, tools)
    raise NotImplementedError, "Subclasses must implement build_parameters_for_provider"
  end

  def parse_response(json_response)
    raise NotImplementedError, "Subclasses must implement parse_response"
  end

  # Model configuration normalization
  def normalize_models(models_hash)
    models_hash = models_hash.to_h
    normalized = models_hash.transform_values do |config|
      config.is_a?(Hash) ? config.with_indifferent_access : config
    end
    normalized.with_indifferent_access
  end

  # Message validation - filters invalid messages before sending
  def build_parameters(system, model_config, limit, messages, tools)
    valid_messages = messages.reject { |m| invalid_message?(m) }
    build_parameters_for_provider(system, model_config, limit, valid_messages, tools)
  end

  private

  def connection
    @connection ||= Faraday.new(
      url: provider_config[:base_url],
      request: { timeout: 600, open_timeout: 600 }
    ) do |faraday|
      faraday.adapter Faraday.default_adapter
    end
  end

  def headers
    {}.tap do |h|
      h.merge!(provider_config[:default_headers] || {})
      h["Content-Type"] = "application/json"
    end
  end

  def prepare_request(system, model, limit, messages, tools)
    model_config = provider_config[:models][model]
    raise ArgumentError, "Unknown model: #{model}." if model_config.blank?

    # Filter internal metadata from API requests
    filtered_config = model_config.except(:pricing, :features, :description, :token_limit, :max_output_tokens)

    parameters = build_parameters(system, filtered_config, limit, messages, tools)
    url = build_url(model_config[:model])

    { url: url, parameters: parameters, model_config: filtered_config }
  end

  def execute_request_with_retry(request_data)
    attempts = 0

    begin
      attempts += 1
      response = make_http_request(request_data)
      process_response(response)
    rescue RateLimitError => e
      if attempts <= RETRY_LIMIT
        sleep RETRY_DELAY
        retry
      else
        raise
      end
    end
  end

  def make_http_request(request_data)
    connection.post do |req|
      req.headers = headers
      req.url request_data[:url]
      req.body = request_data[:parameters].to_json
    end
  end

  def process_response(response)
    json_response = try_parse_json(response.body)

    if api_error?(response, json_response)
      handle_api_error(response, json_response)
    end

    parse_response(json_response)
  end

  def try_parse_json(maybe_json)
    JSON.parse(maybe_json)
  rescue JSON::ParserError
    # Try JSONL format
    begin
      maybe_json.split("\n").reject(&:empty?).map { |line| JSON.parse(line) }
    rescue JSON::ParserError
      maybe_json
    end
  end

  def parse_arguments(arguments)
    return {} if arguments.blank?
    arguments.is_a?(String) ? JSON.parse(arguments, symbolize_names: true) : arguments.symbolize_keys
  rescue JSON::ParserError
    {}
  end
end
```

## Response Structure

All providers return the same `LLMResponse` structure:

```ruby
LLMResponse = Struct.new(:content, :tool_calls, :finish_reason, :usage)

# Example response
response = client.create_message(
  system: "You are helpful",
  model: "gpt-4o",
  limit: 1000,
  messages: [{ role: "user", content: "Hello" }]
)

response.content        # => "Hello! How can I help you today?"
response.tool_calls     # => [] or [{ name: "search", arguments: {...} }]
response.finish_reason  # => "stop" or "tool_calls"
response.usage          # => { "prompt_tokens" => 10, "completion_tokens" => 8 }
```

## Feature Detection

```ruby
# Client class feature support
OpenAIClient.supports_feature?(:chat)           # => true
OpenAIClient.supports_feature?(:vision)         # => true
VoyageAIClient.supports_feature?(:embeddings)   # => true
VoyageAIClient.supports_feature?(:chat)         # => false

# Subclass implementation
class GeminiClient < LLMClient
  def self.supported_features
    Set.new([
      FEATURES[:chat],
      FEATURES[:embeddings],
      FEATURES[:function_calling],
      FEATURES[:vision],
      :multimodal,
      :reasoning
    ])
  end
end
```

## Message Validation

The base class filters invalid messages before sending:

```ruby
def invalid_message?(message)
  role = extract_attribute(message, :role)

  case role
  when "user", "assistant"
    content_missing?(message)
  when "tool_call"
    metadata_missing?(message)
  when "tool_result"
    tool_result_invalid?(message)
  when "error"
    true  # Error messages never sent to LLM
  else
    true  # Unknown types are invalid
  end
end

# Helper methods for message validation
def extract_attribute(message, attr)
  message.respond_to?(attr) ? message.send(attr) : message[attr.to_s] || message[attr]
end

def content_missing?(message)
  content = extract_attribute(message, :content)
  content.blank?
end

def metadata_missing?(message)
  metadata = extract_attribute(message, :metadata)
  metadata.blank?
end

def tool_result_invalid?(message)
  metadata = extract_attribute(message, :metadata)
  metadata.blank? || metadata["id"].blank?
end
```

## Token Usage Tracking

```ruby
# Default implementation
def usage_keys
  self.class.const_defined?(:USAGE_KEYS) ? self.class::USAGE_KEYS : []
end

def total_usage_tokens(usage)
  usage.to_h["total_tokens"].to_i
end

# Provider-specific (e.g., Gemini)
class GeminiClient < LLMClient
  USAGE_KEYS = %w[promptTokenCount candidatesTokenCount].freeze

  def total_usage_tokens(usage)
    usage.to_h["totalTokenCount"].to_i
  end
end
```

## Abstract Methods Checklist

Subclasses must implement:

| Method | Purpose |
|--------|---------|
| `provider_config` | Returns provider-specific configuration hash |
| `build_parameters_for_provider` | Builds request payload |
| `build_url` | Constructs the API endpoint URL |
| `parse_response` | Parses JSON into LLMResponse |
| `self.supported_features` | Returns Set of supported features |

## Testing

```ruby
RSpec.describe LLMClient do
  describe LLMClient::LLMResponse do
    it "provides structured access to response data" do
      response = LLMClient::LLMResponse.new(
        "Hello!",
        [],
        "stop",
        { "total_tokens" => 10 }
      )

      expect(response.content).to eq("Hello!")
      expect(response.tool_calls).to be_empty
      expect(response.finish_reason).to eq("stop")
    end
  end

  describe ".supports_feature?" do
    it "returns false for base class" do
      expect(LLMClient.supports_feature?(:chat)).to be false
    end
  end
end
```

## Next Steps

- [Configuration System](03-configuration.md) - YAML-driven configuration
- [Provider Implementations](04-provider-clients.md) - Specific providers
