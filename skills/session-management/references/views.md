# Session Management Views

## Session Management Index

```erb
<!-- app/views/settings/sessions/index.html.erb -->
<div class="page-header">
  <h1><%= t('settings.sessions.index.title') %></h1>

  <% if @sessions.count > 1 %>
    <%= button_to t('settings.sessions.index.sign_out_all_others'),
                  destroy_all_others_settings_sessions_path,
                  method: :delete,
                  class: "button button--danger",
                  data: { turbo_confirm: t('settings.sessions.index.confirm_all') } %>
  <% end %>
</div>

<div class="sessions-list">
  <% @sessions.each do |session| %>
    <div class="session-card <%= 'session-card--current' if session == @current_session %>">
      <div class="session-card__info">
        <div class="session-card__device">
          <%= session.device_name %> - <%= session.browser_name %>
        </div>
        <div class="session-card__meta">
          <span class="session-card__ip"><%= session.ip_address %></span>
          <span class="session-card__time">
            <% if session == @current_session %>
              <%= t('settings.sessions.index.current_session') %>
            <% else %>
              <%= t('settings.sessions.index.last_active',
                    time: time_ago_in_words(session.last_active_at || session.created_at)) %>
            <% end %>
          </span>
        </div>
      </div>

      <div class="session-card__actions">
        <% if session == @current_session %>
          <span class="badge badge--success">
            <%= t('settings.sessions.index.this_device') %>
          </span>
        <% else %>
          <%= button_to t('settings.sessions.index.sign_out'),
                        settings_session_path(session),
                        method: :delete,
                        class: "button button--small button--danger" %>
        <% end %>
      </div>
    </div>
  <% end %>
</div>
```

## CSS for Session Cards

```css
/* app/assets/stylesheets/sessions.css */
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.session-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--card-bg);
}

.session-card--current {
  border-color: var(--success-color);
  background: var(--success-bg);
}

.session-card__info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.session-card__device {
  font-weight: 600;
}

.session-card__meta {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.session-card__actions {
  display: flex;
  align-items: center;
}
```

## Login Form

```erb
<!-- app/views/sessions/new.html.erb -->
<div class="auth-container">
  <h1><%= t('sessions.new.title') %></h1>

  <%= form_with url: session_path, class: "form" do |form| %>
    <div class="form__group">
      <%= form.label :email_address, t('sessions.form.email'),
                     class: "form__label" %>
      <%= form.email_field :email_address,
                           class: "form__input",
                           required: true,
                           autofocus: true,
                           autocomplete: "email" %>
    </div>

    <div class="form__group">
      <%= form.label :password, t('sessions.form.password'),
                     class: "form__label" %>
      <%= form.password_field :password,
                             class: "form__input",
                             required: true,
                             autocomplete: "current-password" %>
    </div>

    <div class="form__actions">
      <%= form.submit t('sessions.form.sign_in'),
                      class: "button button--primary button--full" %>
    </div>
  <% end %>

  <div class="auth-links">
    <%= link_to t('sessions.new.forgot_password'), new_password_path %>
  </div>
</div>
```

## Session Activity Helper

```ruby
# app/helpers/sessions_helper.rb
module SessionsHelper
  def session_status_badge(session, current_session)
    if session == current_session
      content_tag :span, t('settings.sessions.index.this_device'),
                  class: 'badge badge--success'
    elsif session.stale?
      content_tag :span, t('settings.sessions.index.inactive'),
                  class: 'badge badge--warning'
    end
  end

  def session_last_activity(session, current_session)
    if session == current_session
      t('settings.sessions.index.current_session')
    elsif session.last_active_at
      t('settings.sessions.index.last_active',
        time: time_ago_in_words(session.last_active_at))
    else
      t('settings.sessions.index.created',
        time: time_ago_in_words(session.created_at))
    end
  end
end
```
