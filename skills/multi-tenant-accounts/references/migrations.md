# Multi-Tenant Migrations

## Accounts Table

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_accounts.rb
class CreateAccounts < ActiveRecord::Migration[8.0]
  def change
    create_table :accounts, id: :uuid do |t|
      t.string :name, null: false
      t.jsonb :settings, default: {}, null: false
      t.timestamps
    end
    add_index :accounts, :name, unique: true
  end
end
```

## Add Account to Users

```ruby
# db/migrate/YYYYMMDDHHMMSS_add_account_to_users.rb
class AddAccountToUsers < ActiveRecord::Migration[8.0]
  def change
    add_reference :users, :account, null: false, foreign_key: true, type: :uuid
    add_column :users, :admin, :boolean, null: false, default: false
  end
end
```

## Feature Flags on Accounts

```ruby
# db/migrate/YYYYMMDDHHMMSS_add_allow_user_management_to_accounts.rb
class AddAllowUserManagementToAccounts < ActiveRecord::Migration[8.0]
  def change
    add_column :accounts, :allow_user_management, :boolean, default: false, null: false
  end
end
```

## Account-Scoped Resources Pattern

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_agents.rb
class CreateAgents < ActiveRecord::Migration[8.0]
  def change
    create_table :agents, id: :uuid do |t|
      t.references :account, null: false, foreign_key: true, type: :uuid
      t.string :name, null: false
      t.string :username, null: false
      t.text :instructions
      t.timestamps
    end
    add_index :agents, [:account_id, :username], unique: true
  end
end
```

## Junction Table Pattern

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_account_tools.rb
class CreateAccountTools < ActiveRecord::Migration[8.0]
  def change
    create_table :account_tools, id: :uuid do |t|
      t.references :account, null: false, foreign_key: true, type: :uuid
      t.references :tool, null: false, foreign_key: true, type: :uuid
      t.jsonb :custom_config, default: {}
      t.timestamps
    end
    add_index :account_tools, [:account_id, :tool_id], unique: true
  end
end
```

## Account LLM Configuration

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_account_llms.rb
class CreateAccountLlms < ActiveRecord::Migration[8.0]
  def change
    create_table :account_llms, id: :uuid do |t|
      t.references :account, null: false, foreign_key: true, type: :uuid
      t.references :llm, null: false, foreign_key: true, type: :uuid
      t.text :api_key  # encrypted via encrypts
      t.string :default_model
      t.jsonb :models, default: {}
      t.timestamps
    end
    add_index :account_llms, [:account_id, :llm_id], unique: true
  end
end
```
