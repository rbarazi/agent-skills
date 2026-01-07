# Multi-Tenant Patterns and Anti-Patterns

## Common Gotchas

### 1. Forgetting to Scope Lookups

```ruby
# WRONG
@agent = Agent.find(params[:id])

# CORRECT
@agent = Current.account.agents.find(params[:id])
```

### 2. Joining Without Account Scope

```ruby
# WRONG - might cross accounts
User.joins(:tasks).where(tasks: { status: 'pending' })

# CORRECT
Current.account.users.joins(:tasks).where(tasks: { status: 'pending' })
```

### 3. Caching Without Account Context

```ruby
# WRONG
Rails.cache.fetch("agents_count") { Agent.count }

# CORRECT
Rails.cache.fetch("agents_count_#{Current.account.id}") { Current.account.agents.count }
```

### 4. Background Jobs Without Account

```ruby
# WRONG - Current not available in jobs
class ProcessAgentJob < ApplicationJob
  def perform(task_id)
    task = Current.account.tasks.find(task_id)  # Will fail!
  end
end

# CORRECT
class ProcessAgentJob < ApplicationJob
  def perform(task_id, account_id)
    account = Account.find(account_id)
    task = account.tasks.find(task_id)
  end
end

# Enqueue correctly
ProcessAgentJob.perform_later(task.id, Current.account.id)
```

## Default Scope Warning

Some teams use default scopes, but they can be bypassed:

```ruby
# NOT RECOMMENDED - can be bypassed
class Agent < ApplicationRecord
  default_scope { where(account: Current.account) }
end

# Problem:
Agent.unscoped.find(id)  # Bypasses the scope!
```

**Recommendation:** Explicit scoping via `Current.account.resource` is safer.

## Account Hierarchy (Advanced)

For enterprise with sub-accounts:

```ruby
class Account < ApplicationRecord
  belongs_to :parent_account, class_name: 'Account', optional: true
  has_many :sub_accounts, class_name: 'Account', foreign_key: 'parent_account_id'

  def root_account
    parent_account&.root_account || self
  end
end
```

## Database Seeding

```ruby
# db/seeds.rb
ActiveRecord::Base.transaction do
  account = Account.find_or_create_by!(
    name: ENV.fetch('ACCOUNT_NAME', 'Default Account')
  )

  user = account.users.find_or_initialize_by(
    email_address: ENV.fetch('ADMIN_EMAIL')
  )
  user.password = ENV.fetch('ADMIN_PASSWORD')
  user.save!

  # Create account-scoped resources
  agent = account.agents.find_or_create_by!(
    name: 'Default Agent',
    username: 'default_agent'
  )
end
```
