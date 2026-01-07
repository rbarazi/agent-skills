# Password Reset Views

## Request Reset Form

```erb
<!-- app/views/passwords/new.html.erb -->
<div class="auth-container">
  <h1><%= t('passwords.new.title') %></h1>

  <p class="auth-description">
    <%= t('passwords.new.description') %>
  </p>

  <%= form_with url: passwords_path, class: "form" do |form| %>
    <div class="form__group">
      <%= form.label :email_address,
                     t('passwords.form.email_address'),
                     class: "form__label" %>
      <%= form.email_field :email_address,
                           class: "form__input",
                           required: true,
                           autofocus: true,
                           autocomplete: "email",
                           placeholder: t('passwords.form.placeholders.email') %>
    </div>

    <div class="form__actions">
      <%= form.submit t('passwords.form.send_reset_link'),
                      class: "button button--primary button--full" %>
    </div>
  <% end %>

  <div class="auth-links">
    <%= link_to t('passwords.new.back_to_login'),
                new_session_path,
                class: "link" %>
  </div>
</div>
```

## Reset Password Form

```erb
<!-- app/views/passwords/edit.html.erb -->
<div class="auth-container">
  <h1><%= t('passwords.edit.title') %></h1>

  <% if @user.errors.any? %>
    <div class="form__errors">
      <ul>
        <% @user.errors.full_messages.each do |message| %>
          <li><%= message %></li>
        <% end %>
      </ul>
    </div>
  <% end %>

  <%= form_with url: password_path(token: params[:token]),
                method: :patch,
                class: "form" do |form| %>
    <div class="form__group">
      <%= form.label :password,
                     t('passwords.form.new_password'),
                     class: "form__label" %>
      <%= form.password_field :password,
                             class: "form__input",
                             required: true,
                             autofocus: true,
                             autocomplete: "new-password",
                             minlength: 8,
                             maxlength: 72,
                             placeholder: t('passwords.form.placeholders.password') %>
    </div>

    <div class="form__group">
      <%= form.label :password_confirmation,
                     t('passwords.form.confirm_password'),
                     class: "form__label" %>
      <%= form.password_field :password_confirmation,
                             class: "form__input",
                             required: true,
                             autocomplete: "new-password",
                             minlength: 8,
                             maxlength: 72,
                             placeholder: t('passwords.form.placeholders.confirm') %>
    </div>

    <div class="form__actions">
      <%= form.submit t('passwords.form.reset_password'),
                      class: "button button--primary button--full" %>
    </div>
  <% end %>
</div>
```

## CSS for Auth Container

```css
/* app/assets/stylesheets/auth.css */
.auth-container {
  max-width: 400px;
  margin: 2rem auto;
  padding: 2rem;
}

.auth-container h1 {
  margin-bottom: 0.5rem;
  text-align: center;
}

.auth-description {
  margin-bottom: 1.5rem;
  color: var(--text-muted);
  text-align: center;
}

.auth-links {
  margin-top: 1.5rem;
  text-align: center;
}

.auth-links a {
  color: var(--link-color);
  text-decoration: none;
}

.auth-links a:hover {
  text-decoration: underline;
}
```
