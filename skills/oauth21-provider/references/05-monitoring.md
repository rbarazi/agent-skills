# OAuth Monitoring and Audit

## Purpose
Track OAuth events, monitor token usage, detect suspicious activity, and maintain system health.

## Monitoring Service

```ruby
# app/services/oauth_monitoring_service.rb
class OAuthMonitoringService
  # Track events via ActiveSupport::Notifications
  def self.track_event(event_type, oauth_client_or_token, user_or_details = nil, **extra_details)
    oauth_client, user, details = extract_event_params(oauth_client_or_token, user_or_details, extra_details)

    ActiveSupport::Notifications.instrument("oauth.#{event_type}",
      oauth_client_id: oauth_client&.id,
      user_id: user&.id,
      **details
    )
  end

  # Track token usage
  def self.track_token_usage(access_token, request)
    track_event(:token_used, access_token,
      endpoint: request.path,
      method: request.method,
      ip: request.remote_ip,
      user_agent: request.user_agent
    )

    access_token.update!(
      token_metadata: access_token.token_metadata.merge(
        "last_used_at" => Time.current.to_f
      )
    )
  end

  # Track scope validation
  def self.track_scope_validation(session, required_scopes, success)
    event_type = success ? :scope_validation_success : :scope_violation
    track_event(event_type, session.oauth_client, session.access_token&.user,
      required_scopes: required_scopes,
      available_scopes: session.available_scopes,
      success: success
    )
  end

  # Alert suspicious activity
  def self.alert_suspicious_activity(message, details = {})
    track_event(:suspicious_activity, nil, nil, message: message, **details)
    Rails.logger.warn("OAuth Security Alert: #{message} - #{details.inspect}")
  end

  # Statistics
  def self.token_usage_stats(time_range = 24.hours.ago..Time.current)
    tokens = OAuthAccessToken.where(created_at: time_range)

    {
      total_tokens_issued: tokens.count,
      active_tokens: tokens.where("expires_at > ?", Time.current).count,
      expired_tokens: tokens.where("expires_at <= ?", Time.current).count,
      tokens_by_client: tokens.joins(:oauth_client).group("oauth_clients.name").count
    }
  end

  # Cleanup methods
  def self.cleanup_expired_tokens
    TokenService.cleanup_expired_tokens
  end

  def self.cleanup_expired_sessions
    MCP::ClientSession.where("expires_at < ?", Time.current).delete_all
  end

  private

  def self.extract_event_params(oauth_client_or_token, user_or_details, extra_details)
    case oauth_client_or_token
    when OAuthAccessToken
      [oauth_client_or_token.oauth_client, oauth_client_or_token.user, user_or_details.to_h.merge(extra_details)]
    else
      user = user_or_details.is_a?(User) ? user_or_details : nil
      details = user_or_details.is_a?(Hash) ? user_or_details : {}
      [oauth_client_or_token, user, details.merge(extra_details)]
    end
  end
end
```

## OAuth Event Model

```ruby
# app/models/oauth_event.rb
class OAuthEvent < ApplicationRecord
  belongs_to :oauth_client, optional: true
  belongs_to :user, optional: true

  validates :event_type, presence: true

  scope :recent, -> { where("created_at > ?", 24.hours.ago) }
  scope :security_events, -> { where(event_type: %w[scope_violation auth_failed suspicious_activity]) }

  def self.cleanup(older_than = 90.days.ago)
    where("created_at < ?", older_than).delete_all
  end
end
```

## Event Subscriber

```ruby
# app/services/oauth_event_subscriber.rb
class OAuthEventSubscriber
  def self.subscribe!
    ActiveSupport::Notifications.subscribe(/^oauth\./) do |name, start, finish, id, payload|
      event_type = name.sub("oauth.", "")

      OAuthEvent.create(
        event_type: event_type,
        oauth_client_id: payload[:oauth_client_id],
        user_id: payload[:user_id],
        event_data: payload.except(:oauth_client_id, :user_id)
      )
    end
  end
end

# config/initializers/oauth_event_subscriber.rb
OAuthEventSubscriber.subscribe!
```

