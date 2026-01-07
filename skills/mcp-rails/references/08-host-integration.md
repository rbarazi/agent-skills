# Host Integration

## Purpose
Wire MCP capabilities into your application's domain models and configuration system.

## Tool Configuration Storage

Store MCP configuration per-tool in a JSON field:

```ruby
# app/models/agent_tool.rb
class AgentTool < ApplicationRecord
  belongs_to :agent
  belongs_to :tool

  store_accessor :mcp_config,
    :mode,              # remote | subprocess | embedded
    :endpoint,          # Remote mode: URL
    :command,           # Subprocess mode: Docker command
    :args,              # Subprocess mode: Command arguments
    :env,               # Environment variables
    :startup_timeout,   # Subprocess startup timeout
    :oauth_client_id,
    :oauth_client_secret,
    :oauth_token_endpoint,
    :oauth_token,
    :oauth_refresh_token,
    :oauth_token_expires_at

  encrypts :oauth_client_secret, :oauth_token, :oauth_refresh_token

  def mcp_mode
    mcp_config&.dig("mode")&.to_sym || :remote
  end

  def remote?
    mcp_mode == :remote
  end

  def subprocess?
    mcp_mode == :subprocess
  end
end
```

## Configuration Patterns

### Per-Tool MCP Configuration

```ruby
# Configure MCP for a specific agent's tool
agent.configure_mcp_for_tool(tool,
  mode: :subprocess,
  config: {
    'command' => 'docker',
    'args' => ['run', '--rm', '-i', 'mcp-server:latest'],
    'env' => { 'API_KEY' => ENV['TOOL_API_KEY'] },
    'startup_timeout' => 30
  }
)
```

### Default Server Definitions

Load default MCP server definitions from YAML:

```yaml
# config/mcp_servers.yml
servers:
  filesystem:
    mode: subprocess
    command: npx
    args: ["-y", "@anthropic/mcp-server-filesystem", "/workspace"]
    startup_timeout: 30

  github:
    mode: remote
    endpoint: https://mcp.github.com/
    oauth_required: true

  slack:
    mode: remote
    endpoint: https://mcp.slack.com/
    oauth_discovery: true
```

```ruby
# app/services/mcp_server_config.rb
class MCPServerConfig
  CONFIG_PATH = Rails.root.join("config/mcp_servers.yml")

  def self.load
    @config ||= YAML.load_file(CONFIG_PATH).with_indifferent_access
  end

  def self.server(name)
    load.dig(:servers, name.to_s)
  end

  def self.defaults_for_tool(tool)
    server(tool.mcp_server_name) || {}
  end
end
```

## Agent-Level Overrides

Allow per-agent overrides without mutating global config:

```ruby
# app/models/agent.rb
class Agent < ApplicationRecord
  has_many :agent_tools
  has_many :tools, through: :agent_tools

  def mcp_config_for(tool)
    agent_tool = agent_tools.find_by(tool: tool)
    return {} unless agent_tool

    # Merge defaults with agent-specific overrides
    MCPServerConfig.defaults_for_tool(tool).merge(
      agent_tool.mcp_config || {}
    )
  end

  def build_mcp_client(tool)
    config = mcp_config_for(tool)
    mode = config['mode']&.to_sym || :remote

    MCPClient.new(
      mode: mode,
      endpoint: config['endpoint'],
      access_token: config['oauth_token'],
      supervisor_options: subprocess_options(config)
    )
  end

  private

  def subprocess_options(config)
    return nil unless config['mode'] == 'subprocess'

    {
      command: config['command'],
      args: config['args'],
      env: config['env'],
      startup_timeout: config['startup_timeout'] || 30
    }
  end
end
```

## Input Processing

### Environment Variable Interpolation

Support `${env:VAR}` and `${input:FIELD}` tokens:

```ruby
# app/services/mcp_config_interpolator.rb
class MCPConfigInterpolator
  ENV_PATTERN = /\$\{env:(\w+)\}/
  INPUT_PATTERN = /\$\{input:(\w+)\}/

  def initialize(config, inputs = {})
    @config = config.deep_dup
    @inputs = inputs.with_indifferent_access
  end

  def interpolate
    deep_interpolate(@config)
  end

  private

  def deep_interpolate(obj)
    case obj
    when Hash
      obj.transform_values { |v| deep_interpolate(v) }
    when Array
      obj.map { |v| deep_interpolate(v) }
    when String
      interpolate_string(obj)
    else
      obj
    end
  end

  def interpolate_string(str)
    str
      .gsub(ENV_PATTERN) { ENV.fetch($1, '') }
      .gsub(INPUT_PATTERN) { @inputs.fetch($1, '') }
  end
end

# Usage
config = { 'env' => { 'API_KEY' => '${env:GITHUB_TOKEN}' } }
interpolated = MCPConfigInterpolator.new(config).interpolate
```

### Secure Storage

Encrypt sensitive values at rest:

```ruby
# app/models/agent_tool.rb
class AgentTool < ApplicationRecord
  # Encrypt OAuth credentials
  encrypts :oauth_client_secret
  encrypts :oauth_token
  encrypts :oauth_refresh_token

  # For subprocess env vars containing secrets
  def secure_env
    return {} unless mcp_config&.dig('env')

    mcp_config['env'].transform_values do |value|
      if value.start_with?('encrypted:')
        decrypt_value(value)
      else
        value
      end
    end
  end
end
```

## Multi-Tenancy Support

Scope MCP configuration per account:

```ruby
# app/models/concerns/account_scoped_mcp.rb
module AccountScopedMCP
  extend ActiveSupport::Concern

  included do
    before_action :set_current_account
  end

  def mcp_client_for(tool)
    agent_tool = current_agent.agent_tools.find_by(tool: tool)
    config = agent_tool&.mcp_config || {}

    MCPClient.new(
      mode: config['mode']&.to_sym || :remote,
      endpoint: config['endpoint'],
      access_token: config['oauth_token'],
      account_id: Current.account.id  # Track for subprocess ownership
    )
  end
end
```

## Testing

```ruby
RSpec.describe AgentTool do
  describe "#mcp_mode" do
    it "defaults to remote" do
      agent_tool = build(:agent_tool, mcp_config: {})
      expect(agent_tool.mcp_mode).to eq(:remote)
    end

    it "returns configured mode" do
      agent_tool = build(:agent_tool, mcp_config: { 'mode' => 'subprocess' })
      expect(agent_tool.mcp_mode).to eq(:subprocess)
    end
  end
end

RSpec.describe MCPConfigInterpolator do
  it "interpolates environment variables" do
    allow(ENV).to receive(:fetch).with('API_KEY', '').and_return('secret123')

    config = { 'env' => { 'key' => '${env:API_KEY}' } }
    result = described_class.new(config).interpolate

    expect(result['env']['key']).to eq('secret123')
  end
end
```

## Next Steps

- [UI Resources](09-ui-resources.md) - Rich client rendering
- [Testing](10-testing.md) - Test strategies
