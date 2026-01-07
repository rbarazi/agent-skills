# Session Security Patterns

## Session Limits

Limit concurrent sessions per user:

```ruby
class User < ApplicationRecord
  MAX_SESSIONS = 5

  def enforce_session_limit!
    excess = sessions.order(created_at: :desc).offset(MAX_SESSIONS)
    excess.destroy_all
  end
end

# In authentication concern
def start_new_session_for(user)
  user.sessions.create!(
    user_agent: request.user_agent,
    ip_address: request.remote_ip
  ).tap do |session|
    user.enforce_session_limit!
    # ...cookie setup
  end
end
```

## Session Expiry

Auto-expire old sessions:

```ruby
class Session < ApplicationRecord
  SESSION_TTL = 30.days

  scope :expired, -> { where('created_at < ?', SESSION_TTL.ago) }
  scope :active, -> { where('created_at >= ?', SESSION_TTL.ago) }

  def expired?
    created_at < SESSION_TTL.ago
  end
end

# In find_session_by_cookie
def find_session_by_cookie
  session = Session.find_by(id: cookies.signed[:session_id])
  return nil if session&.expired?
  session
end

# Background job to clean up
class CleanupExpiredSessionsJob < ApplicationJob
  def perform
    Session.expired.delete_all
  end
end
```

## Session Refresh

Extend session on activity:

```ruby
# In authentication concern
def resume_session
  Current.session ||= find_session_by_header || find_session_by_cookie
  Current.session&.touch_activity!
  Current.session
end
```

## IP-Based Security

Monitor IP address changes:

```ruby
class Session < ApplicationRecord
  def ip_changed?(current_ip)
    ip_address != current_ip
  end
end

# In authentication concern
def resume_session
  session = find_session_by_header || find_session_by_cookie

  if session&.ip_changed?(request.remote_ip)
    Rails.logger.warn "Session #{session.id} IP changed from #{session.ip_address} to #{request.remote_ip}"
    # For high security, invalidate the session:
    # session.destroy
    # return nil
  end

  Current.session = session
end
```

## Cookie Security Settings

```ruby
cookies.signed.permanent[:session_id] = {
  value: session.id,
  httponly: true,     # Prevents JavaScript access (XSS protection)
  same_site: :lax,    # CSRF protection
  secure: Rails.env.production?  # HTTPS only in production
}
```

## Rate Limiting

```ruby
class SessionsController < ApplicationController
  rate_limit to: 10, within: 3.minutes, only: :create,
             with: -> { redirect_to new_session_url, alert: t("sessions.flash.rate_limit") }
end
```

## Session Fixation Prevention

Always create a new session after authentication:

```ruby
def start_new_session_for(user)
  # Create new database session
  user.sessions.create!(...)
  # Regenerate Rails session to prevent fixation
  reset_session
end
```

## Session Activity Throttling

Avoid excessive database writes:

```ruby
class Session < ApplicationRecord
  def touch_activity!
    # Only update if more than 5 minutes since last update
    return if last_active_at && last_active_at > 5.minutes.ago
    update_column(:last_active_at, Time.current)
  end
end
```

## New Login Notifications

Alert users of new device logins:

```ruby
class Session < ApplicationRecord
  after_create :notify_new_login

  private

  def notify_new_login
    return if user.sessions.count <= 1  # Skip for first session
    SessionMailer.new_login(self).deliver_later
  end
end
```

## Suspicious Activity Detection

```ruby
class Session < ApplicationRecord
  after_create :check_suspicious_activity

  private

  def check_suspicious_activity
    recent_sessions = user.sessions
      .where('created_at > ?', 1.hour.ago)
      .where.not(ip_address: ip_address)

    if recent_sessions.exists?
      SecurityMailer.suspicious_login(self).deliver_later
    end
  end
end
```

## Session Audit Log

```ruby
class SessionAudit < ApplicationRecord
  belongs_to :session, optional: true
  belongs_to :user

  enum action: {
    created: 'created',
    destroyed: 'destroyed',
    expired: 'expired',
    ip_changed: 'ip_changed'
  }
end

class Session < ApplicationRecord
  after_create { audit!(:created) }
  after_destroy { audit!(:destroyed) }

  def audit!(action)
    SessionAudit.create!(
      session: self,
      user: user,
      action: action,
      ip_address: ip_address,
      user_agent: user_agent,
      metadata: { timestamp: Time.current.iso8601 }
    )
  end
end
```
