# User Management Permissions

## Role-Based Access Control

### User Model with Roles

```ruby
class User < ApplicationRecord
  ROLES = %w[member admin owner].freeze

  belongs_to :account
  has_secure_password
  has_many :sessions, dependent: :destroy

  validates :email_address, presence: true,
                            uniqueness: { case_sensitive: false }
  validates :role, inclusion: { in: ROLES }

  normalizes :email_address, with: ->(e) { e.strip.downcase }

  def admin?
    role.in?(%w[admin owner])
  end

  def owner?
    role == 'owner'
  end

  def member?
    role == 'member'
  end
end
```

### Role Migration

```ruby
class AddRoleToUsers < ActiveRecord::Migration[8.0]
  def change
    add_column :users, :role, :string, null: false, default: 'member'
    add_index :users, :role
  end
end
```

### Controller with Role Checks

```ruby
module Settings
  class UsersController < ApplicationController
    before_action :ensure_user_management_enabled
    before_action :ensure_admin
    before_action :set_user, only: [:destroy]

    def destroy
      if @user == Current.user
        redirect_to settings_users_path,
                    alert: t("settings.users.flash.destroy.self_delete_error")
        return
      end

      if @user.owner?
        redirect_to settings_users_path,
                    alert: t("settings.users.flash.destroy.owner_error")
        return
      end

      @user.destroy
      redirect_to settings_users_path,
                  notice: t("settings.users.flash.destroy.success")
    end

    private

    def ensure_admin
      return if Current.user.admin?
      redirect_to root_path, alert: t('errors.unauthorized')
    end
  end
end
```

## Invitation System

### Invitation Model

```ruby
class Invitation < ApplicationRecord
  belongs_to :account
  belongs_to :inviter, class_name: 'User'

  validates :email, presence: true, format: { with: URI::MailTo::EMAIL_REGEXP }
  validates :email, uniqueness: { scope: :account_id,
                                  message: 'has already been invited' }

  before_create :generate_token

  scope :pending, -> { where('expires_at > ?', Time.current) }
  scope :expired, -> { where('expires_at <= ?', Time.current) }

  def expired?
    expires_at <= Time.current
  end

  def accept!(password:)
    raise 'Invitation has expired' if expired?

    user = account.users.create!(
      email_address: email,
      password: password,
      role: 'member'
    )
    destroy!
    user
  end

  def resend!
    update!(expires_at: 7.days.from_now)
    InvitationMailer.invitation_email(self).deliver_later
  end

  private

  def generate_token
    self.token = SecureRandom.urlsafe_base64(32)
    self.expires_at = 7.days.from_now
  end
end
```

### Invitation Migration

```ruby
class CreateInvitations < ActiveRecord::Migration[8.0]
  def change
    create_table :invitations, id: :uuid do |t|
      t.references :account, null: false, foreign_key: true, type: :uuid
      t.references :inviter, null: false, foreign_key: { to_table: :users }, type: :uuid
      t.string :email, null: false
      t.string :token, null: false
      t.datetime :expires_at, null: false
      t.timestamps
    end

    add_index :invitations, :token, unique: true
    add_index :invitations, [:account_id, :email], unique: true
  end
end
```

### Invitations Controller

```ruby
module Settings
  class InvitationsController < ApplicationController
    before_action :ensure_user_management_enabled
    before_action :ensure_admin

    def index
      @invitations = Current.account.invitations.pending.order(:created_at)
    end

    def new
      @invitation = Current.account.invitations.new
    end

    def create
      @invitation = Current.account.invitations.new(invitation_params)
      @invitation.inviter = Current.user

      if @invitation.save
        InvitationMailer.invitation_email(@invitation).deliver_later
        redirect_to settings_invitations_path,
                    notice: t('settings.invitations.flash.create.success')
      else
        render :new, status: :unprocessable_content
      end
    end

    def destroy
      @invitation = Current.account.invitations.find(params[:id])
      @invitation.destroy
      redirect_to settings_invitations_path,
                  notice: t('settings.invitations.flash.destroy.success')
    end

    private

    def invitation_params
      params.require(:invitation).permit(:email)
    end
  end
end
```

### Accept Invitation Controller

```ruby
class AcceptInvitationsController < ApplicationController
  skip_before_action :authenticate

  def show
    @invitation = Invitation.find_by!(token: params[:token])
    @user = User.new
  rescue ActiveRecord::RecordNotFound
    redirect_to root_path, alert: t('invitations.invalid')
  end

  def update
    @invitation = Invitation.find_by!(token: params[:token])

    if @invitation.expired?
      redirect_to root_path, alert: t('invitations.expired')
      return
    end

    user = @invitation.accept!(password: params[:user][:password])
    start_new_session_for(user)
    redirect_to root_path, notice: t('invitations.accepted')
  rescue ActiveRecord::RecordInvalid => e
    @user = User.new
    @user.errors.add(:base, e.message)
    render :show, status: :unprocessable_content
  end
end
```

### Invitation Mailer

```ruby
class InvitationMailer < ApplicationMailer
  def invitation_email(invitation)
    @invitation = invitation
    @accept_url = accept_invitation_url(token: invitation.token)

    mail(
      to: invitation.email,
      subject: t('invitation_mailer.invitation_email.subject',
                 account: invitation.account.name)
    )
  end
end
```

## Last Login Tracking

### Migration

```ruby
class AddLastLoginAtToUsers < ActiveRecord::Migration[8.0]
  def change
    add_column :users, :last_login_at, :datetime
    add_index :users, :last_login_at
  end
end
```

### User Model Addition

```ruby
class User < ApplicationRecord
  scope :active, -> { where('last_login_at > ?', 30.days.ago) }
  scope :inactive, -> { where('last_login_at <= ? OR last_login_at IS NULL', 30.days.ago) }

  def update_last_login!
    update_column(:last_login_at, Time.current)
  end

  def active?
    last_login_at.present? && last_login_at > 30.days.ago
  end
end
```

### Update on Login

```ruby
# In SessionsController#create
def create
  if user = User.authenticate_by(session_params)
    user.update_last_login!
    start_new_session_for user
    redirect_to after_authentication_url
  else
    redirect_to new_session_path, alert: t('sessions.create.invalid')
  end
end
```
