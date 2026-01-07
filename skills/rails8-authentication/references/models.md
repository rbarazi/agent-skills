# Authentication Models

## User Model

```ruby
# app/models/user.rb
class User < ApplicationRecord
  belongs_to :account  # For multi-tenant apps, see multi-tenant-accounts skill

  has_secure_password
  has_many :sessions, dependent: :destroy

  # Email normalization - strips whitespace and downcases
  normalizes :email_address, with: ->(e) { e.strip.downcase }

  validates :email_address, presence: true,
                            uniqueness: { case_sensitive: false }
end
```

**Key Features:**
- `has_secure_password` provides `password=`, `password_confirmation=`, and `authenticate` methods
- Uses bcrypt for password hashing (password limited to 72 characters)
- `password_digest` column stores the hash
- Rails 8 provides `password_reset_token` method automatically
- Email normalization ensures consistent lookups

## Session Model

```ruby
# app/models/session.rb
class Session < ApplicationRecord
  belongs_to :user
end
```

**Why database-backed sessions?**
- Audit trail: track IP, user agent, login times
- Multiple device support: user can have many active sessions
- Revocation: can invalidate specific sessions
- Security: session ID in cookie is not the user ID

## Current Model

The Current model provides thread-safe request-scoped attributes:

```ruby
# app/models/current.rb
class Current < ActiveSupport::CurrentAttributes
  attribute :session
  attribute :user
  attribute :account
  attribute :oauth_client  # For OAuth support
  attribute :access_token  # For OAuth support

  # Auto-delegate through session chain
  delegate :user, to: :session, allow_nil: true
  delegate :account, to: :user, allow_nil: true
end
```

**Usage anywhere in your app:**
```ruby
Current.session  # The current session record
Current.user     # Auto-delegates to session.user
Current.account  # Auto-delegates to user.account (multi-tenant)
```

**Important:** `Current` attributes are automatically reset between requests.
