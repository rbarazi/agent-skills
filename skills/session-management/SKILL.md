---
name: session-management
description: Implement database-backed session management with cookie handling, audit trails, and multiple device support. Use when building authentication systems that need session tracking, device management, or security audit capabilities.
---

# Session Management Pattern

Database-backed session management for Rails with audit trails, multi-device support, and session revocation.

## When to Use

- Building authentication with session tracking
- Implementing "sign out everywhere" functionality
- Adding device/session management to settings
- Supporting Bearer token authentication for APIs
- Creating security audit trails

## Why Database-Backed Sessions?

| Feature | Cookie-Only | Database-Backed |
|---------|-------------|-----------------|
| Session revocation | No | Yes |
| "Sign out everywhere" | No | Yes |
| Audit trail | No | Yes |
| Multiple device view | No | Yes |
| API token support | Limited | Full |

## Quick Start

### 1. Session Model

```ruby
# app/models/session.rb
class Session < ApplicationRecord
  belongs_to :user

  scope :active, -> { where('created_at > ?', 30.days.ago) }
  scope :recent, -> { order(created_at: :desc) }
end
```

### 2. Migration

```ruby
class CreateSessions < ActiveRecord::Migration[8.0]
  def change
    create_table :sessions, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.string :ip_address
      t.string :user_agent
      t.timestamps
    end
  end
end
```

### 3. Authentication Concern

```ruby
# app/controllers/concerns/authentication.rb
module Authentication
  extend ActiveSupport::Concern

  included do
    before_action :require_authentication
  end

  private

  def require_authentication
    resume_session || request_authentication
  end

  def resume_session
    Current.session ||= find_session_by_cookie
  end

  def find_session_by_cookie
    Session.find_by(id: cookies.signed[:session_id])
  end

  def start_new_session_for(user)
    user.sessions.create!(
      user_agent: request.user_agent,
      ip_address: request.remote_ip
    ).tap do |session|
      Current.session = session
      cookies.signed.permanent[:session_id] = {
        value: session.id,
        httponly: true,
        same_site: :lax
      }
    end
  end

  def terminate_session
    Current.session.destroy
    cookies.delete(:session_id)
  end
end
```

## Cookie Security

- `signed` - Cryptographically signed, tamper-proof
- `permanent` - 20-year expiry
- `httponly: true` - XSS protection
- `same_site: :lax` - CSRF protection

## Reference Files

For complete implementation details:

- **[models.md](references/models.md)** - Session model with activity tracking, device detection
- **[controllers.md](references/controllers.md)** - Sessions controller, settings controller, API controller
- **[views.md](references/views.md)** - Session management UI
- **[i18n.md](references/i18n.md)** - Translation keys
- **[security.md](references/security.md)** - Session limits, expiry, IP monitoring
- **[testing.md](references/testing.md)** - Session factories and specs
