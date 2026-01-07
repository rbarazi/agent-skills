# OAuth 2.1 PKCE Flow

## Purpose
Implement Proof Key for Code Exchange (PKCE) for public clients as required by OAuth 2.1.

## PKCE Service

```ruby
# app/services/p_k_c_e_service.rb
class PKCEService
  def self.generate_code_verifier
    SecureRandom.urlsafe_base64(32)
  end

  def self.generate_code_challenge(code_verifier, method = "S256")
    case method
    when "S256"
      Base64.urlsafe_encode64(
        Digest::SHA256.digest(code_verifier),
        padding: false
      )
    when "plain"
      code_verifier
    else
      raise ArgumentError, "Unsupported method: #{method}"
    end
  end

  def self.verify_code_challenge(code_verifier, code_challenge, method)
    expected = generate_code_challenge(code_verifier, method)
    ActiveSupport::SecurityUtils.secure_compare(expected, code_challenge)
  end
end
```

## Authorization Flow with PKCE

### 1. Validate Authorization Request

```ruby
# In OAuthController
def validate_authorization_request
  @oauth_client = OAuthClient.active.find_by(client_id: params[:client_id])
  return render_error("Unknown client") unless @oauth_client

  @redirect_uri = params[:redirect_uri]
  return render_error("Invalid redirect_uri") unless @oauth_client.valid_redirect_uri?(@redirect_uri)

  @response_type = params[:response_type]
  return render_error("Only code supported") unless @response_type == "code"

  @code_challenge = params[:code_challenge]
  @code_challenge_method = params[:code_challenge_method] || "plain"

  # PKCE required for public clients
  if @oauth_client.public? && @code_challenge.blank?
    return render_error("code_challenge required for public clients")
  end

  @requested_scopes = determine_requested_scopes
  @state = params[:state]
  :valid
end
```

### 2. Issue Authorization Code with PKCE Data

```ruby
def issue_authorization_code
  auth_code = OAuthAuthorizationCode.create!(
    oauth_client: @oauth_client,
    user: Current.session&.user,
    redirect_uri: @redirect_uri,
    pkce_data: {
      code_challenge: @code_challenge,
      code_challenge_method: @code_challenge_method,
      scopes: @requested_scopes
    }
  )

  redirect_to_client_with_code(auth_code.code)
end
```

### 3. Verify PKCE on Token Exchange

```ruby
def handle_authorization_code_grant
  client = authenticate_client
  return unless client

  auth_code = OAuthAuthorizationCode.valid.find_by(code: params[:code])
  unless auth_code && auth_code.oauth_client == client
    return render_oauth_error("invalid_grant", "Invalid authorization code")
  end

  # Verify PKCE
  if auth_code.has_pkce?
    code_verifier = params[:code_verifier]
    unless code_verifier.present? && auth_code.verify_pkce(code_verifier, auth_code.code_challenge_method)
      return render_oauth_error("invalid_grant", "PKCE verification failed")
    end
  end

  # Issue token...
end
```

## Client-Side PKCE Flow

### JavaScript Example

```javascript
// 1. Generate PKCE values
function generateCodeVerifier() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64URLEncode(array);
}

async function generateCodeChallenge(verifier) {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64URLEncode(new Uint8Array(digest));
}

function base64URLEncode(buffer) {
  return btoa(String.fromCharCode(...buffer))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

// 2. Initiate authorization
const codeVerifier = generateCodeVerifier();
const codeChallenge = await generateCodeChallenge(codeVerifier);

// Store verifier for token exchange
sessionStorage.setItem('code_verifier', codeVerifier);

// Redirect to authorization
const authUrl = new URL('/oauth/authorize', 'https://your-app.com');
authUrl.searchParams.set('client_id', CLIENT_ID);
authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('code_challenge', codeChallenge);
authUrl.searchParams.set('code_challenge_method', 'S256');
authUrl.searchParams.set('state', generateState());

window.location.href = authUrl.toString();

// 3. Exchange code for token (after callback)
async function exchangeCode(code) {
  const codeVerifier = sessionStorage.getItem('code_verifier');

  const response = await fetch('/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: REDIRECT_URI,
      client_id: CLIENT_ID,
      code_verifier: codeVerifier
    })
  });

  return response.json();
}
```

## Testing

```ruby
RSpec.describe PKCEService do
  describe ".generate_code_challenge" do
    it "generates S256 challenge" do
      verifier = "test_verifier_12345678901234567890"
      challenge = described_class.generate_code_challenge(verifier, "S256")

      expect(challenge).to be_present
      expect(challenge).not_to eq(verifier)
    end

    it "returns verifier for plain method" do
      verifier = "test_verifier"
      challenge = described_class.generate_code_challenge(verifier, "plain")

      expect(challenge).to eq(verifier)
    end
  end

  describe ".verify_code_challenge" do
    it "verifies valid S256 challenge" do
      verifier = "test_verifier_12345678901234567890"
      challenge = described_class.generate_code_challenge(verifier, "S256")

      expect(described_class.verify_code_challenge(verifier, challenge, "S256")).to be true
    end

    it "rejects invalid verifier" do
      verifier = "correct_verifier"
      challenge = described_class.generate_code_challenge(verifier, "S256")

      expect(described_class.verify_code_challenge("wrong", challenge, "S256")).to be false
    end
  end
end
```

## Security Considerations

1. **Always use S256**: Plain method is only for legacy compatibility
2. **One-time use**: Invalidate authorization code after token exchange
3. **Short TTL**: Authorization codes should expire in 10 minutes
4. **Secure storage**: Use timing-safe comparison for verification

## Next Steps

- [Client Management](03-client-management.md) - Dynamic registration
- [Token Service](04-token-service.md) - Token lifecycle
