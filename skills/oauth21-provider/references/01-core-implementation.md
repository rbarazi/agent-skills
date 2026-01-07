# OAuth 2.1 Core Implementation

## Purpose
Implement the core OAuth 2.1 models and controller for a Rails authorization server.

## Models

### OAuthClient

```ruby
# app/models/oauth_client.rb
class OAuthClient < ApplicationRecord
  has_many :oauth_authorization_codes, dependent: :destroy
  has_many :oauth_access_tokens, dependent: :destroy
  has_many :oauth_refresh_tokens, dependent: :destroy

  validates :name, presence: true
  validates :client_id, presence: true, uniqueness: true
  validates :client_secret, presence: true, if: :confidential?
  validates :client_type, inclusion: { in: %w[public confidential] }

  store_accessor :oauth_metadata,
    :redirect_uris,
    :grant_types,
    :response_types,
    :token_endpoint_auth_method,
    :scopes,
    :client_uri

  encrypts :client_secret

  scope :active, -> { where(active: true) }
  scope :confidential, -> { where(client_type: "confidential") }
  scope :public_clients, -> { where(client_type: "public") }

  before_validation :generate_client_credentials, on: :create

  def confidential?
    client_type == "confidential"
  end

  def public?
    client_type == "public"
  end

  def supports_grant_type?(grant_type)
    (grant_types || []).include?(grant_type)
  end

  def valid_redirect_uri?(uri)
    (redirect_uris || []).include?(uri)
  end

  private

  def generate_client_credentials
    self.client_id ||= SecureRandom.urlsafe_base64(32)
    if confidential? && client_secret.blank?
      self.client_secret = SecureRandom.urlsafe_base64(32)
    end
  end
end
```

### OAuthAccessToken

```ruby
# app/models/oauth_access_token.rb
class OAuthAccessToken < ApplicationRecord
  belongs_to :oauth_client
  belongs_to :user, optional: true
  belongs_to :authorization_code, class_name: "OAuthAuthorizationCode", optional: true

  validates :token, presence: true, uniqueness: true
  validates :expires_at, presence: true
  validates :token_type, presence: true

  encrypts :token, deterministic: true

  store_accessor :token_metadata,
    :scopes,
    :issued_at,
    :client_ip,
    :user_agent

  scope :valid, -> { where("expires_at > ?", Time.current) }
  scope :expired, -> { where("expires_at <= ?", Time.current) }

  before_validation :generate_token, on: :create
  before_validation :set_expiry, on: :create

  def token_valid?
    expires_at > Time.current && oauth_client&.active?
  end

  def expired?
    expires_at <= Time.current
  end

  def has_scope?(required_scope)
    (scopes || []).include?(required_scope) || (scopes || []).include?("*")
  end

  private

  def generate_token
    self.token ||= SecureRandom.urlsafe_base64(32)
  end

  def set_expiry
    self.expires_at ||= 1.hour.from_now
  end
end
```

### OAuthAuthorizationCode

```ruby
# app/models/oauth_authorization_code.rb
class OAuthAuthorizationCode < ApplicationRecord
  belongs_to :oauth_client
  belongs_to :user, optional: true

  validates :code, presence: true, uniqueness: true
  validates :expires_at, presence: true
  validates :redirect_uri, presence: true

  encrypts :code, deterministic: true

  store_accessor :pkce_data,
    :code_challenge,
    :code_challenge_method,
    :scopes

  scope :valid, -> { where("expires_at > ?", Time.current) }

  before_validation :generate_code, on: :create
  before_validation :set_expiry, on: :create

  def not_expired?
    expires_at > Time.current
  end

  def has_pkce?
    code_challenge.present?
  end

  def verify_pkce(code_verifier, method)
    return false unless has_pkce?
    PKCEService.verify_code_challenge(code_verifier, code_challenge, method)
  end

  private

  def generate_code
    self.code ||= SecureRandom.urlsafe_base64(32)
  end

  def set_expiry
    self.expires_at ||= 10.minutes.from_now
  end
end
```

## Controller

