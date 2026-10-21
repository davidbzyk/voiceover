# OWASP Top 10 reference

## OWASP Web Application Top 10 (2021)

| # | Vulnerability | Description | Detection Patterns | Fix |
|---|--------------|-------------|-------------------|-----|
| **A01** | **Broken Access Control** | Users can act outside their intended permissions. IDOR, missing authz checks, CORS misconfiguration. | `GET /admin` accessible without admin role; user A accesses user B data via ID manipulation; missing `@require_role` decorators. | Deny by default. Enforce server-side access control. Disable directory listing. Log access failures. Invalidate JWT/sessions on logout. |
| **A02** | **Cryptographic Failures** | Sensitive data exposed due to weak or missing encryption. Cleartext storage/transmission. | Passwords stored as MD5/SHA1; HTTP endpoints serving sensitive data; hardcoded encryption keys; `TLS 1.0/1.1` in config. | HTTPS everywhere. TLS 1.2+ only. bcrypt/argon2 for passwords. Encrypt data at rest (AES-256). No sensitive data in URLs. |
| **A03** | **Injection** | Untrusted data sent to interpreter without validation. SQL, NoSQL, OS command, LDAP injection. | String concatenation in queries: `f"SELECT * FROM users WHERE id={input}"`; `os.system(user_input)`; unsanitized template rendering. | Parameterized queries/prepared statements. ORM usage. Input validation (allowlist). Escape output. WAF as defense-in-depth. |
| **A04** | **Insecure Design** | Missing or ineffective security controls at design level. Threat modeling not performed. | No rate limit on password reset; unlimited free trial creation; business logic allows negative quantities; no fraud detection. | Threat model during design. Secure design patterns. Unit/integration tests for abuse cases. Limit resource consumption by user. |
| **A05** | **Security Misconfiguration** | Default configs, open cloud storage, unnecessary features enabled, verbose errors. | Default admin credentials; S3 bucket public; stack traces in production; unnecessary HTTP methods enabled; CORS `*`. | Hardened defaults. Remove unused features/frameworks. Automated config scanning. Different credentials per environment. |
| **A06** | **Vulnerable Components** | Using libraries/frameworks with known vulnerabilities. Outdated dependencies. | `npm audit` / `pip-audit` findings; CVE matches in dependency tree; EOL runtime versions; unpatched OS packages. | Dependency scanning in CI/CD. Automated updates (Dependabot/Renovate). Remove unused dependencies. Monitor CVE databases. |
| **A07** | **Auth Failures** | Broken authentication allows credential stuffing, brute force, session hijacking. | No rate limit on login; session ID in URL; no MFA option; weak password policy; session not invalidated on password change. | MFA. Rate limit login attempts. Secure session management. Strong password policy. Rotate session on privilege change. |
| **A08** | **Software/Data Integrity** | Insecure CI/CD pipelines, unsigned updates, deserialization of untrusted data. | `pickle.loads(user_data)`; CDN scripts without SRI hashes; unsigned artifacts in pipeline; auto-merge without review. | SRI for external scripts. Signed artifacts. Review CI/CD pipeline security. Avoid deserializing untrusted data. Code review enforcement. |
| **A09** | **Logging/Monitoring Failures** | Insufficient logging, missing alerts, no incident response capability. | No logs for login failures; logs without user context; no alerting on suspicious patterns; logs stored locally only. | Log all auth events, access failures, input validation failures. Centralized logging. Alert on anomalies. Retention policy. |
| **A10** | **SSRF** | Server-side request forgery - application fetches attacker-controlled URL. | `fetch(user_provided_url)`; URL parameter for image processing; webhook URL without validation; DNS rebinding. | Allowlist for outbound URLs/IPs. Block private IP ranges (10.x, 172.16.x, 169.254.x). Disable HTTP redirects. Network segmentation. |

## OWASP API Security Top 10 (2023)

