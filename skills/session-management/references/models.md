# Session Management Models

## Session Model

```ruby
# app/models/session.rb
class Session < ApplicationRecord
  belongs_to :user

  scope :active, -> { where('created_at > ?', 30.days.ago) }
  scope :expired, -> { where('created_at <= ?', 30.days.ago) }
  scope :recent, -> { order(created_at: :desc) }
end
```

## Extended Session Model

With activity tracking and device detection:

```ruby
# app/models/session.rb
class Session < ApplicationRecord
  SESSION_TTL = 30.days

  belongs_to :user

  scope :active, -> { where('created_at > ?', SESSION_TTL.ago) }
  scope :expired, -> { where('created_at <= ?', SESSION_TTL.ago) }
  scope :recent, -> { order(created_at: :desc) }

  # Update activity timestamp (throttled to avoid DB writes)
  def touch_activity!
    return if last_active_at && last_active_at > 5.minutes.ago
    update_column(:last_active_at, Time.current)
  end

  # Check if session is expired
  def expired?
    created_at < SESSION_TTL.ago
  end

  # Check if session is stale
  def stale?
    last_active_at.nil? || last_active_at < SESSION_TTL.ago
  end

  # Human-readable device info
  def device_name
    return 'Unknown' if user_agent.blank?

    case user_agent
    when /iPhone/i then 'iPhone'
    when /iPad/i then 'iPad'
    when /Android/i then 'Android'
    when /Mac OS X/i then 'Mac'
    when /Windows/i then 'Windows PC'
    when /Linux/i then 'Linux'
    else 'Unknown Device'
    end
  end

  def browser_name
    return 'Unknown' if user_agent.blank?

    case user_agent
    when /Chrome/i then 'Chrome'
    when /Safari/i then 'Safari'
    when /Firefox/i then 'Firefox'
    when /Edge/i then 'Edge'
    else 'Unknown Browser'
    end
  end

  def ip_changed?(current_ip)
    ip_address != current_ip
  end
end
```

## User Model Additions

```ruby
# app/models/user.rb
class User < ApplicationRecord
  MAX_SESSIONS = 5

  has_many :sessions, dependent: :destroy
  has_secure_password

  # Revoke all sessions (sign out everywhere)
  def revoke_all_sessions!
    sessions.destroy_all
  end

  # Revoke all sessions except current
  def revoke_other_sessions!(current_session)
    sessions.where.not(id: current_session.id).destroy_all
  end

  # Limit concurrent sessions
  def enforce_session_limit!
    excess = sessions.order(created_at: :desc).offset(MAX_SESSIONS)
    excess.destroy_all
  end
end
```

## Extended Migration

```ruby
class CreateSessions < ActiveRecord::Migration[8.0]
  def change
    create_table :sessions, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.string :ip_address
      t.string :user_agent
      t.string :device_type       # mobile, desktop, tablet
      t.string :browser           # Chrome, Safari, Firefox
      t.string :os                # macOS, Windows, iOS
      t.string :country           # From IP geolocation
      t.string :city              # From IP geolocation
      t.datetime :last_active_at  # Track activity
      t.timestamps
    end

    add_index :sessions, :created_at
    add_index :sessions, :last_active_at
  end
end
```

## Session Notifications

```ruby
class Session < ApplicationRecord
  after_create :notify_new_login

  private

  def notify_new_login
    return if user.sessions.count <= 1
    SessionMailer.new_login(self).deliver_later
  end
end
```
