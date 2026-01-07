---
name: password-reset-flow
description: Implement secure password reset with Rails 8's built-in token generation. Use when building "forgot password" functionality with email verification and time-limited reset tokens.
---

# Password Reset Flow Pattern

Secure password reset using Rails 8's built-in token generation. No external gems required.

## When to Use

- Building "forgot password" functionality
- Implementing email-based password recovery
- Adding secure token-based password reset

## Security Principles

1. **Don't reveal user existence** - Same message for valid/invalid emails
2. **Time-limited tokens** - 15-minute expiry by default
3. **Single-use tokens** - Token invalidated after password change
4. **Signed tokens** - Cryptographically secure, tamper-proof

## Quick Start

### 1. User Model

Rails 8's `has_secure_password` provides built-in support:

```ruby
class User < ApplicationRecord
  has_secure_password
  # Automatically provides:
  # - password_reset_token (generates signed token)
  # - find_by_password_reset_token!(token)
end
```

### 2. Passwords Controller

```ruby
# app/controllers/passwords_controller.rb
class PasswordsController < ApplicationController
  allow_unauthenticated_access
  before_action :set_user_by_token, only: %i[edit update]

  def new
  end

  def create
    if user = User.find_by(email_address: params[:email_address])
      PasswordsMailer.reset(user).deliver_later
    end
    # Always show success - don't reveal if user exists
    redirect_to new_session_path, notice: t("passwords.flash.create.success")
  end

  def edit
  end

  def update
    if @user.update(password_params)
      redirect_to new_session_path, notice: t("passwords.flash.update.success")
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
    redirect_to new_password_path, alert: t("passwords.flash.invalid_token")
  end
end
```

### 3. Routes

```ruby
resources :passwords, param: :token
```

### 4. Mailer

```ruby
class PasswordsMailer < ApplicationMailer
  def reset(user)
    @user = user
    mail subject: t('passwords.mailer.reset.subject'), to: user.email_address
  end
end
```

## Token Mechanics

```ruby
# Generate token
user.password_reset_token
# => "eyJfcmFpbHMiOnsibWVzc2FnZSI6Ik..."

# Find user by token
User.find_by_password_reset_token!(token)
# => #<User id: 1, ...>

# Default expiry: 15 minutes
# Customize in: config/initializers/active_record.rb
Rails.application.config.active_record.password_reset_token_in = 1.hour
```

## Reference Files

For complete implementation details:

- **[controllers.md](references/controllers.md)** - Full controller with rate limiting, session invalidation
- **[views.md](references/views.md)** - Request and reset forms
- **[mailer.md](references/mailer.md)** - Email templates (HTML and text)
- **[i18n.md](references/i18n.md)** - All translation keys
- **[testing.md](references/testing.md)** - Controller, mailer, and system specs
- **[security.md](references/security.md)** - Rate limiting, logging, password validation
