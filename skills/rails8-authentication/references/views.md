# Authentication Views

## Login Form

```erb
<!-- app/views/sessions/new.html.erb -->
<% if flash[:alert] %>
  <div class="form__errors">
    <ul><li><%= flash[:alert] %></li></ul>
  </div>
<% end %>

<% if flash[:notice] %>
  <div class="form__notice"><%= flash[:notice] %></div>
<% end %>

<%= form_with url: session_path, class: "form form--mobile-friendly" do |form| %>
  <div class="form__group">
    <%= form.label :email_address, t('sessions.form.email'), class: "form__label" %>
    <%= form.email_field :email_address,
                        class: "form__input",
                        required: true,
                        autofocus: true,
                        autocomplete: "username",
                        placeholder: t('sessions.form.placeholders.email_address'),
                        value: params[:email_address] %>
  </div>

  <div class="form__group">
    <%= form.label :password, t('sessions.form.password'), class: "form__label" %>
    <%= form.password_field :password,
                          class: "form__input",
                          required: true,
                          autocomplete: "current-password",
                          placeholder: t('sessions.form.placeholders.password'),
                          maxlength: 72 %>
  </div>

  <div class="form__actions form__actions--mobile">
    <%= form.submit t('sessions.form.sign_in'), class: "button button--primary button--full" %>
    <%= link_to t('sessions.new.forgot_password'), new_password_path, class: "button button--text button--full" %>
  </div>
<% end %>
```

**Key Attributes:**
- `autocomplete: "username"` - Password manager support for email
- `autocomplete: "current-password"` - Password manager support
- `maxlength: 72` - bcrypt password limit
- `autofocus: true` - Focus first field on page load

## User Menu Partial

```erb
<!-- app/views/layouts/_user_menu.html.erb -->
<% if Current.user %>
  <div class="user-menu">
    <span class="user-menu__email"><%= Current.user.email_address %></span>
    <span class="user-menu__account"><%= Current.account&.name %></span>

    <%= link_to t('nav.settings'), settings_path, class: "user-menu__link" %>

    <%= button_to t('sessions.destroy.sign_out'),
                  session_path,
                  method: :delete,
                  class: "button button--text" %>
  </div>
<% else %>
  <%= link_to t('sessions.new.sign_in'), new_session_path, class: "button" %>
<% end %>
```

## Layout Integration

```erb
<!-- app/views/layouts/application.html.erb -->
<!DOCTYPE html>
<html>
<head>
  <title><%= content_for(:title) || "App" %></title>
  <%= csrf_meta_tags %>
  <%= csp_meta_tag %>
  <%= stylesheet_link_tag "application", "data-turbo-track": "reload" %>
  <%= javascript_importmap_tags %>
</head>
<body>
  <header>
    <%= render "layouts/user_menu" %>
  </header>

  <main>
    <%= yield %>
  </main>
</body>
</html>
```

## Auth Layout (Optional)

For standalone auth pages with different styling:

```erb
<!-- app/views/layouts/auth.html.erb -->
<!DOCTYPE html>
<html>
<head>
  <title><%= t('sessions.new.title') %></title>
  <%= csrf_meta_tags %>
  <%= stylesheet_link_tag "application" %>
</head>
<body class="auth-layout">
  <div class="auth-container">
    <h1><%= t('sessions.new.title') %></h1>
    <%= yield %>
  </div>
</body>
</html>
```

Apply in controller:
```ruby
class SessionsController < ApplicationController
  layout "auth"
  # ...
end
```
