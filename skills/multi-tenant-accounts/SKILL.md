---
name: multi-tenant-accounts
description: Implement multi-tenant architecture using an Account model as the tenant boundary. Use when building SaaS applications, team-based apps, or any system where data must be isolated between organizations/accounts.
---

# Multi-Tenant Account Pattern

Account-based multi-tenancy for Rails applications. All resources scoped to accounts for data isolation.

## Quick Start

1. Create Account model as the tenant container
2. Add `belongs_to :account` to User model
3. Configure Current model to delegate account from session
4. Scope all resources via `Current.account`

## Core Architecture

```
Account (tenant boundary)
  └── Users (belong to account)
  └── All resources (scoped to account)

Current.session → Current.user → Current.account
```

## Components

| Component | Purpose | Reference |
|-----------|---------|-----------|
| Account model | Tenant container | [models.md](references/models.md) |
| User-Account relationship | User scoping | [models.md](references/models.md) |
| Current model | Request-scoped access | [models.md](references/models.md) |
| Controller scoping | Safe queries | [controllers.md](references/controllers.md) |
| Database migrations | Schema design | [migrations.md](references/migrations.md) |
| Testing patterns | Isolation tests | [testing.md](references/testing.md) |

## Minimal Implementation

### Account Model

```ruby
class Account < ApplicationRecord
  has_many :users, dependent: :destroy
  has_many :agents, dependent: :destroy  # Example resource

  validates :name, presence: true, uniqueness: true
end
```

### User-Account Association

```ruby
class User < ApplicationRecord
  belongs_to :account
  has_secure_password
end
```

### Current Model

```ruby
class Current < ActiveSupport::CurrentAttributes
  attribute :session
  delegate :user, to: :session, allow_nil: true
  delegate :account, to: :user, allow_nil: true
end
```

### Controller Scoping

```ruby
class AgentsController < ApplicationController
  def index
    @agents = Current.account.agents  # Always scope to account
  end

  def show
    @agent = Current.account.agents.find(params[:id])  # Security critical!
  end
end
```

## Critical Security Pattern

```ruby
# CORRECT - scoped to account
@agent = Current.account.agents.find(params[:id])

# WRONG - exposes all accounts' data!
@agent = Agent.find(params[:id])  # SECURITY VULNERABILITY
```

## Account Access Pattern

```ruby
# Anywhere in your application:
Current.account        # => #<Account id: "abc-123">
Current.user           # => #<User id: "xyz-456">
Current.account.agents # => [Agent, Agent, ...]
Current.account.users  # => [User, User, ...]
```

## Detailed References

- **[models.md](references/models.md)**: Account model, associations, junction tables
- **[controllers.md](references/controllers.md)**: Controller scoping patterns, settings controllers
- **[migrations.md](references/migrations.md)**: Database schema and migrations
- **[testing.md](references/testing.md)**: Testing multi-tenant isolation
- **[patterns.md](references/patterns.md)**: Common patterns and anti-patterns
