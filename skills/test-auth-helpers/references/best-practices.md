# Testing Best Practices

## Do's

### Use I18n for All Form Interactions

```ruby
# GOOD
fill_in I18n.t('sessions.form.email'), with: user.email_address
click_button I18n.t('sessions.form.sign_in')

# BAD - hardcoded strings break when copy changes
fill_in 'Email', with: user.email_address
click_button 'Sign In'
```

### Use Proper Synchronization

```ruby
# GOOD - proper wait
expect(page).to have_content('Success', wait: 5)
expect(page).to have_selector('.item', count: 3, wait: 10)

# BAD - never use sleep
sleep 2
expect(page).to have_content('Success')
```

### Create Minimal Test Data

```ruby
# GOOD - only create what you need
let(:user) { create(:user, account: account) }

# BAD - unnecessary data creation
let(:user) { create(:user, :with_sessions, :admin, account: account) }
```

### Use let! for Required Data

```ruby
# GOOD - data must exist before test runs
let!(:existing_agent) { create(:agent, account: account) }

# Use let (lazy) when data isn't always needed
let(:other_agent) { create(:agent, account: account) }
```

### Reload Models After Database Changes

```ruby
# GOOD
user.reload
expect(user.updated_at).to be > original_time

# BAD - may have stale data
expect(user.updated_at).to be > original_time
```

## Don'ts

### Don't Hardcode Strings

```ruby
# BAD
fill_in 'Email', with: user.email
click_button 'Submit'

# GOOD
fill_in I18n.t('form.email'), with: user.email
click_button I18n.t('form.submit')
```

### Don't Use Sleep

```ruby
# BAD
sleep 2
expect(page).to have_content('Done')

# GOOD
expect(page).to have_content('Done', wait: 5)
```

### Don't Create Unnecessary Data

```ruby
# BAD - creates sessions that aren't needed
let(:user) { create(:user, :with_sessions) }

# GOOD - minimal data
let(:user) { create(:user) }
```

### Don't Manipulate Session Directly in System Tests

```ruby
# BAD
page.set_rack_session(user_id: user.id)

# GOOD
login_user(user)
```

### Don't Test Implementation Details

```ruby
# BAD - tests internal state
expect(Current.session.id).to eq(session.id)

# GOOD - tests behavior
expect(page).to have_current_path(root_path)
```

## Debugging Tips

### View Session in Tests

```ruby
it 'debug session state' do
  setup_authenticated_user(user)
  puts "Session cookie: #{cookies.signed[:session_id]}"
  puts "Current.session: #{Current.session.inspect}"
end
```

### System Test Screenshots

```ruby
it 'captures failure screenshot' do
  login_user(user)
  visit some_path

  # On failure, screenshot is saved automatically with Cuprite
  # Or manually capture:
  save_screenshot('debug_screenshot.png')
end
```

### Request Logging

```ruby
RSpec.configure do |config|
  config.before(:each, type: :request) do
    Rails.logger.level = :debug
  end
end
```

### Database State Inspection

```ruby
it 'debug database state' do
  # Print all records
  puts User.all.inspect
  puts Session.all.inspect

  # Check specific record
  puts user.reload.attributes
end
```

## Performance Tips

### Use let_it_be for Expensive Setup

```ruby
# GOOD - shared across all tests in group
let_it_be(:account) { create(:account) }
let_it_be(:user) { create(:user, account: account) }

# Each test gets fresh data based on these
let(:agent) { create(:agent, account: account) }
```

### Tag Slow Tests

```ruby
# Tag integration tests
RSpec.describe 'Docker Integration', :integration do
  # expensive tests
end

# Exclude by default
# spec/spec_helper.rb
config.filter_run_excluding integration: true
```

### Parallelize Tests

```ruby
# Use parallel_rspec for faster runs
$ bin/parallel_rspec

# Split by file
$ bin/parallel_rspec spec/models spec/controllers
```

## RSpec Configuration

```ruby
# spec/rails_helper.rb
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

  # Clean up after each test
  config.after(:each) do
    Current.reset
  end
end
```
