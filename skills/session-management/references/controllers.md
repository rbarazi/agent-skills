# Session Management Controllers

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
    Current.session&.touch_activity!
    Current.session
  end

  def find_session_by_cookie
    session = Session.find_by(id: cookies.signed[:session_id])
    return nil if session&.expired?
    session
  end

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
    ).tap do |new_session|
      user.enforce_session_limit!
      Current.session = new_session
      cookies.signed.permanent[:session_id] = {
        value: new_session.id,
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

## Sessions Controller

```ruby
# app/controllers/sessions_controller.rb
class SessionsController < ApplicationController
  allow_unauthenticated_access only: %i[new create]

  rate_limit to: 10, within: 3.minutes, only: :create,
             with: -> { redirect_to new_session_url, alert: t("sessions.flash.rate_limit") }

  def new
  end

  def create
    if user = User.authenticate_by(params.permit(:email_address, :password))
      start_new_session_for user
      redirect_to after_authentication_url,
                  notice: t("sessions.flash.create.success")
    else
      redirect_to new_session_path,
                  alert: t("sessions.flash.create.error")
    end
  end

  def destroy
    terminate_session
    redirect_to new_session_path,
                notice: t("sessions.flash.destroy.success")
  end
end
```

## Settings Sessions Controller

For device/session management UI:

```ruby
# app/controllers/settings/sessions_controller.rb
module Settings
  class SessionsController < ApplicationController
    def index
      @sessions = Current.user.sessions.recent
      @current_session = Current.session
    end

    def destroy
      session = Current.user.sessions.find(params[:id])

      if session == Current.session
        terminate_session
        redirect_to new_session_path,
                    notice: t('settings.sessions.flash.destroy.current')
      else
        session.destroy
        redirect_to settings_sessions_path,
                    notice: t('settings.sessions.flash.destroy.success')
      end
    end

    def destroy_all_others
      Current.user.revoke_other_sessions!(Current.session)
      redirect_to settings_sessions_path,
                  notice: t('settings.sessions.flash.destroy_all.success')
    end
  end
end
```

## API Sessions Controller

```ruby
# app/controllers/api/sessions_controller.rb
module Api
  class SessionsController < ApplicationController
    allow_unauthenticated_access only: [:create]
    skip_before_action :verify_authenticity_token

    def create
      if user = User.authenticate_by(params.permit(:email_address, :password))
        start_new_session_for user
        render json: {
          session_id: Current.session.id,
          user: {
            id: user.id,
            email: user.email_address
          }
        }
      else
        render json: { error: 'Invalid credentials' },
               status: :unauthorized
      end
    end

    def destroy
      terminate_session
      render json: { message: 'Signed out successfully' }
    end
  end
end
```

## Routes Configuration

```ruby
# config/routes.rb
Rails.application.routes.draw do
  resource :session, only: [:new, :create, :destroy]

  namespace :settings do
    resources :sessions, only: [:index, :destroy] do
      collection do
        delete :destroy_all_others
      end
    end
  end

  namespace :api do
    resource :session, only: [:create, :destroy]
  end
end
```

## API Client Usage

```bash
# Login
curl -X POST https://api.example.com/api/session \
  -H "Content-Type: application/json" \
  -d '{"email_address": "user@example.com", "password": "secret"}'

# Response: {"session_id": "abc-123-xyz", "user": {...}}

# Authenticated requests
curl https://api.example.com/api/endpoint \
  -H "Authorization: Bearer abc-123-xyz"

# Logout
curl -X DELETE https://api.example.com/api/session \
  -H "Authorization: Bearer abc-123-xyz"
```
