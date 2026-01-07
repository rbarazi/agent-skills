# User Management Controllers

## Settings::UsersController

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
        redirect_to settings_users_path,
                    notice: t("settings.users.flash.create.success")
      else
        render :new, status: :unprocessable_content
      end
    end

    def destroy
      if @user == Current.user
        redirect_to settings_users_path,
                    alert: t("settings.users.flash.destroy.self_delete_error")
        return
      end

      @user.destroy
      redirect_to settings_users_path,
                  notice: t("settings.users.flash.destroy.success")
    end

    private

    def set_user
      # Always scope to current account - security critical!
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

## Settings::AccountsController

For account settings with user management toggle:

```ruby
# app/controllers/settings/accounts_controller.rb
module Settings
  class AccountsController < ApplicationController
    def show
      @account = Current.account
    end

    def update
      @account = Current.account
      if @account.update(account_params)
        redirect_to settings_account_path,
                    notice: t("settings.accounts.flash.update.success")
      else
        render :show, status: :unprocessable_content
      end
    end

    private

    def account_params
      params.require(:account).permit(:name, :allow_user_management)
    end
  end
end
```

## Routes Configuration

```ruby
# config/routes.rb
Rails.application.routes.draw do
  namespace :settings do
    resource :account, only: [:show, :update]
    resources :users, only: [:index, :new, :create, :destroy]
  end
end
```
