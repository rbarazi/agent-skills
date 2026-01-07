---
name: mcp-rails
description: Implement Model Context Protocol (MCP) in Rails applications. Use when building AI agents that need to connect to MCP servers, expose Rails apps as MCP servers, or manage MCP subprocess containers via Docker. Covers JSON-RPC transport, OAuth 2.1 PKCE authentication, SSE streaming, and multi-worker process coordination.
license: MIT
metadata:
  author: agentify
  version: "1.0"
  source: https://github.com/rbarazi/agentify
compatibility: Requires Rails 7+, Ruby 3.2+, PostgreSQL, Faraday gem. Docker required for subprocess MCP servers.
---

# MCP Rails Implementation

Implement a complete Model Context Protocol stack in Rails, enabling your app to:
- **Connect to external MCP servers** as a client
- **Expose itself as an MCP server** for Claude Desktop, VS Code, etc.
- **Manage subprocess MCP servers** via Docker containers

## Quick Decision Guide

**What do you need?**

| Goal | Start With |
|------|------------|
| Connect to external MCP tools | [Client Core](references/01-client-core.md) |
| Build an MCP server in Rails | [Server Implementation](references/05-server-implementation.md) |
| Create multi-tool MCP server | [Tools and Schemas](references/11-tools-and-schemas.md) |
| Add UI widgets to tool results | [UI Widget Pipeline](references/12-ui-widget-pipeline.md) |
| Run MCP servers as Docker containers | [Docker Supervisor](references/04-docker-supervisor.md) |
| Add OAuth to MCP connections | [OAuth Flow](references/03-oauth-flow.md) |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Rails App                          │
├─────────────────────────────────────────────────────────────┤
│  MCP Client Layer              │  MCP Server Layer          │
│  ┌─────────────────────┐       │  ┌─────────────────────┐   │
│  │ MCPClient           │       │  │ BaseMCPServer       │   │
│  │ - Remote HTTP/SSE   │       │  │ - JSON-RPC Handler  │   │
│  │ - Subprocess Docker │       │  │ - Tool Registry     │   │
│  │ - OAuth PKCE Flow   │       │  │ - Resource Support  │   │
│  └─────────────────────┘       │  └─────────────────────┘   │
│           │                    │            │               │
│           ▼                    │            ▼               │
│  ┌─────────────────────┐       │  ┌─────────────────────┐   │
│  │ Transport Layer     │       │  │ MCP::ServersController│  │
│  │ - HTTP Transport    │       │  │ - POST /mcp/:name/  │   │
│  │ - SSE Transport     │       │  │ - GET /mcp/:name/sse│   │
│  │ - Subprocess I/O    │       │  │ - OAuth Auth        │   │
│  └─────────────────────┘       │  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Order

### Phase 1: Client Core (2-3 hours)
1. Read [Client Core](references/01-client-core.md)
2. Run scaffold: `ruby scripts/scaffold_mcp_client.rb`
3. Implement basic JSON-RPC communication

### Phase 2: Transport Layer (2-3 hours)
1. Read [Transport Layer](references/02-transport-layer.md)
2. Choose transport strategy: HTTP-first, SSE-first, or subprocess
3. Implement transport abstraction

### Phase 3: OAuth Flow (Optional, 3-4 hours)
1. Read [OAuth Flow](references/03-oauth-flow.md)
2. Implement PKCE discovery and token exchange
3. Add token storage to your tool configuration model

### Phase 4: Docker Supervisor (Optional, 4-6 hours)
1. Read [Docker Supervisor](references/04-docker-supervisor.md)
2. Implement process lifecycle management
3. Add multi-worker coordination via database locks

### Phase 5: Server Implementation (4-6 hours)
1. Read [Server Implementation](references/05-server-implementation.md)
2. Create BaseMCPServer DSL
3. Implement JSON-RPC controller

## Key Files to Create

