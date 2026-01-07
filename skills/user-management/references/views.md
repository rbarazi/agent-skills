# User Management Views

## Index View

```erb
<!-- app/views/settings/users/index.html.erb -->
<div class="page-header">
  <h1><%= t('settings.users.index.title') %></h1>
  <%= link_to t('settings.users.index.new_user'),
              new_settings_user_path,
              class: "button button--primary" %>
</div>

<table class="table">
  <thead>
    <tr>
      <th><%= t('settings.users.index.email') %></th>
      <th><%= t('settings.users.index.role') %></th>
      <th><%= t('settings.users.index.actions') %></th>
    </tr>
  </thead>
  <tbody>
    <% @users.each do |user| %>
      <tr>
        <td><%= user.email_address %></td>
        <td>
          <% if user == Current.user %>
            <span class="badge badge--info">
              <%= t('settings.users.index.current_user') %>
            </span>
          <% else %>
            <span class="badge">
              <%= t('settings.users.index.team_member') %>
            </span>
          <% end %>
        </td>
        <td>
          <% unless user == Current.user %>
            <%= button_to t('shared.delete'),
                          settings_user_path(user),
                          method: :delete,
                          class: "button button--danger button--small",
                          data: {
                            turbo_confirm: t('settings.users.index.confirm_delete')
                          } %>
          <% end %>
        </td>
      </tr>
    <% end %>
  </tbody>
</table>
```

## New User View

```erb
<!-- app/views/settings/users/new.html.erb -->
<div class="page-header">
  <h1><%= t('settings.users.new.title') %></h1>
</div>

<%= render 'form', user: @user %>
```

## User Form Partial

```erb
<!-- app/views/settings/users/_form.html.erb -->
<%= form_with model: [:settings, user], class: "form" do |form| %>
  <% if user.errors.any? %>
    <div class="form__errors">
      <h3><%= t('settings.users.form.errors.prohibited_save',
                count: user.errors.count) %></h3>
      <ul>
        <% user.errors.full_messages.each do |message| %>
          <li><%= message %></li>
        <% end %>
      </ul>
    </div>
  <% end %>

  <div class="form__group">
    <%= form.label :email_address, t('settings.users.form.email'),
                   class: "form__label" %>
    <%= form.email_field :email_address,
                         class: "form__input",
                         required: true,
                         autofocus: true,
                         autocomplete: "email" %>
  </div>

  <div class="form__group">
    <%= form.label :password, t('settings.users.form.password'),
                   class: "form__label" %>
    <%= form.password_field :password,
                           class: "form__input",
                           required: true,
                           autocomplete: "new-password",
                           minlength: 8,
                           maxlength: 72 %>
    <p class="form__help">
      <%= t('settings.users.form.password_requirements') %>
    </p>
  </div>

  <div class="form__actions">
    <%= form.submit t('settings.users.form.create'),
                    class: "button button--primary" %>
    <%= link_to t('shared.cancel'),
                settings_users_path,
                class: "button button--secondary" %>
  </div>
<% end %>
```

## Account Settings View

```erb
<!-- app/views/settings/accounts/show.html.erb -->
<div class="page-header">
  <h1><%= t('settings.accounts.show.title') %></h1>
</div>

<%= form_with model: @account,
              url: settings_account_path,
              class: "form" do |form| %>

  <div class="form__group">
    <%= form.label :name, t('settings.accounts.form.name'),
                   class: "form__label" %>
    <%= form.text_field :name, class: "form__input", required: true %>
  </div>

  <div class="form__group form__group--checkbox">
    <%= form.check_box :allow_user_management,
                       class: "form__checkbox" %>
    <%= form.label :allow_user_management,
                   t('settings.accounts.form.allow_user_management'),
                   class: "form__checkbox-label" %>
  </div>

  <div class="form__actions">
    <%= form.submit t('shared.save'), class: "button button--primary" %>
  </div>
<% end %>

<% if Current.account.allow_user_management? %>
  <div class="section">
    <h2><%= t('settings.accounts.show.team_section') %></h2>
    <p><%= link_to t('settings.accounts.show.manage_team'),
                   settings_users_path,
                   class: "button button--secondary" %></p>
  </div>
<% end %>
```

## User Count Display Pattern

```erb
<p class="meta">
  <%= t('settings.users.index.user_count',
        count: Current.account.users.count) %>
</p>
```
