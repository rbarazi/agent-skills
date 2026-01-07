# Provider Client Implementations

## Purpose
Implement provider-specific LLM clients that handle unique API formats, authentication, and response parsing for each provider.

## OpenAI Client

```ruby
# app/models/open_ai_client.rb
class OpenAIClient < LLMClient
  USAGE_KEYS = %w[prompt_tokens completion_tokens].freeze
  FUNCTION_TYPE = "function".freeze

  # Models requiring max_completion_tokens instead of max_tokens
  MAX_COMPLETION_TOKENS_MODELS = %w[
    o1 o1-preview o1-mini o3 o3-mini o3-pro o4-mini
    gpt-5 gpt-5-1 gpt-5-2 gpt-5-mini gpt-5-nano
  ].freeze

  def self.supported_features
    Set.new([
      FEATURES[:chat],
      FEATURES[:function_calling],
      FEATURES[:vision],
      :reasoning,
      :multimodal
    ])
  end

  def provider_config
    {
      base_url: "https://api.openai.com".freeze,
      default_headers: {
        'Authorization': "Bearer #{api_key}"
      },
      models: models,
      chat_url: "/v1/chat/completions",
      response_path: ["choices", 0, "delta", "content"],
      multi_type: true
    }.with_indifferent_access
  end

  def default_models
    LLMConfig.generate_default_models_for_client(:openai)
  end

  def self.list_models(api_key)
    data = make_models_request(
      "https://api.openai.com",
      "/v1/models",
      { "Authorization" => "Bearer #{api_key}" }
    )

    (data["data"] || []).map do |model|
      { id: model["id"], created: model["created"], owned_by: model["owned_by"] }
    end
  end

  protected

  def build_parameters_for_provider(system, model_config, limit, messages, tools)
    model_name = model_config[:model]
    token_param = requires_max_completion_tokens?(model_name) ? :max_completion_tokens : :max_tokens

    parameters = {
      token_param => limit,
      messages: [system_message(system), *messages.map { |m| format_message(m) }].compact,
      model: model_name
    }

    parameters[:tools] = tools.map { |t| format_tool(t) } if tools.present?
    parameters
  end

  def parse_response(json_response)
    LLMResponse.new(
      json_response.dig("choices", 0, "message", "content"),
      format_tool_calls(json_response.dig("choices", 0, "message", "tool_calls")),
      json_response.dig("choices", 0, "finish_reason"),
      json_response["usage"]
    )
  end

  def format_tool_calls(tool_calls)
    (tool_calls || []).map do |tool_call|
      {
        id: tool_call.dig("id"),
        name: tool_call.dig("function", "name"),
        arguments: parse_arguments(tool_call.dig("function", "arguments")),
        metadata: tool_call.deep_dup
      }
    end
  end

  def format_message(message)
    case message.role
    when "user", "assistant"
      { role: message.role, content: format_content(message) }
    when "tool_call"
      tool_call_data = build_tool_call_structure(message.metadata)
      { role: "assistant", tool_calls: [tool_call_data] }
    when "tool_result"
      { role: "tool", content: message.content || "", tool_call_id: message.metadata["id"] }
    end
  end

  def format_tool(tool_metadata)
    {
      type: FUNCTION_TYPE,
      function: {
        name: tool_metadata[:name],
        description: tool_metadata[:description],
        parameters: {
          type: "object",
          properties: tool_metadata.dig(:inputSchema, :properties),
          required: tool_metadata.dig(:inputSchema, :required)
        }
      }
    }
  end

  # Handle attachments (images, audio)
  def format_content(message)
    if message.attachments.present?
      content_parts = []
      content_parts << { type: "text", text: message.content } if message.content.present?
      content_parts.concat(format_attachments(message.attachments))
      content_parts
    else
      message.content.presence || ""
    end
  end

  def format_attachments(attachments)
    attachments.map do |attachment|
      if attachment.content_type.include?("image")
        {
          type: "image_url",
          image_url: {
            url: "data:#{attachment.content_type};base64,#{Base64.strict_encode64(attachment.download)}"
          }
        }
      end
    end.compact
  end

  private

  def requires_max_completion_tokens?(model_name)
    MAX_COMPLETION_TOKENS_MODELS.any? { |m| model_name.to_s.start_with?(m) }
  end

  def system_message(system)
    return nil if system.blank?
    { role: "system", content: system }
  end

  def build_tool_call_structure(metadata)
    {
      id: metadata["id"],
      type: FUNCTION_TYPE,
      function: {
        name: metadata["name"] || metadata.dig("function", "name"),
        arguments: (metadata["arguments"] || metadata.dig("function", "arguments") || {}).to_json
      }
    }
  end

  def build_url(model_name)
    provider_config[:chat_url]
  end

  def self.make_models_request(base_url, path, headers)
    conn = Faraday.new(url: base_url) { |f| f.adapter Faraday.default_adapter }
    response = conn.get(path) do |req|
      headers.each { |k, v| req.headers[k] = v }
    end
    JSON.parse(response.body)
  end
end
```

