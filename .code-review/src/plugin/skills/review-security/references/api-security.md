# API security patterns

## 1. Authentication Patterns

### API Keys

```yaml
# GOOD: API key in header
Authorization: ApiKey sk-live-abc123def456

# BAD: API key in URL (logged in server logs, browser history, referrer headers)
GET /api/data?api_key=sk-live-abc123def456

# Best practices:
api_keys:
  - Prefix keys for identification: sk-live-, sk-test-, pk-
  - Store hashed (SHA-256), not plaintext
  - Rotate regularly (90 days max)
  - Scope to specific permissions/resources
  - Rate limit per key
  - Revoke immediately on compromise
  - Different keys per environment (dev/staging/prod)
```

### OAuth 2.0

```yaml
# Recommended flows by client type
oauth2_flows:
  server_to_server: client_credentials
  web_app_with_backend: authorization_code + PKCE
  single_page_app: authorization_code + PKCE (no client secret)
  mobile_app: authorization_code + PKCE
  NEVER_USE: implicit_grant  # Deprecated, tokens exposed in URL

# Token best practices
tokens:
  access_token_lifetime: 15_minutes  # Short-lived
  refresh_token_lifetime: 7_days     # Rotate on use
  refresh_token_rotation: true       # New refresh token each time
  store_tokens: httponly_secure_cookie  # Not localStorage
  revocation: implement_revocation_endpoint
```

### JWT Best Practices

```python
# GOOD: Proper JWT configuration
jwt_config = {
    "algorithm": "RS256",           # Asymmetric, not HS256 with weak secret
    "expiration": 900,              # 15 minutes max
    "issuer": "auth.example.com",   # Always validate
    "audience": "api.example.com",  # Always validate
    "required_claims": ["sub", "exp", "iat", "iss", "aud"],
}

# BAD patterns to detect
jwt_antipatterns = [
    "algorithm: none",       # No signature verification
    "algorithm: HS256",      # With weak/shared secret
    "exp: far_future",       # Tokens that never expire
    "no audience check",     # Token reuse across services
    "secret in code",        # Hardcoded signing key
    "JWT in URL parameter",  # Logged, cached, leaked via referrer
]

# CRITICAL: Always validate
def validate_jwt(token: str) -> dict:
    return jwt.decode(
        token,
        key=PUBLIC_KEY,          # Not a weak shared secret
        algorithms=["RS256"],    # Explicit, not from token header
        audience="api.example.com",
        issuer="auth.example.com",
        options={"require": ["exp", "iat", "sub"]},
    )
```

## 3. Input Validation

### Schema Validation

```python
from pydantic import BaseModel, Field, validator

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(regex=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    age: int = Field(ge=13, le=150)
    role: str = Field(default="user")  # Ignore if user tries to set "admin"

    @validator("role")
    def restrict_role(cls, v):
        if v not in ("user", "viewer"):  # Only allow safe roles
            return "user"
        return v

    class Config:
        extra = "forbid"  # Reject unknown fields (prevent mass assignment)
```

### Type Checking and Size Limits

```yaml
validation_rules:
  string_fields:
    max_length: 10_000         # No unbounded strings
    strip_whitespace: true
    reject_null_bytes: true     # \x00 can cause issues

  numeric_fields:
    define_min_max: true        # Always set bounds
    reject_nan_infinity: true   # Can break math operations

  array_fields:
    max_items: 100              # No unbounded arrays
    validate_each_item: true

  file_uploads:
    max_size: 10MB
    allowed_types: ["image/jpeg", "image/png", "application/pdf"]
    validate_magic_bytes: true  # Don't trust Content-Type header alone
    scan_for_malware: true

  query_parameters:
    max_page_size: 100
    default_page_size: 20
    max_query_length: 500
```

## 4. Webhook Security

### HMAC Signature Verification

```python
import hmac
import hashlib
import time

def verify_webhook(payload: bytes, headers: dict, secret: str) -> bool:
    """Full webhook verification: signature + timestamp."""

    signature = headers.get("X-Webhook-Signature")
    timestamp = headers.get("X-Webhook-Timestamp")

    if not signature or not timestamp:
        return False

    # 1. Prevent replay attacks (5-minute window)
    if abs(time.time() - int(timestamp)) > 300:
        return False

    # 2. Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()

    # 3. Constant-time comparison (prevents timing attacks)
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Webhook Best Practices

```yaml
webhook_security:
  sending:
    - Sign every payload with HMAC-SHA256
    - Include timestamp in signature
    - Send unique event ID for idempotency
    - Use HTTPS only
    - Implement retry with exponential backoff
    - Rotate signing secrets periodically

  receiving:
    - Verify signature BEFORE any processing
    - Reject requests older than 5 minutes (replay protection)
    - Implement idempotency (store processed event IDs)
    - Return 200 quickly, process async
    - Don't trust payload data blindly (validate schema)
    - Rate limit incoming webhooks
    - Log all webhook events for audit
