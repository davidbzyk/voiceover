# Secrets management

## Pre-Commit Checks

- [ ] No secrets in code (`git diff --cached | grep -i "password\|secret\|api_key\|token"`)
- [ ] `.gitignore` covers: `.env`, `.env.local`, `*.pem`, `*.key`
- [ ] `.env.example` uses placeholder values (not real secrets)

## 1. Hardcoded Secrets

### Detection Patterns

| Pattern Type | Regex / Search Term | File Types |
|--------------|---------------------|------------|
| API Keys | `API_KEY\s*=\s*['"][^'"]{20,}['"]` | .ts, .js, .py, .go, .java |
| Passwords | `password\s*=\s*['"][^'"]+['"]` | .ts, .js, .py, .go, .java |
| Tokens | `TOKEN\s*=\s*['"][^'"]{20,}['"]` | .ts, .js, .py, .go, .java |
| AWS Keys | `AKIA[0-9A-Z]{16}` | All |
| Private Keys | `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----` | .pem, .key, .ts, .js |
| Database URLs | `postgres://.*:.*@.*` | .ts, .js, .py, .env |

### Exclusions (False Positives)

- `.env.example`, `.env.template` - example files
- `README.md`, `SETUP.md` - documentation
- `**/tests/**`, `**/__tests__/**`, `*.test.*`, `*.spec.*` - test files with mock data
- Comments explaining secrets (not actual secrets)

### Severity Rules

| Condition | Severity |
|-----------|----------|
| Production AWS key (starts with AKIA) | CRITICAL |
| Database password in non-test file | CRITICAL |
| API token >32 characters | CRITICAL |
| Password in test file | HIGH |
| Development credentials | HIGH |
| Mock/example credentials in docs | MEDIUM |

### Recommendations by Tech Stack

| Stack | Recommendation |
|-------|----------------|
| Node.js | Use `dotenv` package, load from `.env` file, add `.env` to `.gitignore` |
| Python | Use `python-dotenv`, load from `.env`, add to `.gitignore` |
| Go | Use `os.Getenv("VAR_NAME")`, configure via environment |
| Java | Use Spring `@Value("${var.name}")` or Properties files |
| .NET | Use `appsettings.json` + User Secrets, configure via environment |

## Env File Patterns

| Pattern | Type | Contains Secrets? | Safe to Commit? |
|---------|------|-------------------|-----------------|
| `.env` | Local config | YES | NO |
| `.env.local` | Local overrides | YES | NO |
| `.env.*.local` | Per-env local | YES | NO |
| `.env.example` | Template/docs | NO (placeholders) | YES |
| `.env.template` | Template/docs | NO (placeholders) | YES |
| `.env.development` | Dev defaults | DEPENDS | DEPENDS (if no real secrets) |
| `.env.staging` | Staging config | YES | NO |
| `.env.production` | Prod config | YES | NO |
| `.env.test` | Test config | Usually NO | Usually YES |

## Sensitive Var Name Patterns

Variables matching these patterns should never have hardcoded defaults (C4.2):

```
SECRET, PASSWORD, PASSWD, TOKEN, API_KEY, APIKEY,
PRIVATE_KEY, CREDENTIALS, AUTH_TOKEN, ACCESS_KEY,
CLIENT_SECRET, SIGNING_KEY, ENCRYPTION_KEY, JWT_SECRET,
DATABASE_URL (contains credentials), REDIS_URL (may contain password)
```

# C1.2: .env files committed (secrets risk)
env_committed = Glob("{scan_root}/**/.env") + Glob("{scan_root}/**/.env.local")
  + Glob("{scan_root}/**/.env.*.local")
# Exclude safe templates
env_committed = filter_out(env_committed, [".env.example", ".env.template", ".env.test"])
FOR EACH file IN env_committed:
  findings.append(severity: "CRITICAL", check: "C1.2",
    issue: ".env file committed: {file}",
    location: file,
    recommendation: "Remove from tracking (git rm --cached), add to .gitignore",
    effort: "S")