```ruby
# app/controllers/oauth_controller.rb
class OAuthController < ApplicationController
  include OAuthCors

  allow_unauthenticated_access only: %i[well_known register authorize token options]
  skip_before_action :verify_authenticity_token
  layout "oauth", only: [:authorize]

  # RFC 8414 - Authorization Server Metadata
  def well_known
    render json: oauth_server_metadata
  end

  # RFC 7591 - Dynamic Client Registration
  def register
    service = ClientRegistrationService.new(registration_params.to_h)
    oauth_client = service.register

    if oauth_client
      render json: client_registration_response(oauth_client), status: :created
    else
      render_oauth_error("invalid_client_metadata", service.errors.full_messages.to_sentence)
    end
  end

  # OAuth 2.1 Authorization Endpoint
  def authorize
    authenticate
    return if performed?

    validation_result = validate_authorization_request
    return if validation_result != :valid

    if request.post? && params[:consent].present?
      handle_consent_response
    else
      show_consent_screen
    end
  end

  # OAuth 2.1 Token Endpoint
  def token
    case params[:grant_type]
    when "client_credentials"
      handle_client_credentials_grant
    when "authorization_code"
      handle_authorization_code_grant
    else
      render_oauth_error("unsupported_grant_type", "Unsupported grant type")
    end
  end

  def options
    head :ok
  end

  private

  def oauth_server_metadata
    {
      issuer: root_url,
      authorization_endpoint: oauth_authorize_url,
      token_endpoint: oauth_token_url,
      registration_endpoint: oauth_register_url,
      grant_types_supported: %w[client_credentials authorization_code refresh_token],
      response_types_supported: %w[code],
      token_endpoint_auth_methods_supported: %w[client_secret_basic client_secret_post none],
      code_challenge_methods_supported: %w[S256 plain],
      scopes_supported: %w[read write admin]
    }
  end

  def registration_params
    params.permit(:client_name, :client_type, :client_uri, :scopes,
                  :token_endpoint_auth_method, redirect_uris: [], grant_types: [])
  end

  def client_registration_response(oauth_client)
    {
      client_id: oauth_client.client_id,
      client_name: oauth_client.name,
      client_type: oauth_client.client_type,
      redirect_uris: oauth_client.redirect_uris || [],
      scope: (oauth_client.scopes || []).join(" ")
    }.tap do |response|
      response[:client_secret] = oauth_client.client_secret if oauth_client.confidential?
    end
  end

  def authenticate_client
    client_id, client_secret = extract_client_credentials

    if client_id.blank?
      render_oauth_error("invalid_client", "Client authentication required")
      return nil
    end

    client = OAuthClient.active.find_by(client_id: client_id)
    unless client
      render_oauth_error("invalid_client", "Invalid client credentials")
      return nil
    end

    if client.confidential?
      unless ActiveSupport::SecurityUtils.secure_compare(client.client_secret.to_s, client_secret.to_s)
        render_oauth_error("invalid_client", "Invalid client credentials")
        return nil
      end
    end

    client
  end

  def extract_client_credentials
    if request.headers["Authorization"]&.start_with?("Basic ")
      encoded = request.headers["Authorization"].split(" ", 2).last
      decoded = Base64.decode64(encoded)
      return decoded.split(":", 2)
    end
    [params[:client_id], params[:client_secret]]
  end

  def handle_client_credentials_grant
    client = authenticate_client
    return unless client

    unless client.supports_grant_type?("client_credentials")
      return render_oauth_error("unauthorized_client", "Grant type not authorized")
    end

    scopes = determine_granted_scopes(client)
    access_token = TokenService.issue_access_token(oauth_client: client, scopes: scopes)

    render_access_token(access_token, scopes)
  end

  def handle_authorization_code_grant
    client = authenticate_client
    return unless client

    auth_code = OAuthAuthorizationCode.valid.find_by(code: params[:code])
    unless auth_code && auth_code.oauth_client == client && auth_code.redirect_uri == params[:redirect_uri]
      return render_oauth_error("invalid_grant", "Invalid authorization code")
    end

    if auth_code.has_pkce?
      unless params[:code_verifier].present? && auth_code.verify_pkce(params[:code_verifier], auth_code.code_challenge_method)
        return render_oauth_error("invalid_grant", "PKCE verification failed")
      end
    end

    scopes = auth_code.scopes || []
    access_token = TokenService.issue_access_token(
      oauth_client: client,
      user: auth_code.user,
      authorization_code: auth_code,
      scopes: scopes
    )

    auth_code.update!(expires_at: Time.current)  # Invalidate code

    render_access_token(access_token, scopes)
  end

  def render_access_token(access_token, scopes)
    render json: {
      access_token: access_token.token,
      token_type: "Bearer",
      expires_in: (access_token.expires_at - Time.current).to_i,
      scope: scopes.join(" ")
    }
  end

  def determine_granted_scopes(client)
    requested = params[:scope]&.split(" ") || []
    client_scopes = client.scopes || []
    requested.empty? ? client_scopes : (requested & client_scopes)
  end

  def render_oauth_error(error, description, status = :bad_request)
    render json: { error: error, error_description: description }, status: status
  end
end
```

## Routes

```ruby
# config/routes.rb
Rails.application.routes.draw do
  # OAuth metadata discovery
  get "/.well-known/oauth-authorization-server", to: "oauth#well_known"

  # OAuth endpoints
  post "/oauth/register", to: "oauth#register", as: :oauth_register
  get "/oauth/authorize", to: "oauth#authorize", as: :oauth_authorize
  post "/oauth/authorize", to: "oauth#authorize"
  post "/oauth/token", to: "oauth#token", as: :oauth_token

  # CORS preflight
  match "/oauth/*path", to: "oauth#options", via: :options
end
```

## Migrations

```ruby
# db/migrate/create_oauth_clients.rb
class CreateOAuthClients < ActiveRecord::Migration[7.0]
  def change
    create_table :oauth_clients, id: :uuid do |t|
      t.string :name, null: false
      t.string :client_id, null: false, index: { unique: true }
      t.string :client_secret
      t.string :client_type, null: false, default: "public"
      t.boolean :active, null: false, default: true
      t.jsonb :oauth_metadata, null: false, default: {}

      t.timestamps

      t.index :client_type
      t.index :active
    end

    create_table :oauth_access_tokens, id: :uuid do |t|
      t.references :oauth_client, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true
      t.references :authorization_code, type: :uuid, foreign_key: { to_table: :oauth_authorization_codes }

      t.string :token, null: false, index: { unique: true }
      t.string :token_type, null: false, default: "Bearer"
      t.datetime :expires_at, null: false
      t.jsonb :token_metadata, null: false, default: {}

      t.timestamps

      t.index :expires_at
    end

    create_table :oauth_authorization_codes, id: :uuid do |t|
      t.references :oauth_client, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true

      t.string :code, null: false, index: { unique: true }
      t.string :redirect_uri, null: false
      t.datetime :expires_at, null: false
      t.jsonb :pkce_data, null: false, default: {}

      t.timestamps

      t.index :expires_at
    end
  end
end
```

## Next Steps

- [PKCE Flow](02-pkce-flow.md) - Public client authorization
- [Client Management](03-client-management.md) - Dynamic registration
