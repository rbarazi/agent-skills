---
name: test-auth-helpers
description: Implement authentication testing patterns with RSpec, FactoryBot, and test helpers for Rails applications. Use when writing controller specs, system tests, or request specs that require authenticated users and multi-tenant account context.
---

# Test Authentication Helpers Pattern

Testing patterns for authentication in Rails applications using RSpec and FactoryBot.

## When to Use

- Writing controller specs with authenticated users
- Creating system tests with login flows
- Building request specs with session authentication
- Testing multi-tenant account scoping

## Quick Start

### 1. Authentication Helper Module

```ruby
# spec/support/authentication_helpers.rb
module AuthenticationHelpers
  # For controller and request specs
  def setup_authenticated_user(user = nil)
    account = create(:account)
    user ||= create(:user, account: account)
    session = create(:session, user: user)

    if respond_to?(:cookies)
      cookies.signed[:session_id] = session.id
    end

    [account, user, session]
  end

  # For system tests - performs actual login
  def login_user(user)
    visit new_session_path
    fill_in I18n.t('sessions.form.email'), with: user.email_address
    fill_in I18n.t('sessions.form.password'), with: "password"
    click_button I18n.t('sessions.form.sign_in')
    expect(page).not_to have_current_path(new_session_path, wait: 10)
  end

  # For API specs with Bearer token
  def auth_headers_for(user)
    session = create(:session, user: user)
    { "Authorization" => "Bearer #{session.id}" }
  end
end

RSpec.configure do |config|
  config.include AuthenticationHelpers
end
```

### 2. Usage in Controller Specs

```ruby
RSpec.describe AgentsController, type: :controller do
  let(:account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  it 'returns success' do
    get :index
    expect(response).to be_successful
  end
end
```

### 3. Usage in System Tests

```ruby
RSpec.describe 'Agent Management', type: :system, js: true do
  let(:account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { login_user(user) }

  it 'shows agents page' do
    visit agents_path
    expect(page).to have_content(I18n.t('agents.index.title'))
  end
end
```

## Key Patterns

- **Controller specs**: Use `setup_authenticated_user` with cookie injection
- **System tests**: Use `login_user` with actual form submission
- **API specs**: Use `auth_headers_for` with Bearer token
- **Always use I18n**: Never hardcode button/label text

## Reference Files

For complete implementation details:

- **[factories.md](references/factories.md)** - Account, User, Session factories
- **[helpers.md](references/helpers.md)** - Full AuthenticationHelpers module
- **[controller-specs.md](references/controller-specs.md)** - Controller testing patterns
- **[system-specs.md](references/system-specs.md)** - System test patterns
- **[request-specs.md](references/request-specs.md)** - API and request spec patterns
- **[best-practices.md](references/best-practices.md)** - Do's, don'ts, debugging tips
