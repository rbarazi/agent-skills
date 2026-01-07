# Testing Multi-Tenant Isolation

## Model Isolation Tests

```ruby
# spec/models/agent_spec.rb
RSpec.describe Agent, type: :model do
  let(:account1) { create(:account) }
  let(:account2) { create(:account) }

  it "cannot access agents from other accounts" do
    agent1 = create(:agent, account: account1)
    agent2 = create(:agent, account: account2)

    expect(account1.agents).to include(agent1)
    expect(account1.agents).not_to include(agent2)
  end
end
```

## Controller Isolation Tests

```ruby
# spec/controllers/agents_controller_spec.rb
RSpec.describe AgentsController, type: :controller do
  let(:account) { create(:account) }
  let(:other_account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  it "cannot access other account's agents" do
    other_agent = create(:agent, account: other_account)

    expect {
      get :show, params: { id: other_agent.id }
    }.to raise_error(ActiveRecord::RecordNotFound)
  end

  it "lists only current account's agents" do
    own_agent = create(:agent, account: account)
    other_agent = create(:agent, account: other_account)

    get :index

    expect(assigns(:agents)).to include(own_agent)
    expect(assigns(:agents)).not_to include(other_agent)
  end
end
```

## System Test Patterns

```ruby
# spec/system/multi_tenant_spec.rb
RSpec.describe "Multi-tenant isolation", type: :system, js: true do
  let(:account1) { create(:account, name: "Account 1") }
  let(:account2) { create(:account, name: "Account 2") }
  let(:user1) { create(:user, account: account1) }
  let(:user2) { create(:user, account: account2) }

  it "shows only own account resources" do
    agent1 = create(:agent, account: account1, name: "Agent 1")
    agent2 = create(:agent, account: account2, name: "Agent 2")

    login_user(user1)
    visit agents_path

    expect(page).to have_content("Agent 1")
    expect(page).not_to have_content("Agent 2")
  end
end
```

## Factories

```ruby
# spec/factories/accounts.rb
FactoryBot.define do
  factory :account do
    sequence(:name) { |n| "ACME Corp #{n}" }

    trait :with_user_management do
      allow_user_management { true }
    end
  end
end

# spec/factories/users.rb
FactoryBot.define do
  factory :user do
    sequence(:email_address) { |n| "user#{n}@acme.com" }
    password { "password" }
    account
  end
end
```

## Authentication Helper

```ruby
# spec/support/authentication_helpers.rb
module AuthenticationHelpers
  def setup_authenticated_user(user = nil)
    account = create(:account)
    user ||= create(:user, account: account)
    session = create(:session, user: user)

    if respond_to?(:cookies)
      cookies.signed[:session_id] = session.id
    end

    [account, user, session]
  end
end
```
