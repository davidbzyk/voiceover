# Dependency and supply-chain security

## Dependency Discipline

Part of code review is dependency review:

**Before adding any dependency:**
1. Does the existing stack solve this? (Often it does.)
2. How large is the dependency? (Check bundle impact.)
3. Is it actively maintained? (Check last commit, open issues.)
4. Does it have known vulnerabilities? (`npm audit`)
5. What's the license? (Must be compatible with the project.)

**Rule:** Prefer standard library and existing utilities over new dependencies. Every dependency is a liability.

**Upgrading an existing dependency** is a code change like any other, and the riskiest upgrades are the ones merged in bulk with a message like "bump deps." Review them with the same discipline:

1. **Read the changelog, not just the version number.** Semver is a promise the maintainer may not have kept — a "patch" can carry a behavioral change. For a major bump, read the migration notes and find what breaks.
2. **One dependency per change.** Upgrade and merge them individually (or in small related groups). When a bulk bump breaks the build, you've lost which package did it; a single-package change makes the cause obvious and the revert clean.
3. **Let the tests decide.** The upgrade is verified by a green suite before *and* after, not by "it installed." If coverage around the dependency's behavior is thin, that gap is the real finding — add a test first.
4. **Mind the transitive graph.** Most installed packages are ones nobody chose directly. Review the lockfile diff, not just `package.json`; a single direct bump can pull in dozens of indirect changes.
5. **Keep the lockfile honest.** Commit it, review its diff, and never hand-edit it. The lockfile is the thing that actually pins what ships.


- A bulk "bump dependencies" PR with no changelog review and no per-package isolation
- A lockfile change that's hand-edited, uncommitted, or merged without reviewing its diff

## Dependency Security

First locate the **installation boundary**. If the package is matched by a parent `workspaces` declaration, use that workspace root; otherwise use the nearest project root that owns both its manifest and dependency graph. At that boundary, corroborate `packageManager` (when present), the lockfile, and CI commands. Stop if they disagree or competing manager lockfiles exist there. A nested project is independent only when it is outside the parent workspace; independent subprojects may legitimately use different managers.

| Manager/version signal | Frozen/immutable CI install | Known-advisory audit |
|---|---|---|
| npm (`package-lock.json` or `npm-shrinkwrap.json`) | `npm ci` | `npm audit` |
| pnpm | `pnpm install --frozen-lockfile` | `pnpm audit` |
| Yarn 2+ | `yarn install --immutable` | `yarn npm audit -A -R` |
| Yarn 1 | `yarn install --frozen-lockfile` | `yarn audit` |

For an unlisted manager or version, consult its official documentation; do not substitute another manager's commands or newer defaults.

### Install-Script Gate

Never discover dependency lifecycle scripts by first executing an ordinary install on a client whose defaults have not been verified.

1. Bootstrap with dependency scripts disabled, or with a documented default-deny policy plus fail-closed enforcement.
2. Inspect the exact script source and package version before approval.
3. Record the narrowest native allow/deny policy at the installation boundary and commit it.
4. Run a clean frozen/immutable install with that policy and verify the required packages still build.

**Point-in-time snapshot:** Package-manager defaults and command names change quickly. Verify this matrix against the pinned client's current official documentation before relying on it.

| Manager version | Native policy |
|---|---|
| npm without verified granular approvals | Bootstrap with `npm ci --ignore-scripts`, or persist `ignore-scripts=true` when project-wide blocking is intended. Keep scripts disabled or deliberately upgrade before allowing any reviewed dependency script. |
| npm 11.18.x (verified on 11.18.0) | Unreviewed dependency scripts run with a warning by default. Enforce `strict-allow-scripts=true` before a normal install, then use the workspace-unaware `npm install-scripts ls` from the installation boundary; keep approvals version-pinned and denials name-wide. |
| npm 12.x (verified on 12.0.1) | Unreviewed dependency scripts are skipped by default; `strict-allow-scripts=true` makes their presence fail the install before execution. Use the same `npm install-scripts` review and approval flow. |
| pnpm 11+ | Use `pnpm approve-builds` and commit `allowBuilds` decisions; `strictDepBuilds` defaults to `true`, so unreviewed builds fail. |
| pnpm 10.26–10.x | Configure `allowBuilds` explicitly, or use `pnpm approve-builds` with the legacy `onlyBuiltDependencies` / `ignoredBuiltDependencies` lists. Set `strictDepBuilds: true`; its v10 default is `false`. |
| pnpm 10.1–10.25 | `pnpm approve-builds` records the legacy lists; enable `strictDepBuilds` where supported (10.3+). |
| Older or unknown pnpm | Bootstrap with `pnpm install --frozen-lockfile --ignore-scripts`. Keep scripts disabled unless the pinned version documents an enforceable policy. |
| Yarn 4.14+ | Dependency postinstalls are disabled by default. Grant only required exceptions with top-level `dependenciesMeta.<package>.built: true`. |
| Yarn 2–4.13 | Set `enableScripts: false` in `.yarnrc.yml`, then grant only required exceptions with top-level `dependenciesMeta.<package>.built: true`; do not enable scripts globally. |
| Yarn 1 | Bootstrap with `yarn install --ignore-scripts`; keep scripts disabled unless each required exception is reviewed under the pinned client's documented workflow. |