## Anthropic Client

```ruby
# app/models/anthropic_client.rb
class AnthropicClient < LLMClient
  USAGE_KEYS = %w[input_tokens output_tokens cache_read_input_tokens].freeze

  def self.supported_features
    Set.new([
      FEATURES[:chat],
      FEATURES[:function_calling],
      FEATURES[:vision],
      :multimodal,
      :computer_use,
      :extended_thinking
    ])
  end

  def provider_config
    {
      base_url: "https://api.anthropic.com".freeze,
      default_headers: {
        'x-api-key': api_key,
        'anthropic-version': "2023-06-01",
        'anthropic-beta': "messages-2023-12-15"
      },
      models: models,
      chat_url: "/v1/messages",
      response_path: %w[delta text],
      multi_type: true
    }.with_indifferent_access
  end

  def total_usage_tokens(usage)
    usage.to_h["input_tokens"].to_i + usage.to_h["output_tokens"].to_i
  end

  def default_models
    LLMConfig.generate_default_models_for_client(:anthropic)
  end

  # Provider-specific error extraction
  def extract_error_data(json_response)
    return {} unless json_response.is_a?(Hash)

    if json_response["type"] == "error" && json_response["error"].is_a?(Hash)
      json_response["error"]
    else
      super
    end
  end

  protected

  def build_parameters_for_provider(system, model_config, limit, messages, tools)
    parameters = {
      max_tokens: limit,
      messages: messages.map { |m| format_message(m) },
      model: model_config[:model]
    }
    parameters[:system] = system if system.present?
    parameters[:tools] = tools.map { |t| format_tool(t) } if tools.present?
    parameters
  end

  def parse_response(json_response)
    content = json_response["content"]&.find { |c| c["type"] == "text" }&.dig("text")
    tool_calls = format_tool_calls(json_response["content"]&.select { |c| c["type"] == "tool_use" })

    LLMResponse.new(content, tool_calls, json_response["stop_reason"], json_response["usage"])
  end

  def format_tool_calls(tool_calls)
    (tool_calls || []).map do |tool_call|
      {
        id: tool_call.dig("id"),
        name: tool_call.dig("name"),
        arguments: parse_arguments(tool_call.dig("input")),
        metadata: tool_call.deep_dup
      }
    end
  end

  def format_message(message)
    case message.role
    when "user", "assistant"
      { role: message.role, content: message.content }
    when "tool_call"
      { role: "assistant", content: [
        { type: "text", text: message.content },
        message.metadata
      ] }
    when "tool_result"
      { role: "user", content: [{
        type: "tool_result",
        tool_use_id: message.metadata["id"],
        content: message.content,
        is_error: message.content.include?("Error:")
      }] }
    end
  end

  def format_tool(tool_metadata)
    {
      name: tool_metadata[:name],
      description: tool_metadata[:description],
      input_schema: {
        type: "object",
        properties: tool_metadata.dig(:inputSchema, :properties),
        required: tool_metadata.dig(:inputSchema, :required)
      }
    }
  end
end
```

## Gemini Client

