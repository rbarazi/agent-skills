# Password Reset Security

## Rate Limiting

Prevent brute force and enumeration attacks:

```ruby
class PasswordsController < ApplicationController
  rate_limit to: 5, within: 1.hour, only: :create,
             with: -> {
               redirect_to new_password_path,
                           alert: t("passwords.flash.rate_limit")
             }
end
```

## Audit Logging

Log all reset attempts for security monitoring:

```ruby
def create
  if user = User.find_by(email_address: params[:email_address])
    PasswordsMailer.reset(user).deliver_later
    Rails.logger.info "Password reset requested for user #{user.id} from IP #{request.remote_ip}"
  else
    Rails.logger.info "Password reset attempted for unknown email from IP #{request.remote_ip}"
  end

  redirect_to new_session_path, notice: t("passwords.flash.create.success")
end
```

## Session Invalidation

Invalidate all sessions when password is changed:

```ruby
def update
  if @user.update(password_params)
    @user.sessions.destroy_all
    redirect_to new_session_path, notice: t("passwords.flash.update.success")
  else
    render :edit, status: :unprocessable_content
  end
end
```

## Password Strength Validation

```ruby
class User < ApplicationRecord
  has_secure_password

  validates :password, length: { minimum: 8, maximum: 72 },
                       format: {
                         with: /\A(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
                         message: :password_complexity
                       },
                       if: -> { password.present? }
end
```

## Token Security

Rails 8 tokens are:
- **Signed** - Using Rails secret key
- **Purposeful** - Tied to specific action (password_reset)
- **Time-limited** - Default 15 minutes
- **Single-use** - Password change invalidates token

## Preventing User Enumeration

Always show the same response:

```ruby
def create
  if user = User.find_by(email_address: params[:email_address])
    PasswordsMailer.reset(user).deliver_later
  end
  # Same message for both cases
  redirect_to new_session_path, notice: t("passwords.flash.create.success")
end
```

## Token Expiry Configuration

```ruby
# config/initializers/active_record.rb
# Default is 15 minutes
Rails.application.config.active_record.password_reset_token_in = 15.minutes

# For more security, reduce to 10 minutes
Rails.application.config.active_record.password_reset_token_in = 10.minutes
```

## HTTPS Requirement

Ensure all password reset links use HTTPS:

```ruby
# config/environments/production.rb
config.force_ssl = true

# In mailer
Rails.application.config.action_mailer.default_url_options = {
  host: 'example.com',
  protocol: 'https'
}
```

## Security Checklist

- [ ] Same response for valid/invalid emails (prevent enumeration)
- [ ] Token expires in reasonable time (15 minutes default)
- [ ] Rate limiting on reset requests
- [ ] HTTPS required for reset links
- [ ] Sessions invalidated on password change
- [ ] Password meets complexity requirements
- [ ] Audit logging for reset attempts
- [ ] Token is single-use only
- [ ] Secure email delivery (TLS/SSL)

## Suspicious Activity Detection

```ruby
class PasswordResetAttempt < ApplicationRecord
  belongs_to :user, optional: true

  validates :email, :ip_address, presence: true
end

def create
  PasswordResetAttempt.create!(
    email: params[:email_address],
    ip_address: request.remote_ip,
    user_agent: request.user_agent,
    user: User.find_by(email_address: params[:email_address])
  )

  # Check for suspicious patterns
  recent_attempts = PasswordResetAttempt
    .where(ip_address: request.remote_ip)
    .where('created_at > ?', 1.hour.ago)

  if recent_attempts.count > 10
    SecurityMailer.suspicious_reset_activity(request.remote_ip).deliver_later
  end

  # ... rest of create action
end
```
