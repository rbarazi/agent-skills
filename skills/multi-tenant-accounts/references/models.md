# Multi-Tenant Models

## Account Model

```ruby
# app/models/account.rb
class Account < ApplicationRecord
  has_many :users, dependent: :destroy

  # Add all account-scoped resources
  has_many :agents, dependent: :destroy
  has_many :tasks, through: :agents
  has_many :knowledge_bases, dependent: :destroy
  has_many :channels, class_name: "AccountChannel", dependent: :destroy
  has_many :account_tools, dependent: :destroy
  has_many :llms, class_name: "AccountLLM", dependent: :destroy

  validates :name, presence: true, uniqueness: true
end
```

**Design Decisions:**
- UUID primary keys for security (non-enumerable IDs)
- JSONB `settings` column for flexible configuration
- Unique account names for identification
- Central hub for all tenant resources

## User-Account Association

```ruby
# app/models/user.rb
class User < ApplicationRecord
  belongs_to :account
  has_secure_password
  has_many :sessions, dependent: :destroy

  validates :email_address, presence: true,
                            uniqueness: { case_sensitive: false }
  normalizes :email_address, with: ->(e) { e.strip.downcase }
end
```

**Key Points:**
- Users belong to exactly one account
- Email uniqueness is global (or can be scoped to account)
- Admin flag for account-level permissions
- Foreign key constraint ensures referential integrity

## Current Model

```ruby
# app/models/current.rb
class Current < ActiveSupport::CurrentAttributes
  attribute :session
  attribute :user
  attribute :account
  attribute :oauth_client
  attribute :access_token

  # Auto-delegate through the chain: session -> user -> account
  delegate :user, to: :session, allow_nil: true
  delegate :account, to: :user, allow_nil: true
end
```

**How it works:**
1. Authentication sets `Current.session`
2. Session delegates to `user`
3. User delegates to `account`
4. All three accessible via `Current`

## Resource Scoping Patterns

### Direct Association (top-level resources)

```ruby
class Agent < ApplicationRecord
  belongs_to :account
  has_many :tasks, dependent: :destroy
  validates :name, presence: true
end
```

### Through Association (nested resources)

```ruby
class Task < ApplicationRecord
  belongs_to :agent
  delegate :account, to: :agent

  scope :for_account, ->(account) {
    joins(:agent).where(agents: { account_id: account.id })
  }
end
```

## Junction Tables for Shared Resources

For global resources with per-account configuration:

```ruby
# Global tool definition
class Tool < ApplicationRecord
  has_many :account_tools
  has_many :accounts, through: :account_tools
end

# Account-specific configuration
class AccountTool < ApplicationRecord
  belongs_to :account
  belongs_to :tool
  # Account-specific settings stored here
end

# In Account model
class Account < ApplicationRecord
  has_many :account_tools, dependent: :destroy
  has_many :tools, through: :account_tools
end
```

## Account LLM Configuration Pattern

```ruby
class LLM < ApplicationRecord
  # Global LLM provider
  has_many :account_llms
  has_many :accounts, through: :account_llms
end

class AccountLLM < ApplicationRecord
  belongs_to :account
  belongs_to :llm

  # Account-specific API key (encrypted)
  encrypts :api_key

  # Account-specific configuration like `models` (jsonb) and `default_model` (string)
  # are stored as columns on this model, defined in a migration.
end
```
