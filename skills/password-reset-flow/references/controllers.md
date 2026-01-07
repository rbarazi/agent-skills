# Password Reset Controllers

## Passwords Controller

```ruby
# app/controllers/passwords_controller.rb
class PasswordsController < ApplicationController
  allow_unauthenticated_access
  before_action :set_user_by_token, only: %i[edit update]

  rate_limit to: 5, within: 1.hour, only: :create,
             with: -> { redirect_to new_password_path, alert: t("passwords.flash.rate_limit") }

  # GET /passwords/new - Request password reset form
  def new
  end

  # POST /passwords - Send reset email
  def create
    if user = User.find_by(email_address: params[:email_address])
      PasswordsMailer.reset(user).deliver_later
      Rails.logger.info "Password reset requested for user #{user.id}"
    else
      Rails.logger.info "Password reset attempted for unknown email"
    end

    # Always show success - don't reveal if user exists
    redirect_to new_session_path,
                notice: t("passwords.flash.create.success")
  end

  # GET /passwords/:token/edit - Reset password form
  def edit
  end

  # PATCH /passwords/:token - Update password
  def update
    if @user.update(password_params)
      # Invalidate all existing sessions for security
      @user.sessions.destroy_all

      redirect_to new_session_path,
                  notice: t("passwords.flash.update.success")
    else
      render :edit, status: :unprocessable_content
    end
  end

  private

  def password_params
    params.permit(:password, :password_confirmation)
  end

  def set_user_by_token
    @user = User.find_by_password_reset_token!(params[:token])
  rescue ActiveSupport::MessageVerifier::InvalidSignature
    redirect_to new_password_path,
                alert: t("passwords.flash.invalid_token")
  end
end
```

## Routes Configuration

```ruby
# config/routes.rb
Rails.application.routes.draw do
  resource :session
  resources :passwords, param: :token

  # This creates:
  # GET    /passwords/new           -> passwords#new
  # POST   /passwords               -> passwords#create
  # GET    /passwords/:token/edit   -> passwords#edit
  # PATCH  /passwords/:token        -> passwords#update
end
```

## Token Customization

```ruby
# config/initializers/active_record.rb
# Change default 15-minute expiry
Rails.application.config.active_record.password_reset_token_in = 1.hour
```