```

## 5. CORS Configuration

```python
# DANGEROUS: Allow everything
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Credentials: true  # INVALID with * origin

# SECURE: Explicit allowlist
CORS_CONFIG = {
    "allowed_origins": [
        "https://app.example.com",
        "https://admin.example.com",
    ],
    "allowed_methods": ["GET", "POST", "PUT", "DELETE"],
    "allowed_headers": ["Authorization", "Content-Type"],
    "allow_credentials": True,
    "max_age": 3600,  # Preflight cache (1 hour)
    "expose_headers": ["X-RateLimit-Remaining"],
}

# Anti-patterns to detect
cors_antipatterns = [
    "Access-Control-Allow-Origin: *",                  # Too permissive
    "reflect Origin header as Allow-Origin",           # Effectively * with credentials
    "Access-Control-Allow-Origin: null",               # Exploitable
    "Allow-Origin without credentials but with auth",  # Inconsistent
]
```

## 6. Security Headers Checklist

```yaml
# Required security headers for all API responses
security_headers:
  # Prevent MIME sniffing
  X-Content-Type-Options: "nosniff"

  # Prevent clickjacking (for HTML responses)
  X-Frame-Options: "DENY"

  # XSS protection (legacy browsers)
  X-XSS-Protection: "0"  # Disable, use CSP instead

  # HTTPS enforcement
  Strict-Transport-Security: "max-age=31536000; includeSubDomains; preload"

  # Content Security Policy (for HTML responses)
  Content-Security-Policy: "default-src 'self'; script-src 'self'; style-src 'self'"

  # Referrer policy
  Referrer-Policy: "strict-origin-when-cross-origin"

  # Permissions policy
  Permissions-Policy: "camera=(), microphone=(), geolocation=()"

  # Remove server info headers
  Server: REMOVE_THIS_HEADER
  X-Powered-By: REMOVE_THIS_HEADER

  # Cache control for sensitive data
  Cache-Control: "no-store, no-cache, must-revalidate, private"
  Pragma: "no-cache"
```

## 7. Common API Vulnerabilities

### BOLA / IDOR (Broken Object Level Authorization)

```python
# VULNERABLE: No ownership check
@app.get("/api/users/{user_id}/orders")
def get_orders(user_id: int):
    return db.query(Order).filter(Order.user_id == user_id).all()
    # Any authenticated user can access any other user's orders

# SECURE: Enforce ownership
@app.get("/api/users/{user_id}/orders")
def get_orders(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Forbidden")
    return db.query(Order).filter(Order.user_id == user_id).all()
```

### Mass Assignment

```python
# VULNERABLE: Accept all fields from request
@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: dict):
    db.query(User).filter(User.id == user_id).update(data)
    # Attacker sends {"role": "admin", "is_verified": true}

# SECURE: Explicit allowlist of updatable fields
class UserUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    # role and is_verified are NOT included

@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserUpdateRequest):
    db.query(User).filter(User.id == user_id).update(
        data.dict(exclude_unset=True)
    )
```

### Excessive Data Exposure

```python
# VULNERABLE: Return entire database model
@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    return db.query(User).get(user_id).__dict__
    # Returns: id, name, email, password_hash, ssn, internal_notes, ...

# SECURE: Explicit response schema
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    # Only public fields

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    return db.query(User).get(user_id)
```

## Quick Security Review Checklist

```
Authentication:
[ ] All endpoints require authentication (unless explicitly public)
[ ] API keys are in headers, not URLs
[ ] JWTs use RS256 with short expiry
[ ] OAuth 2.0 with PKCE for public clients
[ ] Token rotation implemented

Authorization:
[ ] Ownership check on every data access (BOLA prevention)
[ ] Role check on every privileged operation
[ ] Mass assignment protection (explicit field allowlists)
[ ] Response schemas filter sensitive fields

Input/Output:
[ ] Schema validation on all inputs
[ ] Size limits on all fields, arrays, and files
[ ] Parameterized queries (no string concatenation)
[ ] Generic error messages (no stack traces)

Transport:
[ ] HTTPS everywhere (TLS 1.2+)
[ ] Security headers set
[ ] CORS explicitly configured
[ ] HSTS enabled

Operations:
[ ] Rate limiting per user/IP
[ ] Request logging with correlation IDs
[ ] Webhook signatures verified
[ ] Idempotency keys for mutations
[ ] Dependencies scanned for CVEs
```
