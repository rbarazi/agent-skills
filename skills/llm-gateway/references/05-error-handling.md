# LLM Error Handling

## Purpose
Provide structured error handling with retry logic for rate limits and standardized error types across all LLM providers.

## Error Classes

```ruby
# In LLMClient base class
class LLMClient
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
end
```

## Retry Logic

```ruby
class LLMClient
  RETRY_LIMIT = 2
  RETRY_DELAY = 1

  private

  def execute_request_with_retry(request_data)
    attempts = 0

    begin
      attempts += 1
      response = make_http_request(request_data)
      process_response(response)
    rescue RateLimitError => e
      if attempts <= RETRY_LIMIT
        logger.warn("Rate limited, retrying in #{RETRY_DELAY} seconds (attempt #{attempts})")
        sleep RETRY_DELAY
        retry
      else
        logger.error("Rate limit retries exceeded: #{e.message}")
        raise
      end
    end
  end
end
```

## Error Detection

```ruby
class LLMClient
  private

  def api_error?(response, json_response)
    # Check JSON structure for API-level errors first
    return true if json_response.is_a?(Hash) && json_error?(json_response)

    # Then check HTTP status
    return true if http_error_status?(response)

    # Finally check for missing expected content
    return false unless json_response.is_a?(Hash)
    missing_expected_content?(json_response)
  end

  def json_error?(json_response)
    json_response.key?("error") ||
      json_response["type"] == "error" ||
      json_response["success"] == false ||
      json_response.key?("error_message") ||
      json_response.key?("errors")
  end

  def http_error_status?(response)
    response.status >= 400
  end

  def missing_expected_content?(json_response)
    expected_success_keys = ["choices", "data", "content", "response", "result", "candidates"]
    return false if json_error?(json_response)
    expected_success_keys.none? { |key| json_response.key?(key) }
  end
end
```

## Rate Limit Detection

```ruby
class LLMClient
  private

  def rate_limited?(response, json_response)
    # HTTP 429 status
    return true if response.status == 429

    return false unless json_response.is_a?(Hash)

    error_data = extract_error_data(json_response)
    rate_limit_types = ["rate_limit_error", "rate_limit", "quota_exceeded", "too_many_requests"]

    # Check error type
    return true if rate_limit_types.include?(error_data["type"])

    # Check message content for rate limit keywords
    message = extract_message_safely(error_data)
    return false unless message.is_a?(String)

    message_lower = message.downcase
    rate_limit_keywords = [
      "rate limit", "rate_limit", "too many requests",
      "quota", "exceeded", "throttle", "throttled"
    ]

    rate_limit_keywords.any? { |keyword| message_lower.include?(keyword) }
  end
end
```

## Error Information Extraction

```ruby
class LLMClient
  private

  def extract_error_info(response, json_response)
    # JSON-level errors take priority over HTTP status
    if json_response.is_a?(Hash) && json_error?(json_response)
      error_data = extract_error_data(json_response)
      message = extract_message_safely(error_data)
      return {
        message: message || "Unknown API error",
        type: error_data["type"] || error_data["error_type"],
        code: error_data["code"] || error_data["error_code"],
        param: error_data["param"] || error_data["parameter"]
      }
    end

    # HTTP-level errors as fallback
    if http_error_status?(response)
      return {
        message: "HTTP #{response.status}: #{http_error_message(response, json_response)}",
        type: "http_error",
        code: response.status.to_s,
        param: nil
      }
    end

    # Fallback
    { message: "Unknown API error", type: nil, code: nil, param: nil }
  end

  def extract_error_data(json_response)
    return {} unless json_response.is_a?(Hash)

    if json_response["error"].is_a?(Hash)
      json_response["error"]
    elsif json_response.key?("error_message") || json_response.key?("error_code")
      json_response
    else
      json_response
    end
  end

  def extract_message_safely(error_data)
    return nil unless error_data.is_a?(Hash)

    message_fields = ["message", "error_message", "detail", "error"]

    message_fields.each do |field|
      value = error_data[field]
      next unless value.present?

      if value.is_a?(Hash)
        nested_message = value["message"] || value["error_message"] || value["detail"]
        return nested_message if nested_message.is_a?(String) && nested_message.present?
      elsif value.is_a?(String)
        return value
      end
    end

    nil
  end

  def http_error_message(response, json_response)
    # Try to extract message from JSON response body
    if json_response.is_a?(Hash)
      message = extract_message_safely(json_response)
      return message if message.present?
    end

    # Fall back to HTTP status reason phrase
    case response.status
    when 400 then "Bad Request"
    when 401 then "Unauthorized"
    when 403 then "Forbidden"
    when 404 then "Not Found"
    when 429 then "Too Many Requests"
    when 500 then "Internal Server Error"
    when 502 then "Bad Gateway"
    when 503 then "Service Unavailable"
    else "Request Failed"
    end
  end
end
```

## Provider-Specific Error Handling

