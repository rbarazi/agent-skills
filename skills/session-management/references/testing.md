# Session Management Testing

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
      user_agent { "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15" }
    end

    trait :android do
      user_agent { "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36" }
    end
  end
end
```

## Session Model Specs

```ruby
# spec/models/session_spec.rb
RSpec.describe Session, type: :model do
  describe 'associations' do
    it { is_expected.to belong_to(:user) }
  end

  describe '#device_name' do
    it 'detects iPhone' do
      session = build(:session, :mobile)
      expect(session.device_name).to eq('iPhone')
    end

    it 'detects Android' do
      session = build(:session, :android)
      expect(session.device_name).to eq('Android')
    end

    it 'returns Unknown for blank user agent' do
      session = build(:session, user_agent: nil)
      expect(session.device_name).to eq('Unknown')
    end
  end

  describe '#expired?' do
    it 'returns false for recent sessions' do
      session = create(:session)
      expect(session).not_to be_expired
    end

    it 'returns true for old sessions' do
      session = create(:session, :expired)
      expect(session).to be_expired
    end
  end

  describe '#touch_activity!' do
    it 'updates last_active_at' do
      session = create(:session, last_active_at: nil)
      session.touch_activity!
      expect(session.reload.last_active_at).to be_present
    end

    it 'throttles updates within 5 minutes' do
      session = create(:session, last_active_at: 1.minute.ago)
      original_time = session.last_active_at
      session.touch_activity!
      expect(session.reload.last_active_at).to eq(original_time)
    end
  end
end
```

## Controller Specs

```ruby
# spec/controllers/sessions_controller_spec.rb
RSpec.describe SessionsController, type: :controller do
  describe 'POST #create' do
    let(:user) { create(:user, password: 'password123') }

    it 'creates a session on successful login' do
      expect {
        post :create, params: {
          email_address: user.email_address,
          password: 'password123'
        }
      }.to change(Session, :count).by(1)
    end

    it 'sets session cookie' do
      post :create, params: {
        email_address: user.email_address,
        password: 'password123'
      }
      expect(cookies.signed[:session_id]).to be_present
    end

    it 'rejects invalid credentials' do
      post :create, params: {
        email_address: user.email_address,
        password: 'wrong'
      }
      expect(response).to redirect_to(new_session_path)
      expect(flash[:alert]).to be_present
    end
  end

  describe 'DELETE #destroy' do
    let(:user) { create(:user) }

    before { setup_authenticated_user(user) }

    it 'destroys the current session' do
      expect {
        delete :destroy
      }.to change(Session, :count).by(-1)
    end

    it 'clears session cookie' do
      delete :destroy
      expect(cookies[:session_id]).to be_nil
    end
  end
end

# spec/controllers/settings/sessions_controller_spec.rb
RSpec.describe Settings::SessionsController, type: :controller do
  let(:user) { create(:user) }

  before { setup_authenticated_user(user) }

  describe 'GET #index' do
    it 'lists user sessions' do
      other_session = create(:session, user: user)

      get :index

      expect(assigns(:sessions)).to include(other_session)
    end

    it 'does not list other users sessions' do
      other_user = create(:user)
      other_session = create(:session, user: other_user)

      get :index

      expect(assigns(:sessions)).not_to include(other_session)
    end
  end

  describe 'DELETE #destroy' do
    it 'terminates another session' do
      other_session = create(:session, user: user)

      expect {
        delete :destroy, params: { id: other_session.id }
      }.to change(user.sessions, :count).by(-1)
    end

    it 'cannot terminate other users sessions' do
      other_user = create(:user)
      other_session = create(:session, user: other_user)

      expect {
        delete :destroy, params: { id: other_session.id }
      }.to raise_error(ActiveRecord::RecordNotFound)
    end
  end

  describe 'DELETE #destroy_all_others' do
    it 'terminates all other sessions' do
      create_list(:session, 3, user: user)

      delete :destroy_all_others

      expect(user.sessions.count).to eq(1)
    end
  end
end
```

## System Specs

```ruby
# spec/system/session_management_spec.rb
RSpec.describe 'Session Management', type: :system, js: true do
  let(:user) { create(:user) }

  before { login_user(user) }

  it 'shows active sessions' do
    other_session = create(:session, user: user, user_agent: 'Test Agent')

    visit settings_sessions_path

    expect(page).to have_content(I18n.t('settings.sessions.index.this_device'))
  end

  it 'allows signing out other sessions' do
    other_session = create(:session, user: user)

    visit settings_sessions_path

    within('.session-card:not(.session-card--current)') do
      click_button I18n.t('settings.sessions.index.sign_out')
    end

    expect(page).to have_content(I18n.t('settings.sessions.flash.destroy.success'))
    expect(Session.find_by(id: other_session.id)).to be_nil
  end

  it 'allows signing out all other sessions' do
    create_list(:session, 3, user: user)

    visit settings_sessions_path
    accept_confirm do
      click_button I18n.t('settings.sessions.index.sign_out_all_others')
    end

    expect(page).to have_content(I18n.t('settings.sessions.flash.destroy_all.success'))
    expect(user.sessions.count).to eq(1)
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

  def login_user(user)
    visit new_session_path
    fill_in I18n.t('sessions.form.email'), with: user.email_address
    fill_in I18n.t('sessions.form.password'), with: 'password'
    click_button I18n.t('sessions.form.sign_in')
    expect(page).not_to have_current_path(new_session_path, wait: 10)
  end
end
```

## API Specs

```ruby
# spec/requests/api/sessions_spec.rb
RSpec.describe 'API Sessions', type: :request do
  let(:user) { create(:user, password: 'password123') }

  describe 'POST /api/session' do
    it 'returns session token on success' do
      post '/api/session', params: {
        email_address: user.email_address,
        password: 'password123'
      }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body)['session_id']).to be_present
    end

    it 'returns unauthorized on failure' do
      post '/api/session', params: {
        email_address: user.email_address,
        password: 'wrong'
      }

      expect(response).to have_http_status(:unauthorized)
    end
  end

  describe 'DELETE /api/session' do
    let(:session) { create(:session, user: user) }

    it 'destroys the session' do
      delete '/api/session', headers: {
        'Authorization' => "Bearer #{session.id}"
      }

      expect(response).to have_http_status(:ok)
      expect(Session.find_by(id: session.id)).to be_nil
    end
  end
end
```
