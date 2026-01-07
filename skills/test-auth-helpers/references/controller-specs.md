# Controller Spec Patterns

## Basic Authenticated Controller Spec

```ruby
# spec/controllers/agents_controller_spec.rb
RSpec.describe AgentsController, type: :controller do
  let(:account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  describe 'GET #index' do
    it 'returns success' do
      get :index
      expect(response).to be_successful
    end

    it 'assigns agents from current account' do
      agent = create(:agent, account: account)
      other_agent = create(:agent) # Different account

      get :index

      expect(assigns(:agents)).to include(agent)
      expect(assigns(:agents)).not_to include(other_agent)
    end
  end

  describe 'POST #create' do
    let(:valid_params) do
      { agent: { name: 'Test Agent', username: 'test_agent' } }
    end

    it 'creates agent in current account' do
      expect {
        post :create, params: valid_params
      }.to change(account.agents, :count).by(1)
    end

    it 'redirects on success' do
      post :create, params: valid_params
      expect(response).to redirect_to(agent_path(Agent.last))
    end

    context 'with invalid params' do
      it 'renders new with unprocessable_content status' do
        post :create, params: { agent: { name: '' } }

        expect(response).to render_template(:new)
        expect(response).to have_http_status(:unprocessable_content)
      end
    end
  end
end
```

## Testing Unauthenticated Access

```ruby
RSpec.describe AgentsController, type: :controller do
  describe 'without authentication' do
    it 'redirects to login' do
      get :index
      expect(response).to redirect_to(new_session_path)
    end

    it 'stores return URL' do
      get :index
      expect(session[:return_to_after_authenticating]).to eq(agents_url)
    end
  end
end
```

## Testing Account Scoping

```ruby
RSpec.describe AgentsController, type: :controller do
  let(:account) { create(:account) }
  let(:other_account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  describe 'GET #show' do
    it 'finds agent in current account' do
      agent = create(:agent, account: account)
      get :show, params: { id: agent.id }
      expect(response).to be_successful
    end

    it 'raises not found for other account agent' do
      other_agent = create(:agent, account: other_account)

      expect {
        get :show, params: { id: other_agent.id }
      }.to raise_error(ActiveRecord::RecordNotFound)
    end
  end
end
```

## Testing Feature Flags

```ruby
RSpec.describe Settings::UsersController, type: :controller do
  let(:account) { create(:account, allow_user_management: false) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  it 'blocks access when feature disabled' do
    get :index

    expect(response).to redirect_to(settings_path)
    expect(flash[:alert]).to eq(I18n.t('settings.users.flash.disabled'))
  end

  context 'when feature enabled' do
    let(:account) { create(:account, allow_user_management: true) }

    it 'allows access' do
      get :index
      expect(response).to be_successful
    end
  end
end
```

## Shared Examples

```ruby
# spec/support/shared_examples/authentication.rb
RSpec.shared_examples 'requires authentication' do |method, action, params = {}|
  it 'redirects to login when not authenticated' do
    send(method, action, params: params)
    expect(response).to redirect_to(new_session_path)
  end
end

RSpec.shared_examples 'scoped to current account' do
  let(:account) { create(:account) }
  let(:other_account) { create(:account) }
  let(:user) { create(:user, account: account) }

  before { setup_authenticated_user(user) }

  it 'only returns records from current account' do
    own_record = create(described_class.model_name.singular, account: account)
    other_record = create(described_class.model_name.singular, account: other_account)

    get :index

    expect(assigns(described_class.model_name.plural)).to include(own_record)
    expect(assigns(described_class.model_name.plural)).not_to include(other_record)
  end
end

# Usage
RSpec.describe AgentsController, type: :controller do
  it_behaves_like 'requires authentication', :get, :index
  it_behaves_like 'scoped to current account'
end
```