| # | Vulnerability | Description | Detection Patterns | Fix |
|---|--------------|-------------|-------------------|-----|
| **API1** | **Broken Object Level Authorization (BOLA)** | API exposes endpoints that handle object IDs, allowing attackers to access other users' objects. | `GET /api/v1/users/{id}/orders` without ownership check; sequential/predictable IDs; no authz middleware on data endpoints. | Check object ownership in every request. Use random UUIDs, not sequential IDs. Authorization middleware on all data endpoints. |
| **API2** | **Broken Authentication** | Weak or missing authentication mechanisms on API endpoints. | API keys in URLs; no token expiration; missing auth on internal APIs exposed publicly; credentials in response bodies. | OAuth 2.0 / JWT with short expiry. API key rotation. Auth on ALL endpoints. Never expose credentials in responses. Rate limit auth endpoints. |
| **API3** | **Broken Object Property Level Authorization** | API exposes all object properties, allowing mass assignment or excessive data exposure. | Response includes `password_hash`, `internal_id`, `is_admin`; PUT/PATCH accepts `role` field from user input. | Explicit response schemas (allowlist fields). Block mass assignment. Never auto-expose DB model. Separate read/write DTOs. |
| **API4** | **Unrestricted Resource Consumption** | API doesn't limit requests, payload sizes, or resource usage, enabling DoS. | No pagination (`GET /users` returns all); unlimited file upload size; no rate limiting; expensive queries without timeout. | Rate limiting per user/IP. Pagination (max page size). Payload size limits. Query complexity limits. Timeouts on all operations. |
| **API5** | **Broken Function Level Authorization** | Missing authorization checks on administrative or privileged API functions. | `DELETE /api/users/{id}` accessible to regular users; admin endpoints without role check; horizontal privilege escalation. | RBAC enforcement. Deny by default. Admin endpoints on separate route group with middleware. Regular authorization audits. |
| **API6** | **Unrestricted Access to Sensitive Business Flows** | Automated abuse of legitimate business flows (scalping, spam, credential stuffing). | Automated account creation; bulk coupon redemption; scraping sensitive listings; no CAPTCHA on sensitive flows. | Rate limit business-critical flows. CAPTCHA/device fingerprinting. Anomaly detection. Business logic abuse monitoring. |

| **API8** | **Security Misconfiguration** | Missing security headers, permissive CORS, verbose errors, default credentials on API infrastructure. | `Access-Control-Allow-Origin: *`; detailed error messages with stack traces; default API gateway credentials; TLS 1.0 enabled. | Hardened configs. Restrictive CORS. Generic error responses. Security headers. Regular config audits. |
| **API9** | **Improper Inventory Management** | Deprecated/unpatched API versions still accessible. Shadow APIs. Undocumented endpoints. | `/api/v1/` still active alongside `/api/v3/`; internal debug endpoints exposed; undocumented admin API; no API gateway. | API inventory/catalog. Deprecate and remove old versions. API gateway as single entry point. OpenAPI spec as source of truth. |
| **API10** | **Unsafe Consumption of APIs** | API trusts data from third-party APIs without validation, inheriting their vulnerabilities. | Blindly trusting webhook payloads; no validation on third-party API responses; following redirects from external APIs. | Validate ALL external API responses. Timeout and circuit breakers. Don't trust third-party data more than user input. TLS for all external calls. |

## Quick Audit Checklist

Use this as a rapid assessment during code reviews:

```
[ ] Authentication on all endpoints (A07/API2)
[ ] Authorization checks on every data access (A01/API1/API5)
[ ] Input validation and parameterized queries (A03)
[ ] No sensitive data in logs or error messages (A09/API8)
[ ] Dependencies up to date, no known CVEs (A06)
[ ] Rate limiting on all public endpoints (API4)
[ ] HTTPS everywhere, TLS 1.2+ (A02)
[ ] Security headers set (CSP, HSTS, X-Frame-Options) (A05)
[ ] LLM output treated as untrusted (LLM05)
[ ] Agent tool access follows least privilege (LLM06)
[ ] Prompt injection defenses in place (LLM01)
[ ] Token/cost budgets configured (LLM10)
```
