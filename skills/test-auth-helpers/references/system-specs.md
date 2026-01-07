# System Test Patterns

## Basic Authenticated System Test

```ruby
# spec/system/agents_spec.rb
RSpec.describe 'Agent Management', type: :system, js: true do
  let(:account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { login_user(user) }

  it 'allows creating a new agent' do
    visit agents_path
    click_link I18n.t('agents.index.new_agent')

    fill_in I18n.t('agents.form.name'), with: 'My New Agent'
    fill_in I18n.t('agents.form.username'), with: 'my_agent'
    click_button I18n.t('agents.form.create')

    expect(page).to have_content('My New Agent')
    expect(page).to have_content(I18n.t('agents.flash.create.success'))
  end

  it 'shows validation errors' do
    visit new_agent_path

    click_button I18n.t('agents.form.create')

    expect(page).to have_content("can't be blank")
  end
end
```

## Testing Login Flow

```ruby
RSpec.describe 'Authentication', type: :system, js: true do
  let!(:user) { create(:user, email_address: 'test@example.com') }

  it 'allows user to sign in' do
    visit new_session_path

    fill_in I18n.t('sessions.form.email'), with: 'test@example.com'
    fill_in I18n.t('sessions.form.password'), with: 'password'
    click_button I18n.t('sessions.form.sign_in')

    expect(page).to have_content(I18n.t('sessions.flash.create.success'))
    expect(page).to have_current_path(root_path)
  end

  it 'shows error with invalid credentials' do
    visit new_session_path

    fill_in I18n.t('sessions.form.email'), with: 'test@example.com'
    fill_in I18n.t('sessions.form.password'), with: 'wrongpassword'
    click_button I18n.t('sessions.form.sign_in')

    expect(page).to have_content(I18n.t('sessions.flash.create.error'))
    expect(page).to have_current_path(new_session_path)
  end

  it 'allows user to sign out' do
    login_user(user)

    click_button 'Sign out'

    expect(page).to have_content(I18n.t('sessions.flash.destroy.success'))
    expect(page).to have_current_path(new_session_path)
  end
end
```

## Testing Multi-User Scenarios

```ruby
RSpec.describe 'User Management', type: :system, js: true do
  let(:account) { create(:account, allow_user_management: true) }
  let(:user) { create(:user, account: account) }
  let!(:other_user) { create(:user, account: account) }

  before { login_user(user) }

  it 'shows all team members' do
    visit settings_users_path

    expect(page).to have_content(user.email_address)
    expect(page).to have_content(other_user.email_address)
  end

  it 'allows removing other users' do
    visit settings_users_path

    within('tr', text: other_user.email_address) do
      accept_confirm do
        click_button I18n.t('shared.delete')
      end
    end

    expect(page).not_to have_content(other_user.email_address)
    expect(page).to have_content(I18n.t('settings.users.flash.destroy.success'))
  end

  it 'prevents removing yourself' do
    visit settings_users_path

    within('tr', text: user.email_address) do
      expect(page).not_to have_button(I18n.t('shared.delete'))
    end
  end
end
```

## Testing Account Isolation

```ruby
RSpec.describe 'Multi-tenant Isolation', type: :system, js: true do
  let(:account1) { create(:account, name: 'Account 1') }
  let(:account2) { create(:account, name: 'Account 2') }
  let(:user1) { create(:user, account: account1) }
  let(:user2) { create(:user, account: account2) }

  it 'shows only own account resources' do
    agent1 = create(:agent, account: account1, name: 'Agent 1')
    agent2 = create(:agent, account: account2, name: 'Agent 2')

    login_user(user1)
    visit agents_path

    expect(page).to have_content('Agent 1')
    expect(page).not_to have_content('Agent 2')
  end
end
```

## Custom Checkbox Interactions

```ruby
it 'toggles a custom checkbox' do
  visit settings_account_path

  # Custom styled checkboxes need special handling
  find("span.form__checkbox-label", text: "Enable feature").click

  click_button I18n.t('shared.save')

  expect(page).to have_content(I18n.t('settings.accounts.flash.update.success'))
end
```

## Synchronization Patterns

```ruby
it 'waits for async content' do
  # Use proper synchronization, never sleep
  expect(page).to have_content('Success', wait: 5)

  # Wait for specific element count
  expect(page).to have_selector('.task-item', count: 5, wait: 10)

  # Wait for element to disappear
  expect(page).not_to have_selector('.loading-spinner', wait: 5)
end
```