## Migration

```ruby
# db/migrate/create_oauth_events.rb
class CreateOAuthEvents < ActiveRecord::Migration[7.0]
  def change
    create_table :oauth_events, id: :uuid do |t|
      t.references :oauth_client, type: :uuid, foreign_key: true
      t.references :user, type: :uuid, foreign_key: true
      t.string :event_type, null: false
      t.jsonb :event_data, null: false, default: {}

      t.timestamps

      t.index :event_type
      t.index :created_at
    end
  end
end
```

## Rake Tasks

```ruby
# lib/tasks/oauth.rake
namespace :oauth do
  desc "Show OAuth statistics"
  task stats: :environment do
    stats = OAuthMonitoringService.token_usage_stats

    puts "OAuth Statistics (Last 24 hours)"
    puts "================================"
    puts "Total tokens issued: #{stats[:total_tokens_issued]}"
    puts "Active tokens: #{stats[:active_tokens]}"
    puts "Expired tokens: #{stats[:expired_tokens]}"
    puts "\nBy Client:"
    stats[:tokens_by_client].each do |client, count|
      puts "  #{client}: #{count}"
    end
  end

  desc "Clean up expired OAuth data"
  task cleanup: :environment do
    token_result = OAuthMonitoringService.cleanup_expired_tokens
    session_count = OAuthMonitoringService.cleanup_expired_sessions
    event_count = OAuthEvent.cleanup

    puts "Cleanup Results:"
    puts "  Tokens: #{token_result[:access_tokens_removed]}"
    puts "  Codes: #{token_result[:authorization_codes_removed]}"
    puts "  Sessions: #{session_count}"
    puts "  Events: #{event_count}"
  end

  desc "Show security events"
  task security_report: :environment do
    events = OAuthEvent.security_events.recent

    puts "Security Events (Last 24 hours): #{events.count}"
    events.find_each do |event|
      puts "  [#{event.created_at}] #{event.event_type}: #{event.event_data}"
    end
  end
end
```

## Integration in Controllers

```ruby
# In protected controllers
class ApiController < ApplicationController
  include OAuthAuthentication

  before_action :track_api_usage

  private

  def track_api_usage
    return unless oauth_authenticated?
    OAuthMonitoringService.track_token_usage(@current_access_token, request)
  end
end
```

## Dashboard (Optional)

```ruby
# app/controllers/admin/oauth_controller.rb
module Admin
  class OAuthController < ApplicationController
    def dashboard
      @stats = OAuthMonitoringService.token_usage_stats
      @security_events = OAuthEvent.security_events.recent.limit(20)
      @clients = OAuthClient.active.includes(:oauth_access_tokens)
    end
  end
end
```

## Testing

```ruby
RSpec.describe OAuthMonitoringService do
  describe ".track_token_usage" do
    it "updates last_used_at" do
      token = create(:oauth_access_token)
      request = double(path: "/api/data", method: "GET", remote_ip: "127.0.0.1", user_agent: "Test")

      freeze_time do
        described_class.track_token_usage(token, request)

        token.reload
        expect(token.token_metadata["last_used_at"]).to eq(Time.current.to_f)
      end
    end
  end

  describe ".token_usage_stats" do
    it "returns correct statistics" do
      create_list(:oauth_access_token, 3)
      create(:oauth_access_token, expires_at: 1.hour.ago)

      stats = described_class.token_usage_stats

      expect(stats[:total_tokens_issued]).to eq(4)
      expect(stats[:active_tokens]).to eq(3)
      expect(stats[:expired_tokens]).to eq(1)
    end
  end
end
```

## Best Practices

1. **Retain events**: Keep security events for 90+ days for audit
2. **Alert on anomalies**: Monitor for unusual token issuance rates
3. **Regular cleanup**: Run cleanup tasks hourly
4. **Log IP addresses**: Track token usage locations
5. **Dashboard monitoring**: Build admin dashboard for real-time visibility
