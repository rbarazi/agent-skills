# Password Reset Testing

## Controller Specs

```ruby
# spec/controllers/passwords_controller_spec.rb
RSpec.describe PasswordsController, type: :controller do
  describe 'GET #new' do
    it 'renders the request form' do
      get :new
      expect(response).to have_http_status(:ok)
      expect(response).to render_template(:new)
    end
  end

  describe 'POST #create' do
    context 'with valid email' do
      let!(:user) { create(:user, email_address: 'test@example.com') }

      it 'sends password reset email' do
        expect {
          post :create, params: { email_address: 'test@example.com' }
        }.to have_enqueued_mail(PasswordsMailer, :reset)
      end

      it 'redirects with success message' do
        post :create, params: { email_address: 'test@example.com' }

        expect(response).to redirect_to(new_session_path)
        expect(flash[:notice]).to eq(I18n.t('passwords.flash.create.success'))
      end
    end

    context 'with invalid email' do
      it 'still shows success message (security)' do
        post :create, params: { email_address: 'nonexistent@example.com' }

        expect(response).to redirect_to(new_session_path)
        expect(flash[:notice]).to eq(I18n.t('passwords.flash.create.success'))
      end

      it 'does not send email' do
        expect {
          post :create, params: { email_address: 'nonexistent@example.com' }
        }.not_to have_enqueued_mail
      end
    end
  end

  describe 'GET #edit' do
    let(:user) { create(:user) }

    context 'with valid token' do
      it 'renders the reset form' do
        token = user.password_reset_token
        get :edit, params: { token: token }

        expect(response).to have_http_status(:ok)
        expect(response).to render_template(:edit)
      end
    end

    context 'with expired token' do
      it 'redirects with error' do
        token = user.password_reset_token

        travel 20.minutes do
          get :edit, params: { token: token }
        end

        expect(response).to redirect_to(new_password_path)
        expect(flash[:alert]).to eq(I18n.t('passwords.flash.invalid_token'))
      end
    end

    context 'with invalid token' do
      it 'redirects with error' do
        get :edit, params: { token: 'invalid-token' }

        expect(response).to redirect_to(new_password_path)
        expect(flash[:alert]).to eq(I18n.t('passwords.flash.invalid_token'))
      end
    end
  end

  describe 'PATCH #update' do
    let(:user) { create(:user) }

    context 'with valid token and matching passwords' do
      it 'updates password' do
        token = user.password_reset_token

        patch :update, params: {
          token: token,
          password: 'newpassword123',
          password_confirmation: 'newpassword123'
        }

        expect(response).to redirect_to(new_session_path)
        expect(user.reload.authenticate('newpassword123')).to be_truthy
      end

      it 'invalidates all sessions' do
        create_list(:session, 3, user: user)
        token = user.password_reset_token

        expect {
          patch :update, params: {
            token: token,
            password: 'newpassword123',
            password_confirmation: 'newpassword123'
          }
        }.to change { user.sessions.count }.to(0)
      end
    end

    context 'with mismatched passwords' do
      it 'renders form with errors' do
        token = user.password_reset_token

        patch :update, params: {
          token: token,
          password: 'newpassword123',
          password_confirmation: 'different123'
        }

        expect(response).to have_http_status(:unprocessable_content)
        expect(response).to render_template(:edit)
      end
    end

    context 'with expired token' do
      it 'redirects with error' do
        token = user.password_reset_token

        travel 20.minutes do
          patch :update, params: {
            token: token,
            password: 'newpassword123',
            password_confirmation: 'newpassword123'
          }
        end

        expect(response).to redirect_to(new_password_path)
        expect(flash[:alert]).to eq(I18n.t('passwords.flash.invalid_token'))
      end
    end
  end
end
```

## Mailer Specs

```ruby
# spec/mailers/passwords_mailer_spec.rb
RSpec.describe PasswordsMailer, type: :mailer do
  describe '#reset' do
    let(:user) { create(:user, email_address: 'test@example.com') }
    let(:mail) { described_class.reset(user) }

    it 'sends to correct email' do
      expect(mail.to).to eq(['test@example.com'])
    end

    it 'has correct subject' do
      expect(mail.subject).to eq(I18n.t('passwords.mailer.reset.subject'))
    end

    it 'includes reset link' do
      expect(mail.body.encoded).to include('passwords/')
      expect(mail.body.encoded).to include('/edit')
    end

    it 'includes valid token' do
      # Token is generated when called
      expect(mail.body.encoded).to match(/passwords\/[A-Za-z0-9_-]+\/edit/)
    end

    it 'has both HTML and text parts' do
      expect(mail.parts.map(&:content_type)).to include(
        a_string_matching(/text\/html/),
        a_string_matching(/text\/plain/)
      )
    end
  end
end
```

## System Specs

```ruby
# spec/system/password_reset_spec.rb
RSpec.describe 'Password Reset', type: :system, js: true do
  let!(:user) { create(:user, email_address: 'test@example.com', password: 'oldpassword123') }

  it 'allows user to reset password via email' do
    visit new_session_path
    click_link I18n.t('sessions.new.forgot_password')

    fill_in I18n.t('passwords.form.email_address'), with: 'test@example.com'
    click_button I18n.t('passwords.form.send_reset_link')

    expect(page).to have_content(I18n.t('passwords.flash.create.success'))

    # Get token from email
    mail = ActionMailer::Base.deliveries.last
    token = extract_reset_token(mail)

    # Visit reset page
    visit edit_password_path(token: token)

    fill_in I18n.t('passwords.form.new_password'), with: 'newsecurepass123'
    fill_in I18n.t('passwords.form.confirm_password'), with: 'newsecurepass123'
    click_button I18n.t('passwords.form.reset_password')

    expect(page).to have_content(I18n.t('passwords.flash.update.success'))

    # Can login with new password
    fill_in I18n.t('sessions.form.email'), with: 'test@example.com'
    fill_in I18n.t('sessions.form.password'), with: 'newsecurepass123'
    click_button I18n.t('sessions.form.sign_in')

    expect(page).to have_current_path(root_path)
  end

  it 'shows error for mismatched passwords' do
    token = user.password_reset_token
    visit edit_password_path(token: token)

    fill_in I18n.t('passwords.form.new_password'), with: 'newsecurepass123'
    fill_in I18n.t('passwords.form.confirm_password'), with: 'differentpassword'
    click_button I18n.t('passwords.form.reset_password')

    expect(page).to have_selector('.form__errors')
  end

  it 'shows error for expired token' do
    token = user.password_reset_token

    travel 20.minutes do
      visit edit_password_path(token: token)
    end

    expect(page).to have_content(I18n.t('passwords.flash.invalid_token'))
  end

  def extract_reset_token(mail)
    mail.body.to_s.match(/passwords\/([^\/\s"]+)\/edit/)[1]
  end
end
```

## Request Specs for Rate Limiting

```ruby
# spec/requests/passwords_spec.rb
RSpec.describe 'Password Reset Rate Limiting', type: :request do
  it 'blocks after too many requests' do
    6.times do
      post passwords_path, params: { email_address: 'test@example.com' }
    end

    expect(response).to redirect_to(new_password_path)
    expect(flash[:alert]).to eq(I18n.t('passwords.flash.rate_limit'))
  end
end
```
