---
name: user-management
description: Implement user CRUD operations within an account with permission controls and feature flags. Use when building team member management, user administration, or account user settings in multi-tenant Rails applications.
---

# User Management Pattern

Implement team member management within a multi-tenant Rails application with feature flags and permission controls.

## When to Use

- Adding team member management
- Implementing user administration within accounts
- Building "invite user" or "add team member" functionality
- Adding permission controls for user management

## Architecture Overview

```
Account (has_many :users)
    └── Feature Flag: allow_user_management
         └── Settings::UsersController
              ├── index (list team members)
              ├── new/create (add member)
              └── destroy (remove member, not self)
```

## Quick Start

### 1. Add Feature Flag

```ruby
# Migration
add_column :accounts, :allow_user_management, :boolean, default: false, null: false
```

### 2. Create Controller

```ruby
# app/controllers/settings/users_controller.rb
module Settings
  class UsersController < ApplicationController
    before_action :ensure_user_management_enabled
    before_action :set_user, only: [:destroy]

    def index
      @users = Current.account.users.order(:email_address)
    end

    def new
      @user = Current.account.users.new
    end

    def create
      @user = Current.account.users.new(user_params)
      if @user.save
        redirect_to settings_users_path, notice: t("settings.users.flash.create.success")
      else
        render :new, status: :unprocessable_content
      end
    end

    def destroy
      if @user == Current.user
        redirect_to settings_users_path, alert: t("settings.users.flash.destroy.self_delete_error")
        return
      end
      @user.destroy
      redirect_to settings_users_path, notice: t("settings.users.flash.destroy.success")
    end

    private

    def set_user
      @user = Current.account.users.find(params[:id])
    end

    def user_params
      params.require(:user).permit(:email_address, :password)
    end

    def ensure_user_management_enabled
      return if Current.account.allow_user_management?
      redirect_to settings_path, alert: t("settings.users.flash.disabled")
    end
  end
end
```

### 3. Add Routes

```ruby
namespace :settings do
  resources :users, only: [:index, :new, :create, :destroy]
end
```

## Security Checklist

- [ ] Always scope to `Current.account.users`
- [ ] Prevent self-deletion (`@user == Current.user`)
- [ ] Feature flag disabled by default
- [ ] Password requirements enforced (min 8 chars)
- [ ] Use `:unprocessable_content` status for errors

## Reference Files

For complete implementation details:

- **[controllers.md](references/controllers.md)** - Full controller with all actions
- **[views.md](references/views.md)** - Index, form, and account settings views
- **[i18n.md](references/i18n.md)** - All translation keys
- **[testing.md](references/testing.md)** - Controller and system specs
- **[permissions.md](references/permissions.md)** - Role-based access, invitation system