```
app/
├── services/
│   ├── mcp_client.rb                    # Core client
│   ├── mcp_client/
│   │   ├── session.rb                   # Session management
│   │   ├── oauth_flow.rb                # OAuth PKCE
│   │   └── transport/
│   │       ├── json_rpc_transport.rb    # Base interface
│   │       ├── remote_http_transport.rb # HTTP transport
│   │       ├── remote_sse_transport.rb  # SSE transport
│   │       └── subprocess_transport.rb  # Docker transport
│   └── mcp_docker_process_supervisor.rb # Container management
├── controllers/mcp/
│   └── servers_controller.rb            # MCP server endpoints
├── mcp_servers/
│   └── base_mcp_server.rb               # Server DSL
└── models/mcp/
    ├── client.rb                        # Client registration
    └── client_session.rb                # Session tracking

db/migrate/
├── create_mcp_clients.rb
└── create_mcp_client_sessions.rb
```

## Output Checklist

When implementation is complete, verify:

- [ ] MCP client can initialize sessions and persist `Mcp-Session-Id`
- [ ] Client can list tools (`tools/list`) and call tools (`tools/call`)
- [ ] Transport fallback works (HTTP → SSE or vice versa)
- [ ] OAuth-enabled tools trigger PKCE flow when unauthorized
- [ ] Subprocess mode starts Docker containers with health checks
- [ ] Multi-worker coordination prevents duplicate supervisors
- [ ] Rails app exposes `/mcp/:server` JSON-RPC endpoint
- [ ] Optional SSE endpoint at `/mcp/:server/sse` streams responses
- [ ] UI resources return correct `mimeType` and `uri` formats

## Common Pitfalls

1. **Missing `Mcp-Session-Id` header**: Always send session ID after `initialize` call
2. **Ignoring transport fallback**: When HTTP returns 404/405, try SSE transport
3. **Treating OAuth tools like legacy tools**: Must return `WWW-Authenticate` challenge on missing token
4. **Failing to release locks for stale supervisors**: Implement timeout-based cleanup
5. **Embedding UI resources without correct format**: Ensure `mimeType` and `uri` follow spec
6. **Not handling OAuth token refresh**: Tokens expire, implement refresh or re-auth flow
7. **Process coordination race conditions**: Use database locks for subprocess ownership

## Testing Notes

### Client Testing
- Initialize session and assert `Mcp-Session-Id` persists across requests
- Exercise both HTTP and SSE transport paths
- Simulate OAuth `401` challenge and verify token exchange flow
- Test transport fallback when primary transport fails

### Server Testing
- Validate JSON-RPC success and error envelope formats
- Confirm scope enforcement on protected tools
- Test session creation, extension, and expiration
- Verify tool registration and discovery

### Subprocess Testing
- Start supervisor and wait for ready state
- Kill process and verify restart or failure marking
- Simulate multi-worker contention for supervisor ownership
- Test cleanup of stale containers

## References

- [Client Core](references/01-client-core.md) - JSON-RPC client implementation
- [Transport Layer](references/02-transport-layer.md) - HTTP, SSE, subprocess transports
- [OAuth Flow](references/03-oauth-flow.md) - PKCE discovery and token exchange
- [Docker Supervisor](references/04-docker-supervisor.md) - Container lifecycle
- [Server Implementation](references/05-server-implementation.md) - Building MCP servers
- [Session Management](references/06-session-management.md) - Client sessions
- [Multi-Worker Coordination](references/07-multi-worker-coordination.md) - Database locks
- [Host Integration](references/08-host-integration.md) - Tool configuration and app wiring
- [UI Resources](references/09-ui-resources.md) - Rich client rendering resources
- [Testing](references/10-testing.md) - Test strategies and examples
- [Tools and Schemas](references/11-tools-and-schemas.md) - Multi-tool server patterns
- [UI Widget Pipeline](references/12-ui-widget-pipeline.md) - Widget template hydration