```ruby
# Anthropic has unique error format
class AnthropicClient < LLMClient
  def extract_error_data(json_response)
    return {} unless json_response.is_a?(Hash)

    # Anthropic: { "type": "error", "error": { "type": "...", "message": "..." } }
    if json_response["type"] == "error" && json_response["error"].is_a?(Hash)
      json_response["error"]
    else
      super
    end
  end

  def missing_expected_content?(json_response)
    return false if json_response.key?("content")
    super
  end
end

# Gemini checks for candidates
class GeminiClient < LLMClient
  def missing_expected_content?(json_response)
    return false if json_response.key?("candidates")
    super
  end
end
```

## Error Handling Flow

```ruby
class LLMClient
  private

  def handle_api_error(response, json_response)
    error_info = extract_error_info(response, json_response)

    if rate_limited?(response, json_response)
      raise RateLimitError, error_info[:message]
    else
      raise APIError.new(
        error_info[:message],
        error_type: error_info[:type],
        error_code: error_info[:code],
        error_param: error_info[:param]
      )
    end
  end

  def process_response(response)
    json_response = try_parse_json(response.body)

    if api_error?(response, json_response)
      handle_api_error(response, json_response)
    end

    parse_response(json_response)
  end
end
```

## Usage in Application Code

```ruby
class ChatService
  def send_message(content)
    client = LLMGateway.create(provider: :openai, api_key: api_key)

    client.create_message(
      system: "You are helpful",
      model: "gpt-4o",
      limit: 1000,
      messages: [{ role: "user", content: content }]
    )
  rescue LLMClient::RateLimitError => e
    # Already retried RETRY_LIMIT times
    logger.warn("Rate limit exceeded after retries: #{e.message}")
    ErrorResponse.new("Please try again in a moment")
  rescue LLMClient::APIError => e
    logger.error("LLM API Error: #{e.message} (type: #{e.error_type}, code: #{e.error_code})")

    case e.error_type
    when "invalid_api_key"
      ErrorResponse.new("API key is invalid. Please check your configuration.")
    when "model_not_found"
      ErrorResponse.new("The requested model is not available.")
    else
      ErrorResponse.new("An error occurred: #{e.message}")
    end
  rescue StandardError => e
    logger.error("Unexpected error: #{e.message}")
    ErrorResponse.new("An unexpected error occurred")
  end
end
```

## Common Error Types by Provider

| Provider | Error Type | Meaning |
|----------|------------|---------|
| OpenAI | `invalid_api_key` | API key is invalid |
| OpenAI | `rate_limit_exceeded` | Rate limit hit |
| OpenAI | `model_not_found` | Model doesn't exist |
| OpenAI | `context_length_exceeded` | Input too long |
| Anthropic | `authentication_error` | Invalid credentials |
| Anthropic | `rate_limit_error` | Rate limit hit |
| Anthropic | `overloaded_error` | Server overloaded |
| Gemini | `INVALID_ARGUMENT` | Bad request |
| Gemini | `RESOURCE_EXHAUSTED` | Quota exceeded |

## Testing Error Handling

```ruby
RSpec.describe LLMClient do
  let(:client) { OpenAIClient.new(api_key: "test-key") }

  describe "rate limit handling" do
    it "retries on rate limit" do
      # First call fails with rate limit
      stub_request(:post, /openai/)
        .to_return(status: 429, body: { error: { message: "Rate limit exceeded" } }.to_json)
        .then
        .to_return(body: {
          choices: [{ message: { content: "Hello!" }, finish_reason: "stop" }],
          usage: { total_tokens: 10 }
        }.to_json)

      response = client.create_message(
        model: "gpt-4o",
        messages: [{ role: "user", content: "Hi" }]
      )

      expect(response.content).to eq("Hello!")
    end

    it "raises after max retries" do
      stub_request(:post, /openai/)
        .to_return(status: 429, body: { error: { message: "Rate limit exceeded" } }.to_json)

      expect {
        client.create_message(model: "gpt-4o", messages: [{ role: "user", content: "Hi" }])
      }.to raise_error(LLMClient::RateLimitError)
    end
  end

  describe "API error handling" do
    it "raises APIError with structured info" do
      stub_request(:post, /openai/)
        .to_return(status: 400, body: {
          error: {
            message: "Invalid model",
            type: "invalid_request_error",
            code: "model_not_found"
          }
        }.to_json)

      expect {
        client.create_message(model: "invalid-model", messages: [])
      }.to raise_error(LLMClient::APIError) do |error|
        expect(error.message).to include("Invalid model")
        expect(error.error_type).to eq("invalid_request_error")
        expect(error.error_code).to eq("model_not_found")
      end
    end
  end
end
```

## Best Practices

1. **Always handle both error types**: `RateLimitError` and `APIError`
2. **Log error details**: Include `error_type`, `error_code` for debugging
3. **User-friendly messages**: Don't expose raw API errors to users
4. **Retry configuration**: Adjust `RETRY_LIMIT` and `RETRY_DELAY` per use case
5. **Circuit breaker**: Consider adding circuit breaker for persistent failures
