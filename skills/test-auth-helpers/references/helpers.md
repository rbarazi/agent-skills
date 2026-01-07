# Authentication Helpers Module

## Full Helper Implementation

```ruby
# spec/support/authentication_helpers.rb
module AuthenticationHelpers
  # For controller and request specs
  # Injects session cookie directly without HTTP login
  def setup_authenticated_user(user = nil)
    account = create(:account)
    user ||= create(:user, account: account)
    session = create(:session, user: user)

    # Inject session cookie for controller specs
    if respond_to?(:cookies)
      cookies.signed[:session_id] = session.id
    end

    [account, user, session]
  end

  # For system tests - performs actual login via form
  # Use this instead of session manipulation for realistic testing
  def login_user(user)
    visit new_session_path
    fill_in I18n.t('sessions.form.email'), with: user.email_address
    fill_in I18n.t('sessions.form.password'), with: "password"
    click_button I18n.t('sessions.form.sign_in')

    # Wait for redirect to complete
    expect(page).not_to have_current_path(new_session_path, wait: 10)

    # Set test cookie for ActionCable connections (if needed)
    page.execute_script("document.cookie = 'test_user_id=#{user.id}; path=/';")
  end

  # For API/request specs with Bearer token authentication
  def auth_headers_for(user)
    session = create(:session, user: user)
    { "Authorization" => "Bearer #{session.id}" }
  end

  # Logout helper for system tests
  def logout_user
    click_button 'Sign out'
    expect(page).to have_current_path(new_session_path)
  end

  # Create authenticated request headers with JSON content type
  def json_auth_headers_for(user)
    auth_headers_for(user).merge({
      "Content-Type" => "application/json",
      "Accept" => "application/json"
    })
  end
end

RSpec.configure do |config|
  config.include AuthenticationHelpers
end
```

## Helper Registration

```ruby
# spec/rails_helper.rb
require 'support/authentication_helpers'

RSpec.configure do |config|
  config.include AuthenticationHelpers

  # System test setup
  config.before(:each, type: :system) do
    driven_by(:cuprite, screen_size: [1400, 1400])
  end

  # Use transactional fixtures
  config.use_transactional_fixtures = true

  # Include FactoryBot methods
  config.include FactoryBot::Syntax::Methods
end
```

## When to Use Each Helper

| Helper | Use Case | How It Works |
|--------|----------|--------------|
| `setup_authenticated_user` | Controller specs, Request specs | Cookie injection |
| `login_user` | System tests | Form submission |
| `auth_headers_for` | API specs | Bearer token header |
| `logout_user` | System tests | Button click |
