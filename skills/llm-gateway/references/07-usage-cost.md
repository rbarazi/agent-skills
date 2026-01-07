# Usage and Cost Tracking

## Purpose
Record token usage and compute costs using model pricing from configuration.

## Response Usage Structure

All LLM clients return usage in the response:

```ruby
response = client.create_message(
  model: "gpt-4o",
  messages: [{ role: "user", content: "Hello" }]
)

response.usage
# OpenAI: { "prompt_tokens" => 10, "completion_tokens" => 8, "total_tokens" => 18 }
# Anthropic: { "input_tokens" => 10, "output_tokens" => 8 }
# Gemini: { "promptTokenCount" => 10, "candidatesTokenCount" => 8, "totalTokenCount" => 18 }
```

## Normalizing Usage Keys

Each provider uses different keys; normalize them:

```ruby
# app/models/llm_client.rb
class LLMClient
  def usage_keys
    self.class.const_defined?(:USAGE_KEYS) ? self.class::USAGE_KEYS : []
  end

  def total_usage_tokens(usage)
    usage.to_h["total_tokens"].to_i
  end
end

# Provider-specific implementations
class OpenAIClient < LLMClient
  USAGE_KEYS = %w[prompt_tokens completion_tokens].freeze
end

class AnthropicClient < LLMClient
  USAGE_KEYS = %w[input_tokens output_tokens cache_read_input_tokens].freeze

  def total_usage_tokens(usage)
    usage.to_h["input_tokens"].to_i + usage.to_h["output_tokens"].to_i
  end
end

class GeminiClient < LLMClient
  USAGE_KEYS = %w[promptTokenCount candidatesTokenCount].freeze

  def total_usage_tokens(usage)
    usage.to_h["totalTokenCount"].to_i
  end
end
```

## Message Cost Calculation

Calculate cost based on model pricing:

```ruby
# app/models/message.rb
class Message < ApplicationRecord
  belongs_to :task
  store_accessor :metadata, :usage, :cost_cents

  def calculate_cost
    return 0 unless usage.present?

    provider = task.agent.account_llm.llm.name
    model = task.agent.model.presence || task.agent.account_llm.default_model
    pricing = LLMConfig.get_pricing(provider, model)

    return 0 if pricing.blank?

    input_tokens = extract_input_tokens
    output_tokens = extract_output_tokens

    input_cost = (input_tokens * pricing["input"].to_f) / 1000.0
    output_cost = (output_tokens * pricing["output"].to_f) / 1000.0

    ((input_cost + output_cost) * 100).round  # Cost in cents
  end

  def extract_input_tokens
    usage["prompt_tokens"] || usage["input_tokens"] || usage["promptTokenCount"] || 0
  end

  def extract_output_tokens
    usage["completion_tokens"] || usage["output_tokens"] || usage["candidatesTokenCount"] || 0
  end
end
```

## Task Usage Aggregation

Aggregate usage across all messages in a task:

```ruby
# app/models/task.rb
class Task < ApplicationRecord
  has_many :messages

  def total_usage
    messages.where.not(metadata: nil).sum do |message|
      usage = message.usage || {}
      extract_total_tokens(usage)
    end
  end

  def total_cost_cents
    messages.sum { |m| m.cost_cents || 0 }
  end

  def usage_summary
    {
      total_tokens: total_usage,
      total_cost_cents: total_cost_cents,
      total_cost_dollars: total_cost_cents / 100.0,
      message_count: messages.count,
      model: agent.model || agent.account_llm.default_model
    }
  end

  private

  def extract_total_tokens(usage)
    return usage["total_tokens"].to_i if usage.key?("total_tokens")
    return usage["totalTokenCount"].to_i if usage.key?("totalTokenCount")

    if usage.key?("input_tokens")
      return usage["input_tokens"].to_i + usage["output_tokens"].to_i
    end

    if usage.key?("prompt_tokens")
      return usage["prompt_tokens"].to_i + usage["completion_tokens"].to_i
    end

    0
  end
end
```

## Usage Tracking Service

Centralized service for tracking usage:

