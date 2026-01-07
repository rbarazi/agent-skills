# Authentication Security Best Practices

## Password Security

1. **bcrypt hashing** via `has_secure_password`
   - Automatic salting
   - Configurable cost factor
   - 72 character max (bcrypt limit)

2. **Never reveal user existence**
   - Same error for invalid email and password
   - Use: "Try another email address or password."
   - NOT: "Email not found" or "Wrong password"

3. **Password confirmation**
   - Use `password_confirmation` for password changes
   - Let `has_secure_password` handle validation

## Session Security

1. **Signed cookies**
   ```ruby
   cookies.signed.permanent[:session_id] = {
     value: session.id,
     httponly: true,
     same_site: :lax
   }
   ```

2. **HttpOnly** - Prevents JavaScript access (XSS protection)

3. **SameSite: :lax** - CSRF protection

4. **Audit trail**
   - Store IP and user agent for each session
   - Log suspicious activity

## Rate Limiting

Built-in Rails 8 rate limiting:

```ruby
rate_limit to: 10, within: 3.minutes, only: :create,
           with: -> { redirect_to new_session_url, alert: t("sessions.flash.rate_limit") }
```

## Parameter Filtering

Ensure passwords are filtered from logs:

```ruby
# config/initializers/filter_parameter_logging.rb
Rails.application.config.filter_parameters += [
  :passw, :secret, :token, :_key, :crypt, :salt, :certificate, :otp, :ssn
]
```

## Session Invalidation

Invalidate sessions on password change:

```ruby
# In user model or service
def change_password(new_password)
  update(password: new_password)
  sessions.destroy_all  # Force re-login everywhere
end
```

## HTTPS Enforcement

In production, force SSL:

```ruby
# config/environments/production.rb
config.force_ssl = true
```

## Common Attacks Prevented

| Attack | Protection |
|--------|------------|
| Brute force | Rate limiting |
| Session hijacking | Signed cookies, HttpOnly |
| XSS | HttpOnly cookies |
| CSRF | SameSite cookies |
| Timing attacks | `authenticate_by` constant-time comparison |
| Password enumeration | Generic error messages |
