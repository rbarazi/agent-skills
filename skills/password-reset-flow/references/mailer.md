# Password Reset Mailer

## Mailer Class

```ruby
# app/mailers/passwords_mailer.rb
class PasswordsMailer < ApplicationMailer
  def reset(user)
    @user = user
    mail subject: t('passwords.mailer.reset.subject'),
         to: user.email_address
  end
end
```

## HTML Email Template

```erb
<!-- app/views/passwords_mailer/reset.html.erb -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      color: #1a1a1a;
      font-size: 24px;
      margin-bottom: 20px;
    }
    .button {
      background-color: #4A90D9;
      border-radius: 4px;
      color: white;
      display: inline-block;
      padding: 12px 24px;
      text-decoration: none;
      font-weight: 600;
      margin: 20px 0;
    }
    .button:hover {
      background-color: #357ABD;
    }
    .notice {
      background-color: #f8f9fa;
      border-left: 4px solid #e9ecef;
      padding: 12px;
      margin: 20px 0;
      font-size: 14px;
      color: #666;
    }
    .footer {
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid #eee;
      font-size: 12px;
      color: #999;
    }
  </style>
</head>
<body>
  <h1><%= t('passwords.mailer.reset.heading') %></h1>

  <p><%= t('passwords.mailer.reset.intro') %></p>

  <p style="text-align: center;">
    <%= link_to t('passwords.mailer.reset.button'),
                edit_password_url(token: @user.password_reset_token),
                class: 'button' %>
  </p>

  <div class="notice">
    <p><strong><%= t('passwords.mailer.reset.expiry_notice') %></strong></p>
  </div>

  <p><%= t('passwords.mailer.reset.ignore_notice') %></p>

  <div class="footer">
    <p><%= t('passwords.mailer.reset.security_notice') %></p>
  </div>
</body>
</html>
```

## Text Email Template

```erb
<!-- app/views/passwords_mailer/reset.text.erb -->
<%= t('passwords.mailer.reset.heading') %>

<%= t('passwords.mailer.reset.intro') %>

<%= t('passwords.mailer.reset.button') %>:
<%= edit_password_url(token: @user.password_reset_token) %>

<%= t('passwords.mailer.reset.expiry_notice') %>

<%= t('passwords.mailer.reset.ignore_notice') %>

---
<%= t('passwords.mailer.reset.security_notice') %>
```

## Email Preview

```ruby
# test/mailers/previews/passwords_mailer_preview.rb
class PasswordsMailerPreview < ActionMailer::Preview
  def reset
    user = User.first || User.new(email_address: 'test@example.com')
    PasswordsMailer.reset(user)
  end
end
```

Access previews at: `http://localhost:3000/rails/mailers/passwords_mailer/reset`