Authoritative checks: [npm install-scripts](https://docs.npmjs.com/cli/v11/commands/npm-install-scripts/), [install policy](https://docs.npmjs.com/cli/v11/commands/npm-install/), and [CLI releases](https://github.com/npm/cli/releases); [pnpm approve-builds](https://pnpm.io/cli/approve-builds) and [build settings](https://pnpm.io/settings#allowbuilds); [Yarn security](https://yarnpkg.com/features/security) and [manifest](https://yarnpkg.com/configuration/manifest#dependenciesMeta).

**Supply-chain hygiene** (advisory audits do not catch newly malicious packages):
- [ ] Exactly one authoritative lockfile per project/workspace root is committed and CI never rewrites it
- [ ] Critical/high findings are triaged for reachability; deferrals have a reason and review date
- [ ] Forced audit remediation (`npm audit fix --force` or equivalent) is never automatic; remediation diffs and changelogs are reviewed
- [ ] Registry signatures/provenance are verified where the manager supports it
- [ ] Dependency lifecycle scripts are blocked before first execution and approved only through the pinned manager's native policy
- [ ] New dependencies are reviewed for ownership, maintenance, release age, provenance, transitive graph, and typosquatting

## 4. Insecure Dependencies

### Audit Commands by Stack

| Stack | Command | Output Format |
|-------|---------|---------------|
| Node.js | `npm audit --json` | JSON with vulnerabilities |
| Python | `pip-audit --format json` | JSON with CVEs |
| Rust | `cargo audit --json` | JSON with advisories |
| .NET | `dotnet list package --vulnerable` | Table format |
| Go | `go list -json -m all \| nancy sleuth` | JSON with CVEs |

### Severity Mapping

| CVE CVSS Score | Severity |
|----------------|----------|
| 9.0-10.0 | CRITICAL |
| 7.0-8.9 | HIGH |
| 4.0-6.9 | MEDIUM |
| 0.1-3.9 | LOW |

### Recommendations

| Scenario | Action |
|----------|--------|
| Patch available | Update to patched version immediately |
| No patch, workaround exists | Apply workaround, add comment with CVE ID |
| No patch, actively exploited | Replace package with alternative |
| Unmaintained package | Find maintained alternative |
| Dev dependency only | Lower priority, update when possible |

## Node.js / npm

| Command | Purpose | Output |
|---------|---------|--------|
| `npm audit` | Check for vulnerabilities | Human-readable |
| `npm audit --json` | Machine-readable output | JSON |
| `npm audit --audit-level=high` | Fail only on high+ severity | Exit code |
| `npm audit fix` | Auto-fix safe updates | Modified package-lock |
| `npm audit fix --dry-run` | Preview fixes | No changes |

**Tool Alternatives:**
- `npx audit-ci` - CI-friendly wrapper
- `snyk test` - Commercial scanner (free tier available)

---

## .NET / NuGet

| Command | Purpose | Output |
|---------|---------|--------|
| `dotnet list package --vulnerable` | Check vulnerable packages | Human-readable |
| `dotnet list package --vulnerable --include-transitive` | Include transitive deps | Detailed |

**Tool Alternatives:**
- `dotnet-outdated` - Global tool for updates
- NuGet Package Explorer - GUI for package analysis

---

## Python / pip

| Tool | Command | Purpose |
|------|---------|---------|
| **pip-audit** | `pip-audit` | OSV database check |
| **pip-audit** | `pip-audit --fix` | Auto-fix vulnerabilities |
| **pip-audit** | `pip-audit --format=json` | JSON output |
| **safety** | `safety check` | PyUp.io database check |
| **safety** | `safety check --full-report` | Detailed output |

**Note:** pip-audit is preferred (OSV database is more comprehensive).

---

## Go

| Command | Purpose | Output |
|---------|---------|--------|
| `govulncheck ./...` | Check for vulnerabilities | Human-readable |
| `govulncheck -json ./...` | JSON output | JSON |

---

## Ruby / Bundler

| Command | Purpose | Output |
|---------|---------|--------|
| `bundle audit check` | Check for vulnerabilities | Human-readable |
| `bundle audit update` | Update advisory database | Database update |

---

## Rust / Cargo

| Command | Purpose | Output |
|---------|---------|--------|
| `cargo audit` | Check for vulnerabilities | Human-readable |
| `cargo audit --json` | Machine-readable output | JSON |

---

## PHP / Composer

| Command | Purpose | Output |
|---------|---------|--------|
| `composer audit` | Check for vulnerabilities | Human-readable |
| `composer audit --format=json` | JSON output | JSON |

---

## Handling False Positives

### npm

Use `.nsprc` or `audit-ci` config to ignore specific advisories:
- Document reason for each ignore
- Review ignores quarterly
- Remove when fix available

### .NET

Use `<NoWarn>` in csproj for specific packages:
- Only for packages without fix
- Add comment with CVE ID

### Python

Use `.safety-policy.yml` or `pip-audit` ignore file:
- Specify exact package@version
- Add expiration date for review

   - Vulnerability: read code -- is the vulnerable API actually called in this project?

**Severity:**
- **HIGH:** Custom crypto (security risk)
- **MEDIUM:** Custom utilities with well-tested alternatives

### 5. Vulnerability Scan (CVE/CVSS)
**Mode:** full AND vulnerabilities_only

**Detection:**
- Detect ecosystems: npm, NuGet, pip, Go, Bundler, Cargo, Composer
- Run the audit commands given in this file
- Parse results with the CVSS mapping given in this file

**Severity:**
- **CRITICAL:** CVSS 9.0-10.0 (immediate fix required)
- **HIGH:** CVSS 7.0-8.9 (fix within 48h)
- **MEDIUM:** CVSS 4.0-6.9 (fix within 1 week)
- **LOW:** CVSS 0.1-3.9 (fix when convenient)

**Fix Classification:**
- Patch update (x.x.Y) -> safe auto-fix
- Minor update (x.Y.0) -> usually safe
- Major update (Y.0.0) -> manual review required
- No fix available -> document and monitor

**Recommendation:** Update to fixed version, verify lock file integrity

**Effort:** S-L (depends on breaking changes)

CVSS score to severity level mapping for dependency vulnerabilities.

---

## CVSS v3 Score Mapping

| CVSS Score | Severity | Action Required |
|------------|----------|-----------------|
| 9.0 - 10.0 | **Critical** | Immediate fix required, blocks CI |
| 7.0 - 8.9 | **High** | Fix within 48 hours |
| 4.0 - 6.9 | **Medium** | Fix within 1 week |
| 0.1 - 3.9 | **Low** | Fix when convenient |
| 0.0 | **None** | Informational only |

## Ecosystem-Specific Mappings

### npm audit

| npm Severity | CVSS Equivalent | Our Severity |
|--------------|-----------------|--------------|
| critical | 9.0+ | Critical |
| high | 7.0-8.9 | High |
| moderate | 4.0-6.9 | Medium |
| low | 0.1-3.9 | Low |

### NuGet

NuGet uses CVSS directly - apply standard mapping.

### pip-audit / safety

| OSV Severity | Our Severity |
|--------------|--------------|
| CRITICAL | Critical |
| HIGH | High |
| MODERATE / MEDIUM | Medium |
| LOW | Low |

## Triaging npm audit Results

Not all audit findings require immediate action. Use this decision tree:

```
npm audit reports a vulnerability
├── Severity: critical or high
│   ├── Is the vulnerable code reachable in your app?
│   │   ├── YES --> Fix immediately (update, patch, or replace the dependency)
│   │   └── NO (dev-only dep, unused code path) --> Fix soon, but not a blocker
│   └── Is a fix available?
│       ├── YES --> Update to the patched version
│       └── NO --> Check for workarounds, consider replacing the dependency, or add to allowlist with a review date
├── Severity: moderate
│   ├── Reachable in production? --> Fix in the next release cycle
│   └── Dev-only? --> Fix when convenient, track in backlog
└── Severity: low
    └── Track and fix during regular dependency updates
```

**Key questions:**
- Is the vulnerable function actually called in your code path?
- Is the dependency a runtime dependency or dev-only?
- Is the vulnerability exploitable given your deployment context (e.g., a server-side vulnerability in a client-only app)?

When you defer a fix, document the reason and set a review date.

### Supply-Chain Hygiene

`npm audit` catches known CVEs; it won't catch a malicious or typosquatted package. Also:

- **Commit the lockfile** and install with `npm ci` (not `npm install`) in CI — reproducible builds, no silent version drift.
- **Review new dependencies before adding them** — maintenance, download counts, and whether they truly earn their place. Every dependency is attack surface (OWASP **A06: Vulnerable Components**, **LLM03: Supply Chain**).
- **Be wary of `postinstall` scripts** in unfamiliar packages — they run arbitrary code at install time.
- **Watch for typosquats** — `cross-env` vs `crossenv`, `react-dom` vs `reactdom`.