```ruby
# app/models/gemini_client.rb
class GeminiClient < LLMClient
  USAGE_KEYS = %w[promptTokenCount candidatesTokenCount].freeze
  MAX_EMBEDDING_BATCH_SIZE = 100
  EmbeddingResponse = Struct.new(:embeddings, :usage)

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

  def provider_config
    {
      base_url: "https://generativelanguage.googleapis.com".freeze,
      default_headers: { 'Content-Type': "application/json" },
      models: models,
      chat_url: "/v1beta/models/:model:generateContent",
      embedding_url: "/v1beta/models/:model:embedContent",
      embeddings_url: "/v1beta/models/:model:batchEmbedContents",
      response_path: ["candidates", 0, "content", "parts", 0, "text"],
      query_params: { key: :api_key }  # API key in query string
    }.with_indifferent_access
  end

  def total_usage_tokens(usage)
    usage.to_h["totalTokenCount"].to_i
  end

  def default_models
    LLMConfig.generate_default_models_for_client(:gemini)
  end

  # Embeddings support
  def create_embeddings(texts:, model: nil, input_type: nil)
    texts = normalize_texts(texts)
    raise ArgumentError, "texts array cannot have more than #{MAX_EMBEDDING_BATCH_SIZE} items" if texts.size > MAX_EMBEDDING_BATCH_SIZE

    model_key = model.presence || default_embedding_model_key
    model_config = provider_config[:models][model_key]
    raise ArgumentError, "Unknown model: #{model_key}." if model_config.blank?

    # Single text vs batch
    if texts.size == 1
      response = single_embedding_request(texts.first, model_config)
      EmbeddingResponse.new([response], build_embeddings_usage(response, texts))
    else
      response = batch_embedding_request(texts, model_config)
      embeddings = Array(response["embeddings"]).map { |item| item["values"] }
      EmbeddingResponse.new(embeddings, build_embeddings_usage(response, texts))
    end
  end

  def max_embedding_batch_size
    MAX_EMBEDDING_BATCH_SIZE
  end

  protected

  def build_parameters_for_provider(system, model_config, limit, messages, tools)
    params = {
      generationConfig: { maxOutputTokens: limit },
      contents: format_messages(messages)
    }

    if system.present?
      params[:system_instruction] = { parts: { text: system } }
    end

    if tools.present?
      params[:tools] = [{ functionDeclarations: tools.map { |t| format_tool(t) } }]
      params[:tool_config] = { functionCallingConfig: { mode: "auto" } }
    end

    params.merge(model_config.except(:token_limit, :pricing, :features))
  end

  def parse_response(json_response)
    content = json_response.dig("candidates", 0, "content", "parts", 0, "text")
    tool_calls = format_tool_calls(json_response.dig("candidates", 0, "content", "parts", 0, "functionCall"))

    LLMResponse.new(content, tool_calls, json_response.dig("candidates", 0, "finishReason"), json_response["usageMetadata"])
  end

  def format_tool_calls(function_call)
    return [] unless function_call

    [{
      name: function_call["name"],
      arguments: parse_arguments(function_call["args"]),
      metadata: function_call.deep_dup
    }]
  end

  def format_message(message)
    case message.role
    when "user"
      { role: "user", parts: format_content_parts(message) }
    when "assistant"
      { role: "model", parts: format_content_parts(message) }
    when "tool_call"
      { role: "model", parts: [{ functionCall: message.metadata }] }
    when "tool_result"
      {
        role: "user",
        parts: [{
          functionResponse: {
            name: message.metadata["name"],
            response: { name: message.metadata["name"], content: message.content }
          }
        }]
      }
    end
  end

  def format_content_parts(message)
    parts = []
    parts << { text: message.content } if message.content.present?

    if message.attachments.present?
      parts.concat(format_attachments(message.attachments))
    end

    parts.presence || [{ text: "" }]
  end

  def format_attachments(attachments)
    attachments.map do |attachment|
      if attachment.content_type.include?("image")
        {
          inlineData: {
            mimeType: attachment.content_type,
            data: Base64.strict_encode64(attachment.download)
          }
        }
      end
    end.compact
  end

  def format_messages(messages)
    messages.map { |m| format_message(m) }
  end

  def format_tool(tool_metadata)
    {
      name: tool_metadata[:name],
      description: tool_metadata[:description],
      parameters: {
        type: "object",
        properties: tool_metadata.dig(:inputSchema, :properties),
        required: tool_metadata.dig(:inputSchema, :required)
      }
    }
  end
end
```

## Key Differences by Provider

| Aspect | OpenAI | Anthropic | Gemini |
|--------|--------|-----------|--------|
| Auth Header | `Authorization: Bearer` | `x-api-key` | Query param `?key=` |
| System Message | In messages array | Separate `system` param | `system_instruction` |
| Tool Format | `{ type: "function", function: {...} }` | `{ name, input_schema }` | `{ functionDeclarations: [...] }` |
| Tool Calls | `message.tool_calls` | `content[].type: "tool_use"` | `parts[].functionCall` |
| Tool Results | `role: "tool"` | `role: "user", type: "tool_result"` | `role: "user", functionResponse` |
| Token Param | `max_tokens` or `max_completion_tokens` | `max_tokens` | `maxOutputTokens` |
| Images | `image_url` with data URL | `image` in content | `inlineData` |

## Testing

```ruby
RSpec.describe OpenAIClient do
  let(:client) { described_class.new(api_key: "test-key") }

  describe "#create_message" do
    it "builds correct parameters" do
      # Mock the HTTP request
      stub_request(:post, "https://api.openai.com/v1/chat/completions")
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
  end
end
```

## Next Steps

- [Error Handling](05-error-handling.md) - Structured errors and retry logic
