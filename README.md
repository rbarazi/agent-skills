# Agentify Agent Skills

Production-ready Claude Code skills extracted from [Agentify](https://github.com/rbarazi/agentify). These patterns power real AI agent infrastructure and have been battle-tested in production.

## Installation

### Register the Marketplace

```bash
# In Claude Code
/plugin marketplace add your-org/agent-skills
```

### Install Individual Skills

```bash
# Install a single skill
/plugin install rails8-authentication

# Install from this marketplace specifically
/plugin install mcp-rails@your-org/agent-skills
```

### Manual Installation

Copy any skill folder to your project's `.claude/skills/` directory:

```bash
cp -r skills/llm-gateway /path/to/your-project/.claude/skills/
```

## Skill Catalog

### Authentication & Authorization

| Skill | Description |
|-------|-------------|
| [rails8-authentication](skills/rails8-authentication) | Rails 8 built-in auth with `has_secure_password`, session cookies, and the Authentication concern |
| [oauth21-provider](skills/oauth21-provider) | RFC-compliant OAuth 2.1 authorization server with PKCE and dynamic client registration |
| [password-reset-flow](skills/password-reset-flow) | Secure password reset with Rails 8's built-in token generation |
| [session-management](skills/session-management) | Database-backed sessions with audit trails and multi-device support |

### Multi-Tenant Architecture

| Skill | Description |
|-------|-------------|
| [multi-tenant-accounts](skills/multi-tenant-accounts) | Account-based multi-tenancy for SaaS applications |
| [user-management](skills/user-management) | User CRUD with permissions and feature flags in multi-tenant context |

### AI Infrastructure

| Skill | Description |
|-------|-------------|
| [llm-gateway](skills/llm-gateway) | Multi-provider LLM abstraction (OpenAI, Anthropic, Gemini, Ollama) with feature detection and cost tracking |
| [mcp-rails](skills/mcp-rails) | Complete MCP implementation: client, server, Docker subprocess management, OAuth integration |

### UI Widgets

| Skill | Description |
|-------|-------------|
| [chatkit-frontend-bootstrap](skills/chatkit-frontend-bootstrap) | Embed OpenAI ChatKit widget with Turbo navigation and theme sync |
| [chatkit-rails-backend](skills/chatkit-rails-backend) | SSE streaming backend for ChatKit with thread management and attachments |
| [mcp-widget-authoring](skills/mcp-widget-authoring) | Create visual widgets in MCP tool responses with JSON Schema validation |

### Slack Integration

| Skill | Description |
|-------|-------------|
| [slack-channel-integration](skills/slack-channel-integration) | Slack as AI agent channel: OAuth, webhooks, event processing |
| [slack-blockkit-ui](skills/slack-blockkit-ui) | Render rich Block Kit messages from agent tool results |
| [slack-mcp-server](skills/slack-mcp-server) | MCP servers for Slack API operations (canvases, messages) |
| [slack-work-objects](skills/slack-work-objects) | Trackable Work Objects with link unfurling and flexpanes |

### Testing

| Skill | Description |
|-------|-------------|
| [test-auth-helpers](skills/test-auth-helpers) | Authentication testing patterns with RSpec and FactoryBot |

### Meta

| Skill | Description |
|-------|-------------|
| [code-pattern-extraction](skills/code-pattern-extraction) | Extract reusable patterns from codebases into new Skills |

## Skill Compatibility

All skills are designed for:
- **Rails 7+** (most optimized for Rails 8)
- **Ruby 3.2+**
- **PostgreSQL** (for skills requiring database features)

Individual skills may have additional requirements documented in their SKILL.md files.

## Skill Structure

Each skill follows the [Agent Skills specification](https://github.com/anthropics/skills):

```
skill-name/
├── SKILL.md          # Main instructions with YAML frontmatter
├── references/       # Detailed documentation (loaded on demand)
├── scripts/          # Executable utilities (optional)
└── assets/           # Templates and static files (optional)
```

## Creating New Skills

Use the `code-pattern-extraction` skill to create new skills from your codebase:

```bash
# In Claude Code with this marketplace installed
# Ask Claude to extract patterns from your code
```

Or use the scaffolding scripts:

```bash
# Initialize a new skill
python skills/code-pattern-extraction/scripts/init_skill.py my-new-skill --path .claude/skills

# Validate before publishing
python skills/code-pattern-extraction/scripts/package_skill.py skills/my-new-skill --validate-only
```

## Private Marketplace

This marketplace can be kept private:

1. **Private GitHub repo**: Works with your existing Git credentials
2. **Self-hosted Git**: Point to your internal GitLab/Gitea
3. **Git submodule**: Include in private projects as a submodule

```bash
# Add as submodule to a private project
git submodule add git@github.com:your-org/agent-skills.git .claude/agent-skills
```

## Contributing

1. Fork this repository
2. Create a skill following the structure in `skills/code-pattern-extraction/SKILL.md`
3. Validate with `package_skill.py --validate-only`
4. Submit a pull request

## License

MIT License - see individual skills for any specific licensing.
