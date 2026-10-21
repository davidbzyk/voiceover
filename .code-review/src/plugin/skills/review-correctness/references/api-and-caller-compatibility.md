Don't change what the code does — only how it expresses it. All inputs, outputs, side effects, error behavior, and edge cases must remain identical. If you're not sure a simplification preserves behavior, don't make it.

```
ASK BEFORE EVERY CHANGE:
→ Does this produce the same output for every input?
→ Does this maintain the same error behavior?
→ Does this preserve the same side effects and ordering?
→ Do all existing tests still pass without modification?
```

- Removing error handling because "it makes the code cleaner"

- **Hyrum's Law**: with sufficient callers, every observable behavior — including
  implementation details, error message text, coincidental call ordering, and undocumented
  side effects — becomes an implicit contract that callers depend on, even though it was
  never guaranteed by the declared API

- A subclass overrides most parent methods with incompatible behavior or throws exceptions
  where the parent contract guarantees success (LSP violation: substitution breaks callers)

- Backward compatibility: whether API changes preserve existing callers or force
  coordinated upgrades across the organization

- **Breaking changes to public interfaces** -- renamed fields, removed endpoints, changed response shapes, narrowed accepted input types, or altered status codes that existing clients depend on. Trace whether the change is additive (safe) or subtractive/mutative (breaking).
- **Missing versioning on breaking changes** (SemVer: on a stable API -- 1.0.0 or later -- a breaking change is a major bump; a 0.y.z package follows the project's declared versioning policy) -- a breaking change shipped without a version bump, deprecation period, or migration path. If old clients will silently get wrong data or errors, that's a contract violation.
- **Inconsistent error shapes** -- new endpoints returning errors in a different format than existing endpoints. Mixed `{ error: string }` and `{ errors: [{ message }] }` in the same API. Clients shouldn't need per-endpoint error parsing.
- **Undocumented behavior changes** (Hyrum's Law: every observable behavior of an interface will be depended on by somebody, documented or not) -- response field that silently changes semantics (e.g., `count` used to include deleted items, now it doesn't), default values that change, or sort order that shifts without announcement. Use the law's name in the title when the change alters observable-but-undocumented behavior; the observed semantic change, not the name, decides whether to flag it.
- **Sentinel contract overloads** -- new `null`, `undefined`, empty collection/object, or fallback enum returns that reuse an existing value for a new state. Audit visible consumers for semantic handling, not just compile/type acceptance; if clients cannot distinguish "no data" from "data exists but cannot be summarized", the contract needs a richer shape or explicit discriminator.
- **Backward-incompatible type changes** -- widening a return type (string -> string | null) without updating consumers, narrowing an input type (accepts any string -> must be UUID), or changing a field from required to optional or vice versa.

## Rule 6: Architectural Honesty

Read-named function contains write side-effects (architecturally dishonest interface).

### Detection



| Step | Tool | Pattern |
|------|------|---------|
| 1. Find read-named functions | Grep | `(def\|function\|async)\s+(get_\|find_\|check_\|validate_\|is_\|has_)` in service files |
| 2. Check body for write markers | Grep | Side-effect markers per reference (DB writes, HTTP calls, notifications, events) |
| 3. Apply exclusions | Logic | Skip get_or_create, @cache decorators, CQRS handlers, check_and_* (per reference) |

### Severity

| Condition | Severity |
|-----------|----------|
| Read-named function in auth/payment service with write side-effects | HIGH |
| Read-named function in other services with write side-effects | MEDIUM |

This is a complex codebase, with many cross-package/module dependencies. Often simple code changes in one place have subtle interactions that break functionality elsewhere. You MUST be extremely thorough in tracing through possible side effects of the changes.
