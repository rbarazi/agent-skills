# User Management Testing

## Controller Specs

```ruby
# spec/controllers/settings/users_controller_spec.rb
RSpec.describe Settings::UsersController, type: :controller do
  let(:account) { create(:account, allow_user_management: true) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  describe 'GET #index' do
    it 'lists users from current account only' do
      other_account = create(:account)
      other_user = create(:user, account: other_account)

      get :index

      expect(assigns(:users)).to include(user)
      expect(assigns(:users)).not_to include(other_user)
    end
  end

  describe 'GET #new' do
    it 'initializes a new user in current account' do
      get :new

      expect(assigns(:user)).to be_a_new(User)
    end
  end

  describe 'POST #create' do
    it 'creates user in current account' do
      expect {
        post :create, params: {
          user: { email_address: 'new@example.com', password: 'password123' }
        }
      }.to change(account.users, :count).by(1)
    end

    it 'redirects with success message' do
      post :create, params: {
        user: { email_address: 'new@example.com', password: 'password123' }
      }

      expect(response).to redirect_to(settings_users_path)
      expect(flash[:notice]).to eq(I18n.t('settings.users.flash.create.success'))
    end

    it 'renders form with errors for invalid data' do
      post :create, params: {
        user: { email_address: '', password: 'short' }
      }

      expect(response).to have_http_status(:unprocessable_content)
      expect(response).to render_template(:new)
    end
  end

  describe 'DELETE #destroy' do
    it 'prevents self-deletion' do
      delete :destroy, params: { id: user.id }

      expect(response).to redirect_to(settings_users_path)
      expect(flash[:alert]).to eq(I18n.t('settings.users.flash.destroy.self_delete_error'))
      expect(user.reload).to be_present
    end

    it 'allows deleting other users' do
      other_user = create(:user, account: account)

      expect {
        delete :destroy, params: { id: other_user.id }
      }.to change(account.users, :count).by(-1)

      expect(response).to redirect_to(settings_users_path)
      expect(flash[:notice]).to eq(I18n.t('settings.users.flash.destroy.success'))
    end

    it 'cannot delete users from other accounts' do
      other_account = create(:account)
      other_user = create(:user, account: other_account)

      expect {
        delete :destroy, params: { id: other_user.id }
      }.to raise_error(ActiveRecord::RecordNotFound)
    end
  end

  context 'when user management disabled' do
    let(:account) { create(:account, allow_user_management: false) }

    it 'redirects index with alert' do
      get :index

      expect(response).to redirect_to(settings_path)
      expect(flash[:alert]).to eq(I18n.t('settings.users.flash.disabled'))
    end

    it 'redirects create with alert' do
      post :create, params: {
        user: { email_address: 'new@example.com', password: 'password123' }
      }

      expect(response).to redirect_to(settings_path)
    end
  end
end
```

## System Specs

```ruby
# spec/system/user_management_spec.rb
RSpec.describe 'User Management', type: :system, js: true do
  let(:account) { create(:account, allow_user_management: true) }
  let(:user) { create(:user, account: account) }

  before { login_user(user) }

  it 'lists team members' do
    other_user = create(:user, account: account)

    visit settings_users_path

    expect(page).to have_content(user.email_address)
    expect(page).to have_content(other_user.email_address)
  end

  it 'allows adding a new team member' do
    visit settings_users_path

    click_link I18n.t('settings.users.index.new_user')

    fill_in I18n.t('settings.users.form.email'), with: 'newuser@example.com'
    fill_in I18n.t('settings.users.form.password'), with: 'securepass123'
    click_button I18n.t('settings.users.form.create')

    expect(page).to have_content('newuser@example.com')
    expect(page).to have_content(I18n.t('settings.users.flash.create.success'))
  end

  it 'shows validation errors' do
    visit new_settings_user_path

    fill_in I18n.t('settings.users.form.email'), with: 'invalid'
    fill_in I18n.t('settings.users.form.password'), with: 'short'
    click_button I18n.t('settings.users.form.create')

    expect(page).to have_selector('.form__errors')
  end

  it 'marks current user differently' do
    visit settings_users_path

    within('tr', text: user.email_address) do
      expect(page).to have_content(I18n.t('settings.users.index.current_user'))
    end
  end

  it 'prevents deleting yourself' do
    visit settings_users_path

    within('tr', text: user.email_address) do
      expect(page).not_to have_button(I18n.t('shared.delete'))
    end
  end

  it 'allows deleting other team members' do
    other_user = create(:user, account: account)

    visit settings_users_path

    within('tr', text: other_user.email_address) do
      accept_confirm do
        click_button I18n.t('shared.delete')
      end
    end

    expect(page).to have_content(I18n.t('settings.users.flash.destroy.success'))
    expect(page).not_to have_content(other_user.email_address)
  end

  context 'when user management is disabled' do
    let(:account) { create(:account, allow_user_management: false) }

    it 'redirects to settings with alert' do
      visit settings_users_path

      expect(page).to have_current_path(settings_path)
      expect(page).to have_content(I18n.t('settings.users.flash.disabled'))
    end
  end
end
```

## Factory

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
```