```ruby
# app/services/usage_tracking_service.rb
class UsageTrackingService
  def self.track(message, response)
    return unless response.usage.present?

    message.update!(
      metadata: message.metadata.merge(
        "usage" => response.usage,
        "model" => message.task.agent.model,
        "provider" => message.task.agent.account_llm.llm.name
      )
    )

    # Calculate and store cost
    cost = calculate_cost(message, response.usage)
    message.update!(cost_cents: cost) if cost > 0

    # Update account usage stats
    update_account_stats(message.task.account, response.usage, cost)
  end

  def self.calculate_cost(message, usage)
    provider = message.task.agent.account_llm.llm.name
    model = message.task.agent.model
    pricing = LLMConfig.get_pricing(provider, model)

    return 0 if pricing.blank?

    input = usage["prompt_tokens"] || usage["input_tokens"] || 0
    output = usage["completion_tokens"] || usage["output_tokens"] || 0

    input_cost = (input * pricing["input"].to_f) / 1000.0
    output_cost = (output * pricing["output"].to_f) / 1000.0

    ((input_cost + output_cost) * 100).round
  end

  def self.update_account_stats(account, usage, cost_cents)
    account.increment!(:total_tokens_used, extract_total(usage))
    account.increment!(:total_cost_cents, cost_cents)
  end

  private

  def self.extract_total(usage)
    usage["total_tokens"] ||
      usage["totalTokenCount"] ||
      (usage["input_tokens"].to_i + usage["output_tokens"].to_i)
  end
end
```

## Account Usage Statistics

Track usage at the account level:

```ruby
# app/models/account.rb
class Account < ApplicationRecord
  store_accessor :usage_stats,
    :total_tokens_used,
    :total_cost_cents,
    :tokens_by_provider,
    :tokens_by_model

  def usage_summary(period: 30.days)
    messages = Message.joins(task: :agent)
      .where(agents: { account_id: id })
      .where("messages.created_at > ?", period.ago)

    {
      period_days: period / 1.day,
      total_tokens: messages.sum { |m| m.usage&.dig("total_tokens") || 0 },
      total_cost_dollars: messages.sum { |m| m.cost_cents || 0 } / 100.0,
      by_model: messages.group_by { |m| m.metadata&.dig("model") }
        .transform_values { |msgs| msgs.sum { |m| m.cost_cents || 0 } / 100.0 }
    }
  end
end
```

## Cost Dashboard

```ruby
# app/controllers/admin/usage_controller.rb
class Admin::UsageController < ApplicationController
  def index
    @accounts = Account.all.map do |account|
      {
        account: account,
        usage: account.usage_summary(period: 30.days)
      }
    end

    @total_cost = @accounts.sum { |a| a[:usage][:total_cost_dollars] }
    @total_tokens = @accounts.sum { |a| a[:usage][:total_tokens] }
  end
end
```

## Testing

```ruby
RSpec.describe UsageTrackingService do
  describe ".calculate_cost" do
    let(:message) { create(:message) }
    let(:usage) { { "prompt_tokens" => 1000, "completion_tokens" => 500 } }

    before do
      allow(LLMConfig).to receive(:get_pricing)
        .and_return({ "input" => 0.01, "output" => 0.03 })
    end

    it "calculates cost in cents" do
      cost = described_class.calculate_cost(message, usage)

      # (1000 * 0.01 / 1000) + (500 * 0.03 / 1000) = 0.01 + 0.015 = 0.025
      # 0.025 * 100 = 2.5 cents, rounded to 3
      expect(cost).to eq(3)
    end
  end
end

RSpec.describe Message do
  describe "#calculate_cost" do
    it "returns 0 when no usage" do
      message = build(:message, metadata: {})
      expect(message.calculate_cost).to eq(0)
    end

    it "calculates cost from usage" do
      message = build(:message, metadata: {
        "usage" => { "prompt_tokens" => 100, "completion_tokens" => 50 }
      })

      allow(LLMConfig).to receive(:get_pricing)
        .and_return({ "input" => 0.01, "output" => 0.03 })

      expect(message.calculate_cost).to be > 0
    end
  end
end
```

## Next Steps

- [Rails Adapter](08-rails-adapter.md) - Rails-specific integration patterns
