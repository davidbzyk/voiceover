# Project rule files

## 3-Tier Priority Chain

| Priority | Source | When |
|----------|--------|------|
| **1. Custom** | `docs/project/dependency_rules.yaml` | Project team defined own boundaries |
| **3. Auto-detected** | Directory structure heuristics | No docs, infer from project layout |

## Rule Types

Inspired by [dependency-cruiser](https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md):

| Type | Semantics | Violation severity |
|------|-----------|-------------------|
| **forbidden** | This dependency MUST NOT exist | Per rule (CRITICAL/HIGH/MEDIUM) |
| **allowed** | ONLY listed dependencies are permitted (whitelist) | MEDIUM for unlisted deps |
| **required** | This dependency MUST exist | MEDIUM for missing deps |

## Custom Project Rules Format

Projects define their own boundaries in `docs/project/dependency_rules.yaml`:

```yaml
modules:
  - {name: auth, path: "src/auth/**"}
  - {name: billing, path: "src/billing/**"}
  - {name: shared, path: "src/shared/**"}
  - {name: legacy, path: "src/legacy/**"}

forbidden:
  - {from: billing, to: auth, severity: HIGH, reason: "Billing must not know about auth internals"}
  - {from: "src/*/internal/**", to: "src/*/internal/**", cross: true, severity: MEDIUM, reason: "Internal packages are private"}
  - {from: "*", to: legacy, severity: LOW, reason: "Avoid new dependencies on legacy code"}

allowed:
  - {from: "*", to: shared, reason: "Shared module is accessible by all"}

required:
  - {module: "src/*/", must_depend_on: "src/shared/logging", reason: "All modules must use centralized logging"}
```

## Pattern Matching

- `*` — matches any single module name
- `**/` — matches any number of directory levels
- `features/*/` — matches any direct child of features/
- `cross: true` — only flag violations BETWEEN different groups (not within same module)

- **Adaptive architecture** -- never assume one style; detect from project structure or docs
- **3-tier priority** -- custom rules > architecture.md > auto-detection
- **Hybrid support** -- projects mix styles; apply different presets per zone
- **Custom = safe mode** -- if no pattern detected, only check cycles + metrics (no false boundary violations)

1. For each entry in `custom_risks`, validate that it has:
   - `name` — non-empty string
   - `question` — the diagnostic question to ask
   - `symptoms` — non-empty list of symptom patterns
   - `severity` — map with at least one of: `critical`, `warning`, `suggestion`

During the analysis, treat each custom risk as an additional step after the standard
process:

- Use `question` as the diagnostic question
- Use `symptoms` as the symptom lookup list
- Use the `severity` map for tier classification

# custom_risks:
#   C1:
#     name: Security Debt
#     question: "Are there known security vulnerabilities being deferred?"
#     symptoms:
#       - "Hardcoded credentials or API keys"
#       - "Missing input validation on user-facing endpoints"
#       - "Dependencies with known CVEs not updated"
#     severity:
#       critical: "Exploitable vulnerability in production"
#       warning: "Known vulnerability with mitigating controls"
#       suggestion: "Best-practice deviation with no current exposure"
#   C2:
#     name: Accessibility Debt
#     question: "Does the UI meet WCAG 2.1 AA standards?"
#     symptoms:
#       - "Missing alt text on images"
#       - "Insufficient color contrast ratios"
#       - "No keyboard navigation support"
#     severity:
#       critical: "Core flows inaccessible to screen readers"
#       warning: "Secondary flows missing accessibility support"
#       suggestion: "Minor ARIA label improvements"

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

## Framework-Managed Variables (Layer 2 Exclusions)

Exclude from C2.1 (Code→Example sync) — these are auto-set by frameworks:

| Framework | Auto-Managed Vars |
|-----------|-------------------|
| Node.js | `NODE_ENV`, `PORT` |
| Next.js | `NEXT_PUBLIC_*` prefix, `NEXT_RUNTIME`, `NEXT_PHASE` |
| Vite | `VITE_*` prefix, `MODE`, `BASE_URL`, `PROD`, `DEV` |
| Python/Django | `DJANGO_SETTINGS_MODULE` |
| Python/Flask | `FLASK_APP`, `FLASK_ENV`, `FLASK_DEBUG` |
| .NET | `ASPNETCORE_ENVIRONMENT`, `ASPNETCORE_URLS`, `DOTNET_ENVIRONMENT` |
| Go | `GOPATH`, `GOROOT`, `GOPROXY` |
| Ruby/Rails | `RAILS_ENV`, `RACK_ENV` |
| Java/Spring | `SPRING_PROFILES_ACTIVE` |
| Docker | `HOSTNAME`, `HOME`, `PATH` |
