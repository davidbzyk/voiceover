- Defensive programming and error-handling discipline (guard clauses, input validation,
  explicit error paths, assertions for invariants)

- Whether missing error handling makes failure modes invisible to maintainers

Michael Nygard's *Release It!* stability vocabulary applies here: name the antipattern (cascading failure, retry storm, integration point without a timeout) or the stabilizing fix (circuit breaker, bulkhead, fail fast) in the finding when one matches — the name calibrates the finding, but the missing protection you can point to, not the name, decides whether to flag it.

Every gap below is a finding only when the failure it allows costs something where this code runs: a crashed or wedged service, a caller or user acting on a wrong or missing result, or work left half-done in a way that running it again does not repair. Read how the code runs from the diff, the PR description, and nearby docs, not from an assumed production service.

- **Missing error handling on I/O boundaries** -- HTTP calls, database queries, file operations, or message queue interactions without try/catch or error callbacks.

- **Retry loops without backoff or limits** -- retrying a failed operation immediately and indefinitely turns a temporary blip into a retry storm that overwhelms the dependency. Check for max attempts, exponential backoff, and jitter.
- **Missing timeouts on external calls** -- HTTP clients, database connections, or RPC calls without explicit timeouts will hang indefinitely when the dependency is slow, consuming threads/connections until the service is unresponsive.

- **Error swallowing (catch-and-ignore)** -- `catch (e) {}`, `.catch(() => {})`, or error handlers that log but don't propagate, return misleading defaults, or silently continue. The caller thinks the operation succeeded; the data says otherwise.

- **Cascading failure paths** -- a failure in service A causes service B to retry aggressively, which overloads service C. Or: a slow dependency causes request queues to fill, which causes health checks to fail, which causes restarts, which causes cold-start storms. Trace the failure propagation path.

### 4. Missing Error Handling

- Find async functions without try-catch
- Check API routes without error middleware
- Verify database calls have error handling

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Payment/auth without error handling |
| **HIGH** | User-facing operations without error handling |
| **MEDIUM** | Internal operations without error handling |

## Rule 4: Inconsistent Error Contracts

Mixed error patterns within same service.

### Detection

| Step | Tool | Pattern |
|------|------|---------|
| 1. Find raises | Grep | `raise \|throw \|throw new` in service methods |
| 2. Find return None | Grep | `return None\|return null\|return undefined` in same service |
| 3. Find Result type | Grep | `Result\|Either\|Optional\|Maybe` in return types |
| 4. Compare | Logic | If 2+ patterns in same service class → violation |

### Language-Specific Patterns

| Language | Pattern A (Exception) | Pattern B (Null return) | Pattern C (Result type) |
|----------|-----------------------|-------------------------|-------------------------|
| Python | `raise.*Error\|raise.*Exception` | `return None` | `Result\|Either\|Optional` |
| TypeScript | `throw new.*Error` | `return null\|return undefined` | `Result<\|Either<\|Option<` |
| C# | `throw new.*Exception` | `return null` | `Result<\|OneOf<\|ErrorOr<` |
| Java | `throw new.*Exception` | `return null\|return Optional.empty` | `Either<\|Result<\|Try<` |

1. **Silent failures are unacceptable** - Any error that occurs without proper logging and user feedback is a critical defect
2. **Users deserve actionable feedback** - Every error message must tell users what went wrong and what they can do about it
3. **Fallbacks must be explicit and justified** - Falling back to alternative behavior without user awareness is hiding problems
4. **Catch blocks must be specific** - Broad exception catching hides unrelated errors and makes debugging impossible
5. **Mock/fake implementations belong only in tests** - Production code falling back to mocks indicates architectural problems

### 1. Identify All Error Handling Code

Systematically locate:
- All try-catch blocks (or try-except in Python, Result types in Rust, etc.)
- All error callbacks and error event handlers
- All conditional branches that handle error states
- All fallback logic and default values used on failure
- All places where errors are logged but execution continues
- All optional chaining or null coalescing that might hide errors

### 2. Scrutinize Each Error Handler

For every error handling location, ask:

**Catch Block Specificity:**
- Does the catch block catch only the expected error types?
- Could this catch block accidentally suppress unrelated errors?
- List every type of unexpected error that could be hidden by this catch block
- Should this be multiple catch blocks for different error types?

**Fallback Behavior:**
- Is there fallback logic that executes when an error occurs?
- Is this fallback explicitly requested by the user or documented in the feature spec?
- Does the fallback behavior mask the underlying problem?
- Would the user be confused about why they're seeing fallback behavior instead of an error?
- Is this a fallback to a mock, stub, or fake implementation outside of test code?

**Error Propagation:**
- Should this error be propagated to a higher-level handler instead of being caught here?
- Is the error being swallowed when it should bubble up?
- Does catching here prevent proper cleanup or resource management?

### 4. Check for Hidden Failures

Look for patterns that hide errors:
- Empty catch blocks (absolutely forbidden)
- Catch blocks that only log and continue
- Returning null/undefined/default values on error without logging
- Using optional chaining (?.) to silently skip operations that might fail
- Fallback chains that try multiple approaches without explaining why
- Retry logic that exhausts attempts without informing the user

  - FAIL-OPEN STATE DRIFT: when a security decision reads parsed/cached/tracked/callback state, verify error, cancellation, TOCTOU, cache-skew, and unhandled-variant paths do not yield a default that skips enforcement — broad-except→pass, unwrap_or({}), missing-finally cleanup, ignored verifier params, or stale validator maps all fail open. The finding is the path where the fallback value is the allow outcome. Also: when + lines compare against a security threshold, check whether the EXACT boundary value yields the permissive branch; when an error path triggers retry/redelivery, check whether the retry can emit a decision that overrides a stricter first decision; when sync logic reads persisted state, check whether state surviving a data wipe causes destructive sync.

**Anchor 100** — the gap is mechanical: a `requests.get(url)` with no `timeout=` keyword, an infinite loop with no break, a catch block with `pass` and no log.

**Anchor 75** — the reliability gap is directly visible: an HTTP call with no timeout set, a retry loop with no max attempts, a catch block that swallows the error. You can point to the specific line missing the protection.

**Anchor 50** — the code lacks explicit protection but might be handled by framework defaults or middleware you can't see — e.g., the HTTP client *might* have a default timeout configured elsewhere.

**Anchor 25 or below — suppress** — the reliability concern is architectural and can't be confirmed from the diff alone.
