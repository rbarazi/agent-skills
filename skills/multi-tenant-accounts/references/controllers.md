# Multi-Tenant Controllers

## Resource Controller Pattern

```ruby
# app/controllers/agents_controller.rb
class AgentsController < ApplicationController
  before_action :set_agent, only: %i[show edit update destroy]

  def index
    # ALWAYS scope to current account
    @agents = Current.account.agents.order(:name)
  end

  def new
    @agent = Current.account.agents.new
  end

  def create
    @agent = Current.account.agents.new(agent_params)
    if @agent.save
      redirect_to @agent, notice: t('agents.flash.create.success')
    else
      render :new, status: :unprocessable_content
    end
  end

  def update
    if @agent.update(agent_params)
      redirect_to @agent, notice: t('agents.flash.update.success')
    else
      render :edit, status: :unprocessable_content
    end
  end

  def destroy
    @agent.destroy
    redirect_to agents_path, notice: t('agents.flash.destroy.success')
  end

  private

  def set_agent
    # Security critical: always scope to current account!
    @agent = Current.account.agents.find(params[:id])
  end

  def agent_params
    params.require(:agent).permit(:name, :instructions)
  end
end
```

## Account Settings Controller

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

## Feature Flag Controller Pattern

```ruby
# Check feature flags in controllers
def ensure_user_management_enabled
  return if Current.account.allow_user_management?
  redirect_to settings_path, alert: t("settings.users.flash.disabled")
end
```

## Safe vs Unsafe Query Patterns

### Safe Queries

```ruby
# Always use Current.account scope
Current.account.users.count
Current.account.agents.where(active: true)
Current.account.tasks.where(status: 'pending').limit(10)

# Through associations (already scoped)
@agent = Current.account.agents.find(params[:id])
@agent.tasks.recent  # Already scoped through agent
```

### Unsafe Queries (AVOID!)

```ruby
# NEVER do unscoped lookups
User.find(params[:id])        # Can access other accounts' users
Agent.where(name: 'test')     # Can see other accounts' agents
Task.all                       # Exposes all tenants' data
```

## Routes for Multi-Tenant Settings

```ruby
# config/routes.rb
Rails.application.routes.draw do
  namespace :settings do
    resource :account, only: [:show, :update]
    resources :users, only: [:index, :new, :create, :destroy]
    resources :account_llms
    resources :account_tools
    resources :account_channels
  end

  # Regular account-scoped resources
  resources :agents do
    resources :tasks
  end
end
```
