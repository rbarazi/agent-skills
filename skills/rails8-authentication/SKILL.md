---
name: rails8-authentication
description: Implement Rails 8 built-in authentication with has_secure_password, session cookies, and the Authentication concern. Use when building login/logout functionality, session-based auth, or user authentication systems in Rails 8+ applications.
---

# Rails 8 Built-in Authentication

Lightweight authentication using Rails 8's built-in features. No Devise or external gems required.

## Quick Start

1. Generate models: User (with `has_secure_password`) and Session
2. Create Authentication concern for controllers
3. Build SessionsController for login/logout
4. Add Current model for request-scoped attributes

## Core Components

| Component | Purpose | Reference |
|-----------|---------|-----------|
| User model | Password hashing with bcrypt | [models.md](references/models.md) |
| Session model | Track active sessions | [models.md](references/models.md) |
| Current model | Request-scoped attributes | [models.md](references/models.md) |
| Authentication concern | Controller authentication | [controllers.md](references/controllers.md) |
| SessionsController | Login/logout endpoints | [controllers.md](references/controllers.md) |
| Login view | Sign-in form | [views.md](references/views.md) |
| Migrations | Database schema | [migrations.md](references/migrations.md) |
| I18n translations | User-facing strings | [i18n.md](references/i18n.md) |

## Minimal Implementation

### User Model

```ruby
class User < ApplicationRecord
  has_secure_password
  has_many :sessions, dependent: :destroy
  normalizes :email_address, with: ->(e) { e.strip.downcase }
  validates :email_address, presence: true, uniqueness: { case_sensitive: false }
end
```

### Session Model

```ruby
class Session < ApplicationRecord
  belongs_to :user
end
```

### Current Model

```ruby
class Current < ActiveSupport::CurrentAttributes
  attribute :session
  delegate :user, to: :session, allow_nil: true
end
```

### Authentication Concern

```ruby
module Authentication
  extend ActiveSupport::Concern
  included do
    before_action :require_authentication
  end

  class_methods do
    def allow_unauthenticated_access(**options)
      skip_before_action :require_authentication, **options
    end
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

  def request_authentication
    session[:return_to_after_authenticating] = request.url
    redirect_to new_session_path
  end

  def start_new_session_for(user)
    user.sessions.create!(user_agent: request.user_agent, ip_address: request.remote_ip).tap do |session|
      Current.session = session
      cookies.signed.permanent[:session_id] = { value: session.id, httponly: true, same_site: :lax }
    end
  end

  def terminate_session
    Current.session.destroy
    cookies.delete(:session_id)
  end
end
```

### Sessions Controller

```ruby
class SessionsController < ApplicationController
  allow_unauthenticated_access only: %i[new create]
  rate_limit to: 10, within: 3.minutes, only: :create,
             with: -> { redirect_to new_session_url, alert: t("sessions.flash.rate_limit") }

  def new; end

  def create
    if user = User.authenticate_by(params.permit(:email_address, :password))
      start_new_session_for user
      redirect_to after_authentication_url, notice: t("sessions.flash.create.success")
    else
      redirect_to new_session_path, alert: t("sessions.flash.create.error")
    end
  end

  def destroy
    terminate_session
    redirect_to new_session_path, notice: t("sessions.flash.destroy.success")
  end

  private

  def after_authentication_url
    session.delete(:return_to_after_authenticating) || root_url
  end
end
```

### Routes

```ruby
Rails.application.routes.draw do
  resource :session  # new, create, destroy
end
```

## Security Features

- **Signed cookies**: Tamper-proof session storage
- **HttpOnly**: Prevents JavaScript access (XSS protection)
- **SameSite: :lax**: CSRF protection
- **Rate limiting**: Built-in brute force protection
- **bcrypt hashing**: Secure password storage

## Detailed References

For complete implementation details:

- **[models.md](references/models.md)**: Full model code with validations and associations
- **[controllers.md](references/controllers.md)**: Complete controller implementations with Bearer token support
- **[views.md](references/views.md)**: Login form templates with proper autocomplete attributes
- **[migrations.md](references/migrations.md)**: Database migrations for users and sessions
- **[i18n.md](references/i18n.md)**: Translation keys for all user-facing strings
- **[security.md](references/security.md)**: Security best practices and considerations
