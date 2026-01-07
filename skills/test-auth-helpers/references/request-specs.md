# Request Spec Patterns

## API Authentication

```ruby
# spec/requests/api/agents_spec.rb
RSpec.describe 'API Agents', type: :request do
  let(:account) { create(:account) }
  let(:user) { create(:user, account: account) }
  let!(:agent) { create(:agent, account: account) }

  describe 'GET /api/agents' do
    it 'returns agents with valid auth' do
      get '/api/agents', headers: auth_headers_for(user)

      expect(response).to have_http_status(:ok)
      expect(json_response['agents'].size).to eq(1)
    end

    it 'returns 401 without auth' do
      get '/api/agents'

      expect(response).to have_http_status(:unauthorized)
    end

    it 'returns 401 with invalid token' do
      get '/api/agents', headers: { 'Authorization' => 'Bearer invalid' }

      expect(response).to have_http_status(:unauthorized)
    end
  end

  describe 'POST /api/agents' do
    let(:valid_params) do
      { agent: { name: 'New Agent', username: 'new_agent' } }
    end

    it 'creates agent with valid auth' do
      expect {
        post '/api/agents',
             params: valid_params.to_json,
             headers: json_auth_headers_for(user)
      }.to change(Agent, :count).by(1)

      expect(response).to have_http_status(:created)
    end
  end

  private

  def json_response
    JSON.parse(response.body)
  end

  def json_auth_headers_for(user)
    auth_headers_for(user).merge({
      "Content-Type" => "application/json",
      "Accept" => "application/json"
    })
  end
end
```

## Session API Specs

```ruby
RSpec.describe 'API Sessions', type: :request do
  let!(:user) { create(:user, email_address: 'api@example.com') }

  describe 'POST /api/session' do
    it 'creates session with valid credentials' do
      post '/api/session', params: {
        email_address: 'api@example.com',
        password: 'password'
      }

      expect(response).to have_http_status(:ok)
      expect(json_response['session_id']).to be_present
      expect(json_response['user']['email']).to eq('api@example.com')
    end

    it 'returns 401 with invalid credentials' do
      post '/api/session', params: {
        email_address: 'api@example.com',
        password: 'wrong'
      }

      expect(response).to have_http_status(:unauthorized)
      expect(json_response['error']).to be_present
    end
  end

  describe 'DELETE /api/session' do
    it 'destroys the session' do
      session = create(:session, user: user)

      delete '/api/session', headers: {
        'Authorization' => "Bearer #{session.id}"
      }

      expect(response).to have_http_status(:ok)
      expect(Session.find_by(id: session.id)).to be_nil
    end
  end

  private

  def json_response
    JSON.parse(response.body)
  end
end
```

## Testing Account Scoping

```ruby
RSpec.describe 'API Agents', type: :request do
  let(:account) { create(:account) }
  let(:other_account) { create(:account) }
  let(:user) { create(:user, account: account) }

  it 'cannot access other account resources' do
    other_agent = create(:agent, account: other_account)

    get "/api/agents/#{other_agent.id}",
        headers: auth_headers_for(user)

    expect(response).to have_http_status(:not_found)
  end

  it 'only lists own account resources' do
    own_agent = create(:agent, account: account)
    other_agent = create(:agent, account: other_account)

    get '/api/agents', headers: auth_headers_for(user)

    agent_ids = json_response['agents'].map { |a| a['id'] }
    expect(agent_ids).to include(own_agent.id)
    expect(agent_ids).not_to include(other_agent.id)
  end
end
```

## Rate Limiting Tests

```ruby
RSpec.describe 'Rate Limiting', type: :request do
  it 'blocks after too many password reset requests' do
    6.times do
      post passwords_path, params: { email_address: 'test@example.com' }
    end

    expect(response).to redirect_to(new_password_path)
    follow_redirect!
    expect(response.body).to include(I18n.t('passwords.flash.rate_limit'))
  end
end
```
