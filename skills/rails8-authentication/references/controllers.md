# Authentication Controllers

## Authentication Concern

```ruby
# app/controllers/concerns/authentication.rb
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
    Current.session ||= find_session_by_header || find_session_by_cookie
  end

  def find_session_by_cookie
    Session.find_by(id: cookies.signed[:session_id])
  end

  # Bearer token support for API clients
  def find_session_by_header
    auth_header = request.headers["Authorization"]
    return if auth_header.blank? || !auth_header.start_with?("Bearer ")
    Session.find_by(id: auth_header.split(" ", 2).last)
  end

  def request_authentication
    session[:return_to_after_authenticating] = request.url
    redirect_to new_session_path
  end

  def after_authentication_url
    session.delete(:return_to_after_authenticating) || root_url
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

**Cookie Security:**
- `signed` - Cryptographically signed, tamper-proof
- `permanent` - 20-year expiry (persists across browser sessions)
- `httponly: true` - Not accessible via JavaScript (XSS protection)
- `same_site: :lax` - CSRF protection

## Sessions Controller

```ruby
# app/controllers/sessions_controller.rb
class SessionsController < ApplicationController
  allow_unauthenticated_access only: %i[new create]

  # Rate limiting: 10 attempts per 3 minutes
  rate_limit to: 10, within: 3.minutes, only: :create,
             with: -> { redirect_to new_session_url, alert: t("sessions.flash.rate_limit") }

  def new
  end

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
end
```

**Rails 8 Features:**
- `User.authenticate_by` - Built-in method from `has_secure_password`
- `rate_limit` - Built-in rate limiting (no gems needed)
- Returns `nil` on invalid credentials (prevents timing attacks)

## Application Controller

```ruby
# app/controllers/application_controller.rb
class ApplicationController < ActionController::Base
  include Authentication
  allow_browser versions: :modern
end
```

## API Sessions Controller

For JSON API authentication:

```ruby
# app/controllers/api/sessions_controller.rb
module Api
  class SessionsController < ApplicationController
    allow_unauthenticated_access only: [:create]
    skip_before_action :verify_authenticity_token

    def create
      if user = User.authenticate_by(params.permit(:email_address, :password))
        start_new_session_for user
        render json: { session_id: Current.session.id }
      else
        render json: { error: "Invalid credentials" }, status: :unauthorized
      end
    end
  end
end
```

**API Client Usage:**
```bash
# Login
curl -X POST https://api.example.com/api/session \
  -H "Content-Type: application/json" \
  -d '{"email_address": "user@example.com", "password": "secret"}'

# Response: {"session_id": "abc-123-xyz"}

# Authenticated requests
curl https://api.example.com/api/endpoint \
  -H "Authorization: Bearer abc-123-xyz"
```

## Controller Protection Patterns

```ruby
# Require authentication (default via concern)
class DashboardController < ApplicationController
  # Automatically requires authentication
end

# Allow some actions without authentication
class PagesController < ApplicationController
  allow_unauthenticated_access only: %i[home about]
end

# Skip authentication entirely
class PublicController < ApplicationController
  allow_unauthenticated_access
end
```
