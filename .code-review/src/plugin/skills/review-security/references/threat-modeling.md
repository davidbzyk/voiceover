# Threat modeling reference

## Threat Modeling (Start Here)

Before reaching for controls, spend five minutes thinking like an attacker:

- [ ] Trust boundaries mapped (requests, uploads, webhooks, third-party APIs, LLM output)
- [ ] Assets named (credentials, PII, payment data, admin actions, money movement)
- [ ] STRIDE run per boundary (Spoofing, Tampering, Repudiation, Info disclosure, DoS, Elevation)
- [ ] Abuse cases written next to use cases ("how would I misuse this?")

## When to Use What

| Method | Best For | Effort | Output |
|--------|----------|--------|--------|
| **STRIDE** | Component-level analysis, quick threat identification | Low-Medium | List of threats per component |
| **PASTA** | Full system risk analysis, business-aligned | Medium-High | Prioritized attack scenarios |
| **Both** | Critical systems, compliance requirements | High | Complete threat landscape |

**Rule of thumb:**
- Quick code review or PR? -> STRIDE on changed components
- New system design or architecture review? -> PASTA full process
- Production system with sensitive data? -> Both (PASTA for strategy, STRIDE for each component)

STRIDE categorizes threats into six types. For each, ask: "Can an attacker do this to my system?"

### S - Spoofing (Identity)

**Question:** Can someone pretend to be another user, service, or component?

**Detection patterns:** Missing auth middleware, hardcoded/weak secrets, no mutual TLS between services.

**Mitigations:** Strong authentication (OAuth 2.0, mTLS), HMAC signature validation, API key rotation.

### T - Tampering (Data Integrity)

**Question:** Can someone modify data in transit, at rest, or in processing?

**Detection patterns:** No input validation, HTTP endpoints, missing integrity checks on files, no checksums.

**Mitigations:** Input validation/sanitization, HTTPS everywhere, signed artifacts, database constraints.

### R - Repudiation (Accountability)

**Question:** Can someone perform an action and deny it later?

**Detection patterns:** Missing audit logs, logs without timestamps/user IDs, mutable log storage, no log forwarding.

**Mitigations:** Immutable audit logs (append-only), centralized logging (SIEM), signed log entries, write-once storage.

### I - Information Disclosure

**Question:** Can someone access data they shouldn't see?

**Detection patterns:** Verbose errors in production, exposed config files, missing access controls on endpoints, debug mode enabled.

**Mitigations:** Generic error messages, secrets in vault (not env files), access control on all endpoints, disable debug in production.

### D - Denial of Service

**Question:** Can someone make the system unavailable?

**Detection patterns:** Missing rate limits, unbounded queries, regex without timeout, no resource limits on containers.

**Mitigations:** Rate limiting, pagination, query limits, circuit breakers, resource quotas, CDN/WAF.

### E - Elevation of Privilege

**Question:** Can someone gain permissions they shouldn't have?

**Detection patterns:** Missing authorization checks (not just authentication), mass assignment vulnerabilities, path traversal, insecure deserialization.

**Mitigations:** Role-based access control (RBAC), allowlist for assignable fields, input path validation, principle of least privilege.

### STRIDE Analysis

| Category | Threat | Severity | Mitigation |
|----------|--------|----------|------------|
| **Spoofing** | Attacker sends fake Stripe events | CRITICAL | Verify `Stripe-Signature` header with HMAC |
| **Tampering** | Event payload modified in transit | HIGH | HTTPS + signature verification |
| **Repudiation** | Cannot prove event was received/processed | MEDIUM | Log all webhook events with idempotency key |
| **Info Disclosure** | Error responses leak internal state | MEDIUM | Return generic 200/400, log details internally |
| **DoS** | Flood endpoint with fake events | HIGH | Rate limit by IP, verify signature before processing |
| **EoP** | Webhook triggers admin-level operations | HIGH | Webhook handler runs with minimal permissions, validate event type |

### STRIDE Analysis

| Category | Threat | Severity | Mitigation |
|----------|--------|----------|------------|
| **Spoofing** | Prompt injection makes agent impersonate admin | CRITICAL | Server-side authorization and least-privilege tools; human approval for privileged actions (prompt hardening is not a boundary) |
| **Tampering** | Agent modifies files/DB beyond intended scope | CRITICAL | Read-only by default, allowlist of writable paths |
| **Repudiation** | Cannot trace which agent action caused damage | HIGH | Log every tool call with full context |
| **Info Disclosure** | Agent leaks secrets from context/env to output | CRITICAL | Strip secrets before context injection, output filtering |
| **DoS** | Agent enters infinite loop, burns API credits | HIGH | Iteration limits, token budgets, timeout per operation |
| **EoP** | Agent escapes sandbox via tool chaining | CRITICAL | Least-privilege tool access, no shell access, sandboxed execution |

## Quick Reference: Severity Matrix

| | Low Impact | Medium Impact | High Impact |
|---|---|---|---|
| **High Probability** | MEDIUM | HIGH | CRITICAL |
| **Medium Probability** | LOW | MEDIUM | HIGH |
| **Low Probability** | LOW | LOW | MEDIUM |

Controls bolted on without a threat model are guesses. Before hardening, spend five minutes thinking like an attacker:

1. **Map the trust boundaries.** Where does untrusted data cross into your system? HTTP requests, form fields, file uploads, webhooks, third-party APIs, message queues, and **LLM output**. Every boundary is attack surface.
2. **Name the assets.** What's worth stealing or breaking? Credentials, PII, payment data, admin actions, money movement.
3. **Run STRIDE over each boundary** — a quick lens, not a ceremony:

| Threat | Ask | Typical mitigation |
|---|---|---|
| **S**poofing | Can someone impersonate a user/service? | Authentication, signature verification |
| **T**ampering | Can data be altered in transit or at rest? | Integrity checks, parameterized queries, HTTPS |
| **R**epudiation | Can an action be denied later? | Audit logging of security events |
| **I**nformation disclosure | Can data leak? | Encryption, field allowlists, generic errors |
| **D**enial of service | Can it be overwhelmed? | Rate limiting, input size caps, timeouts |
| **E**levation of privilege | Can a user gain rights they shouldn't? | Authorization checks, least privilege |

4. **Write abuse cases next to use cases.** For each feature, ask "how would I misuse this?" — then make that your first test.

If you can't name the trust boundaries for a feature, you're not ready to secure it. This is OWASP **A04: Insecure Design** — most breaches begin in design, not code.

**Attack surface inventory** -- New endpoints (who can access?), new data stores (sensitivity? access control?), new integrations (what crosses the trust boundary?), new user inputs (validation mentioned?). Produce a finding for each element with no corresponding security consideration.

**Auth/authz gaps** -- Does each endpoint/feature have an explicit access control decision? Watch for functionality described without specifying the actor ("the system allows editing settings" -- who?). New roles or permission changes need defined boundaries.

**Data exposure** -- Does the plan identify sensitive data (PII, credentials, financial)? Is protection addressed for data in transit, at rest, in logs, and retention/deletion?

**Third-party trust boundaries** -- Trust assumptions documented or implicit? Credential storage and rotation defined? Failure modes (compromise, malicious data, unavailability) addressed? Minimum necessary data shared?

**Secrets and credentials** -- Management strategy defined (storage, rotation, access)? Risk of hardcoding, source control, or logging? Environment separation?

**Plan-level threat model** -- Not a full model. Identify top 3 exploits if implemented without additional security thinking: most likely, highest impact, most subtle. One sentence each plus needed mitigation.
