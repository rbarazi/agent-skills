# Authentication Migrations

## Users Table

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_users.rb
class CreateUsers < ActiveRecord::Migration[8.0]
  def change
    create_table :users, id: :uuid do |t|
      t.string :email_address, null: false
      t.string :password_digest, null: false
      t.timestamps
    end
    add_index :users, :email_address, unique: true
  end
end
```

**Key Points:**
- UUID primary key for security (non-enumerable)
- `email_address` is unique and required
- `password_digest` stores bcrypt hash (never store plain passwords)

## Sessions Table

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_sessions.rb
class CreateSessions < ActiveRecord::Migration[8.0]
  def change
    create_table :sessions, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.string :ip_address
      t.string :user_agent
      t.timestamps
    end
  end
end
```

**Purpose of columns:**
- `user_id` - Foreign key to users table
- `ip_address` - Audit trail for security
- `user_agent` - Device identification

## Extended Sessions (Optional)

For enhanced session management:

```ruby
class AddFieldsToSessions < ActiveRecord::Migration[8.0]
  def change
    add_column :sessions, :last_active_at, :datetime
    add_column :sessions, :device_type, :string    # mobile, desktop, tablet
    add_column :sessions, :browser, :string        # Chrome, Safari, Firefox
    add_column :sessions, :os, :string             # macOS, Windows, iOS
    add_column :sessions, :country, :string        # From IP geolocation
    add_column :sessions, :city, :string           # From IP geolocation

    add_index :sessions, :created_at
  end
end
```

## Routes

```ruby
# config/routes.rb
Rails.application.routes.draw do
  resource :session  # new, create, destroy
  resources :passwords, param: :token

  root "dashboard#index"
end
```

This creates:
- `GET /session/new` → `sessions#new` (login form)
- `POST /session` → `sessions#create` (login action)
- `DELETE /session` → `sessions#destroy` (logout)
