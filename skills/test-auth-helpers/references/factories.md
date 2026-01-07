# Test Factories

## Account Factory

```ruby
# spec/factories/accounts.rb
FactoryBot.define do
  factory :account do
    sequence(:name) { |n| "ACME Corp #{n}" }

    trait :with_user_management do
      allow_user_management { true }
    end

    trait :with_users do
      transient do
        users_count { 3 }
      end

      after(:create) do |account, evaluator|
        create_list(:user, evaluator.users_count, account: account)
      end
    end
  end
end
```

## User Factory

```ruby
# spec/factories/users.rb
FactoryBot.define do
  factory :user do
    sequence(:email_address) { |n| "user#{n}@acme.com" }
    password { "password" }
    account

    trait :admin do
      admin { true }
    end

    trait :with_sessions do
      transient do
        sessions_count { 2 }
      end

      after(:create) do |user, evaluator|
        create_list(:session, evaluator.sessions_count, user: user)
      end
    end

    trait :with_role do
      transient do
        role { 'member' }
      end

      after(:build) do |user, evaluator|
        user.role = evaluator.role
      end
    end
  end
end
```

## Session Factory

```ruby
# spec/factories/sessions.rb
FactoryBot.define do
  factory :session do
    user
    ip_address { "127.0.0.1" }
    user_agent { "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" }

    trait :expired do
      created_at { 31.days.ago }
    end

    trait :stale do
      last_active_at { 31.days.ago }
    end

    trait :mobile do
      user_agent { "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)" }
      ip_address { "192.168.1.100" }
    end

    trait :android do
      user_agent { "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36" }
    end

    trait :with_activity do
      last_active_at { 5.minutes.ago }
    end
  end
end
```

## Factory Best Practices

### Minimal Data Creation

```ruby
# GOOD - create only what you need
let(:user) { create(:user, account: account) }

# BAD - creates unnecessary data
let(:user) { create(:user, :with_sessions, :admin, account: account) }
```

### Use Traits for Optional Associations

```ruby
# GOOD - use traits for optional features
create(:account, :with_user_management)
create(:user, :admin)
create(:session, :mobile)

# BAD - create cascading objects automatically
factory :account do
  after(:create) { |a| create(:user, account: a) }  # Avoid this!
end
```

### Sequences for Uniqueness

```ruby
# GOOD - use sequences for unique fields
sequence(:email_address) { |n| "user#{n}@example.com" }
sequence(:name) { |n| "Account #{n}" }

# BAD - hardcoded values cause uniqueness conflicts
email_address { "user@example.com" }
```