# C4.2: Sensitive defaults (Layer 1 + Layer 2)
sensitive_patterns = config_rules.sensitive_var_patterns
FOR EACH var IN code_vars WHERE var.has_default == true:
  var_upper = var.name.upper()
  IF any(pattern IN var_upper for pattern IN sensitive_patterns):
    # Layer 2: verify this is truly sensitive
    context = Read(var.file, var.line +- 10 lines)
    IF default_value is not empty string AND not "changeme" AND not placeholder:
      findings.append(severity: "HIGH", check: "C4.2",
        issue: "Sensitive default for '{var.name}': hardcoded fallback bypasses env config",
        location: var.file + ":" + var.line,
        recommendation: "Remove default; require explicit env var or fail at startup",
        effort: "S")

### Secrets Protection (always required regardless of stack)


Minimal required patterns:

| Pattern | Severity if Missing |
|---------|---------------------|
| `.env` | HIGH |
| `.env.local` | HIGH |
| `.env.*.local` | HIGH |
| `*.pem` | HIGH |
| `*.key` | HIGH |
| `secrets/` | MEDIUM |

  # Check 3.1b: Secrets protection (compare with gitignore_secrets.template)
  secrets_patterns = [".env", ".env.local", "*.pem", "*.key", "secrets/"]
  FOR EACH pattern IN secrets_patterns:
    IF pattern NOT in .gitignore:
      findings.append(severity: "HIGH", issue: ".gitignore missing secrets: {pattern}",
        principle: "Ignore Files / Secrets")

1. Choose the existing supported backend: Vault, a cloud secret manager or the host's protected secret store. Keep environment boundaries and minimum privileges explicit.
2. For Vault, read `references/secret-handling.md`. Development mode and root tokens are not production configuration.
3. For GitHub Actions, read `references/secret-handling.md`. Keep pull-request validation separate from privileged jobs. Supply values to the consuming process, never interpolate them into generated shell source or print them for debugging.
4. Prefer short-lived workload identity when the backend supports it. Check issuer, audience, workload/environment restrictions and denied access before enabling retrieval.
5. Rotate through prepare, consumer switch, verification and old-credential revocation. Use the backend's supported rotation protocol; retries must not leave the database and secret store on different credentials.
6. Inspect logs, error paths, artifacts and crash reports with synthetic secret markers. Record metadata such as operation, principal and outcome rather than values.


- Authorized retrieval succeeds; a different workload or environment is denied.
- Missing credentials fail closed without exposing values.
- Rotation and rollback are exercised with synthetic data.
- Logs and artifacts contain no secret markers, including on failure.
- Exposed credentials are revoked or rotated; merely deleting their log entry is insufficient.

Masking cannot make logging secrets safe. Secret data can persist in infrastructure state, subprocess environments or backups; review those boundaries explicitly. Do not alter real credentials or deploy secret infrastructure without authorization.

## Secrets Management

```
.env files:
  ├── .env.example  → Committed (template with placeholder values)
  ├── .env          → NOT committed (contains real secrets)
  └── .env.local    → NOT committed (local overrides)

.gitignore must include:
  .env
  .env.local
  .env.*.local
  *.pem
  *.key
```

**Always check before committing:**
```bash
# Check for accidentally staged secrets
git diff --cached | grep -i "password\|secret\|api_key\|token"
```

**If a secret is ever committed, rotate it.** Deleting the line or rewriting history is not enough — assume it's compromised the moment it reaches a remote. Revoke and reissue the key first, then purge it from history.

Identify the trusted job, required secret names, environment, permitted branches and actual consuming process.

Supply secrets through process environment or an approved credential action, not expression interpolation into shell source. Avoid printing, tracing, encoding or uploading secret values. Limit scope and lifetime; isolate untrusted pull-request jobs. Verify missing-secret failure and inspect test logs using synthetic markers. Review access and rotation ownership.

Masking is a fallback, not authorization to log secrets. An environment name does not by itself establish reviewer rules; inspect the configured protection before relying on it.

Identify the deployment, secrets engine mount/version, workload identity, secret owner and rotation consumer.

Separate disposable development mode from production. For production, verify authenticated TLS, storage, recovery procedures, audit access and least-privilege policies using the installed version's documentation. Prefer workload identity with short-lived credentials. Test allowed and denied paths with synthetic values; rotate in staging, verify consumers switch, then revoke the old credential only after successful validation.

Never use a development root token for deployment or print values to test retrieval. Rotation is a coordinated state transition with rollback, not just overwriting a secret field.
