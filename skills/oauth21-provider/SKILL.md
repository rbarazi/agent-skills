---
name: oauth21-provider
description: Implement an RFC-compliant OAuth 2.1 authorization server in Rails applications. Use when building apps that need to authorize third-party clients (like MCP clients, API consumers, or external integrations) using industry-standard OAuth flows with PKCE, dynamic client registration, and token management.
license: MIT
metadata:
  author: agentify
  version: "1.0"
  source: https://github.com/rbarazi/agentify
compatibility: Requires Rails 7+, Ruby 3.2+, PostgreSQL with encrypted columns support.
---

# OAuth 2.1 Provider for Rails

Build a complete RFC-compliant OAuth 2.1 authorization server enabling your Rails app to:
- **Authorize third-party clients** with consent screens
- **Issue access tokens** via authorization code + PKCE or client credentials
- **Dynamic client registration** (RFC 7591)
- **OAuth metadata discovery** (RFC 8414)
- **Comprehensive audit logging and monitoring**

## Quick Decision Guide

| Goal | Start With |
|------|------------|
| Basic OAuth provider | [Core Implementation](references/01-core-implementation.md) |
| PKCE for public clients | [PKCE Flow](references/02-pkce-flow.md) |
| Client registration | [Client Management](references/03-client-management.md) |
| Token lifecycle | [Token Service](references/04-token-service.md) |
| Monitoring & audit | [Monitoring](references/05-monitoring.md) |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     OAuth 2.1 Provider                       │
├─────────────────────────────────────────────────────────────┤
│  Discovery Layer                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ GET /.well-known/oauth-authorization-server             │ │
│  │ Returns: issuer, authorization_endpoint, token_endpoint │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  Authorization Layer                                         │
│  ┌─────────────────────┐   ┌─────────────────────┐         │
│  │ /oauth/authorize    │   │ /oauth/token        │         │
│  │ - Consent screen    │   │ - client_credentials│         │
│  │ - PKCE validation   │   │ - authorization_code│         │
│  │ - Code issuance     │   │ - refresh_token     │         │
│  └─────────────────────┘   └─────────────────────┘         │
│                                                              │
│  Client Layer                                                │
│  ┌─────────────────────┐   ┌─────────────────────┐         │
│  │ /oauth/register     │   │ OAuthClient         │         │
│  │ - Dynamic DCR       │   │ OAuthAccessToken    │         │
│  │ - RFC 7591          │   │ OAuthAuthorizationCode│       │
│  └─────────────────────┘   └─────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Order

### Phase 1: Core Models (1-2 hours)
1. Read [Core Implementation](references/01-core-implementation.md)
2. Generate migrations for OAuth tables
3. Create OAuthClient, OAuthAccessToken, OAuthAuthorizationCode models

### Phase 2: Authorization Endpoints (2-3 hours)
1. Read [PKCE Flow](references/02-pkce-flow.md)
2. Implement OAuthController with discovery, authorize, token endpoints
3. Create consent screen view

### Phase 3: Client Management (1-2 hours)
1. Read [Client Management](references/03-client-management.md)
2. Implement ClientRegistrationService
3. Add dynamic client registration endpoint

### Phase 4: Token Service (1-2 hours)
1. Read [Token Service](references/04-token-service.md)
2. Implement TokenService for issuance and validation
3. Add cleanup tasks for expired tokens

### Phase 5: Monitoring (Optional, 1-2 hours)
1. Read [Monitoring](references/05-monitoring.md)
2. Implement OAuthMonitoringService
3. Add event tracking and cleanup tasks

## Key Files to Create

```
app/
├── controllers/
│   └── oauth_controller.rb           # Main OAuth endpoints
├── models/
│   ├── oauth_client.rb               # Client registration
│   ├── oauth_access_token.rb         # Bearer tokens
│   ├── oauth_authorization_code.rb   # Auth codes with PKCE
│   ├── oauth_refresh_token.rb        # Refresh tokens
│   └── oauth_event.rb                # Audit logging
├── services/
│   ├── token_service.rb              # Token issuance/validation
│   ├── client_registration_service.rb # Dynamic registration
│   ├── p_k_c_e_service.rb            # PKCE handling
│   └── oauth_monitoring_service.rb   # Stats and cleanup
├── views/
│   └── oauth/
│       └── authorize.html.erb        # Consent screen
└── concerns/
    ├── oauth_authentication.rb       # Auth concern
    └── oauth_cors.rb                 # CORS handling

config/
├── initializers/
│   └── oauth_security.rb             # Security config
└── oauth_security.yml                # Security settings

db/migrate/
├── create_oauth_clients.rb
├── create_oauth_access_tokens.rb
├── create_oauth_authorization_codes.rb
└── create_oauth_events.rb
```

## Output Checklist

When implementation is complete, verify:

- [ ] `GET /.well-known/oauth-authorization-server` returns RFC 8414 metadata
- [ ] Discovery includes: `issuer`, `authorization_endpoint`, `token_endpoint`, `registration_endpoint`
- [ ] Discovery includes: `grant_types_supported`, `response_types_supported`, `scopes_supported`
- [ ] `POST /oauth/register` supports dynamic client registration (RFC 7591)
- [ ] Registration validates redirect URIs (HTTPS required except localhost)
- [ ] `GET /oauth/authorize` renders consent screen for logged-in users
- [ ] Authorization code flow enforces PKCE for public clients
- [ ] `POST /oauth/token` handles `authorization_code` grant with PKCE verification
- [ ] `POST /oauth/token` handles `client_credentials` grant for confidential clients
- [ ] Token validation is timing-safe using `secure_compare`
- [ ] Scope validation is centralized and enforced on protected endpoints
- [ ] Expired tokens and codes are cleaned up automatically

## Common Pitfalls

1. **Missing PKCE for public clients**: OAuth 2.1 requires PKCE for all public clients
2. **Timing attacks on token validation**: Always use `secure_compare` for token comparison
3. **Token leakage**: Encrypt tokens at rest with Rails `encrypts` declaration
4. **CORS issues**: Configure proper CORS headers for browser-based clients
5. **Redirect URI validation**: Strict validation to prevent open redirector attacks
6. **HTTP for non-localhost**: Only allow HTTP for localhost redirect URIs
7. **Fragment in redirect URI**: Reject URIs containing fragments (`#`)
8. **Missing state parameter**: Always validate and return state for CSRF protection

## Testing Notes

### Discovery Testing
- Verify `/.well-known/oauth-authorization-server` returns valid JSON
- Confirm all required RFC 8414 fields are present
- Test that endpoints URLs are absolute

### Registration Testing
- Test public client creation (no secret returned)
- Test confidential client creation (secret returned)
- Verify HTTP redirect URIs rejected (except localhost)
- Verify fragment-containing URIs rejected

### Authorization Flow Testing
- Test PKCE required for public clients
- Test state parameter preservation
- Test consent screen renders correctly
- Test code issuance and single-use

### Token Exchange Testing
- Test PKCE verification with correct verifier
- Test PKCE failure with incorrect verifier
- Test code expiration (10 min default)
- Test redirect_uri matching

### Security Testing
- Verify timing-safe token comparison
- Test rate limiting on token endpoint
- Verify token encryption at rest
- Test scope enforcement

## References

- [Core Implementation](references/01-core-implementation.md) - Models and controller
- [PKCE Flow](references/02-pkce-flow.md) - Public client authorization
- [Client Management](references/03-client-management.md) - Dynamic registration
- [Token Service](references/04-token-service.md) - Token lifecycle
- [Monitoring](references/05-monitoring.md) - Audit and cleanup
