Think in terms of the deploy window: old code on new schema, new code on old data, partial failures leaving inconsistent state. Never trust fixtures — production data shapes differ.

Cross-reference every change in each in-scope dump against migrations **in this PR's diff**:

- Schema version (or structure version stamp) should match the PR's newest migration timestamp
- Every new column/table/index in the dump must come from a PR migration
- **Drift:** columns, tables, indexes, or version bumps not explained by PR migrations

- **Swapped or inverted ID/enum mappings** — `1 => TypeA, 2 => TypeB` in code but production has the reverse. Verify each CASE/IF branch and constant hash entry individually.
- **Irreversible migrations without rollback plan** — column drops, precision-losing type changes, data deletes. Destructive `down` missing or non-restorative needs explicit acknowledgment.
- **Missing backfill for new non-nullable columns** — `NOT NULL` without default or backfill fails on existing rows.
- **Deploy-window breaks** — rename/drop before all code paths stop reading; constraints that existing rows violate. The fix vocabulary is the expand/contract (parallel change) pattern: additive expand, migrate readers and writers, contract only after nothing reads the old shape.
- **Orphaned references** — after drop/rename, search serializers, jobs, admin, rake tasks, `includes`/`joins` for stale columns or associations.
- **Broken dual-write** — transition period requires both old and new columns populated; rollback otherwise sees NULLs.
- **Missing transaction boundaries** — multi-table backfills without appropriate transaction scope.
- **Hot-table index changes** — large-table indexes without concurrent/online creation where available.
- **Silent data loss** — `text` → `varchar(n)` truncation, float → integer precision loss.

For non-trivial data transforms, check whether the PR includes (or clearly defers with a ticket):

- Read-only SQL to prove correctness post-deploy (mapping counts, NULL checks, dual-write verification)
- Rollback or feature-flag guardrails for risky paths

### Transaction Boundary Rules

| Owner Layer | commit() Allowed In | commit() Forbidden In |
|-------------|---------------------|----------------------|
| Service-owned UoW | services/ | repositories/, api/ |
| Endpoint-owned UoW | api/ | repositories/, services/ |
| Repository-owned UoW | repositories/ | services/, api/ |

**Detection:**
```
repo_commits = Grep("\.commit\(\)|\.rollback\(\)", "**/repositories/**")
service_commits = Grep("\.commit\(\)|\.rollback\(\)", "**/services/**")
api_commits = Grep("\.commit\(\)|\.rollback\(\)", "**/api/**")
```

**Safe Patterns (not violations):**
- `# best-effort telemetry` comment in context
- `_callbacks.py` files (progress notifiers)
- `# UoW boundary` explicit marker

**Violation Rules:**

| Condition | Severity | Issue |
|-----------|----------|-------|
| layers_with_commits >= 3 | CRITICAL | Mixed UoW ownership across all layers |
| repo + api commits | HIGH | Transaction control bypasses service layer |
| repo + service commits | HIGH | Ambiguous UoW owner (repo vs service) |
| service + api commits | MEDIUM | Transaction control spans service + API |

**Exception:** Saga pattern / distributed transactions with explicit compensating actions -> downgrade CRITICAL to MEDIUM. UoW boundary documented with `// architecture decision` or ADR -> skip.

**Recommendation:** Choose single UoW owner (service layer recommended), remove commit() from other layers

### 1. Missing Intermediate Commits
**What:** UPDATE without commit when DB trigger/NOTIFY depends on transaction commit

**Detection:**
- **Step 1:** Find triggers in migrations:
  - Grep for `pg_notify|NOTIFY|CREATE TRIGGER|CREATE OR REPLACE FUNCTION.*trigger` in `alembic/versions/`, `migrations/`
  - Extract: trigger function name, table name, trigger event (INSERT/UPDATE)
- **Step 2:** Find code that UPDATEs trigger-affected tables:
  - Grep for `repo.*update|session\.execute.*update|\.progress|\.status` related to trigger tables
- **Step 3:** Check for `commit()` between sequential updates:
  - If multiple UPDATEs to trigger table occur in a loop/sequence without intermediate `commit()`, NOTIFY events are deferred until final commit
  - Real-time progress tracking breaks without intermediate commits

**Severity:**
- **CRITICAL:** Missing commit for NOTIFY/LISTEN-based real-time features (SSE, WebSocket)
- **HIGH:** Missing commit for triggers that update materialized data

**Exception:** Single atomic operation with no intermediate observable state -> downgrade CRITICAL to MEDIUM. Transaction scope documented as intentional (ADR, architecture comment) -> downgrade one level

**Recommendation:**
- Add `session.commit()` at progress milestones (throttled: every N%, every T seconds)
- Or move real-time notifications out of DB triggers (Redis pub/sub, in-process events)

**Effort:** S-M (add strategic commits or redesign notification path)

### 2. Transaction Scope Too Wide
**What:** Single transaction wraps unrelated operations, including slow external calls

**Detection:**
- Find `async with session.begin()` or explicit transaction blocks
- Check if block contains external calls: `await httpx.`, `await aiohttp.`, `await requests.`, `await grpc.`
- Check if block contains file I/O: `open(`, `.read(`, `.write(`
- Pattern: DB write + external API call + another DB write in same transaction

**Severity:**
- **HIGH:** External HTTP/gRPC call inside transaction (holds DB connection during network latency)
- **MEDIUM:** File I/O inside transaction

**Recommendation:** Split into separate transactions; use Saga/Outbox pattern for cross-service consistency

**Effort:** M-L (restructure transaction boundaries)

### 3. Transaction Scope Too Narrow
**What:** Logically atomic operations split across multiple commits

**Detection:**
- Multiple `session.commit()` calls for operations that should be atomic
- Pattern: create parent entity, commit, create child entities, commit (should be single transaction)
- Pattern: update status + create audit log in separate commits

**Severity:**
- **HIGH:** Parent-child creation in separate commits (orphan risk on failure)
- **MEDIUM:** Related updates in separate commits (inconsistent state on failure)

**Recommendation:** Wrap related operations in single transaction using `async with session.begin()` or unit-of-work pattern

**Effort:** M (restructure commit boundaries)

### 4. Missing Rollback Handling
**What:** `session.commit()` without proper error handling and rollback

**Detection:**
- Find `session.commit()` not inside `try/except` block or context manager
- Find `session.commit()` in `try` without `session.rollback()` in `except`
- Pattern: bare `await session.commit()` in service methods
- Exception: `async with session.begin()` auto-rollbacks (safe)

**Severity:**
- **MEDIUM:** Missing rollback (session left in broken state on failure)
- **LOW:** Missing explicit rollback when using context manager (auto-handled)

**Recommendation:** Use `async with session.begin()` (auto-rollback), or add explicit `try/except/rollback` pattern

**Effort:** S (wrap in context manager or add error handling)

### 5. Long-Held Transaction
**What:** Transaction open during slow/blocking operations

**Detection:**
- Measure scope: count lines between transaction start and commit
- Flag if >50 lines of code between `begin()` and `commit()`
- Flag if transaction contains `await` calls to external services (network latency)
- Flag if transaction contains `time.sleep()` or `asyncio.sleep()`

**Severity:**
- **HIGH:** Transaction held during external API call (connection pool exhaustion risk)
- **MEDIUM:** Transaction spans >50 lines (complex logic, high chance of lock contention)

**Recommendation:** Minimize transaction scope; prepare data before opening transaction, commit immediately after DB operations

**Effort:** M (restructure code to minimize transaction window)

### 6. Event Channel Name Consistency
**What:** Publisher channel/topic name does not match subscriber channel/topic name

**Detection:**
- **Step 1:** Collect publisher channel names (extend Phase 2 trigger discovery):
  - Migration triggers: extract string argument from `pg_notify('channel_name', ...)`, `NOTIFY channel_name`
  - Application code: Grep for `\.publish\(["']|\.emit\(["']|redis.*publish\(["']|\.send_to\(["']` in `src/`, `app/`
  - Extract: `{channel_name, source_file, source_line, technology}`
- **Step 2:** Collect subscriber channel names:
  - PostgreSQL: Grep for `LISTEN\s+(\w+)` in application code (not just migrations)
  - Redis: Grep for `\.subscribe\(["']([^"']+)` in `src/`, `app/`
  - EventEmitter/WebSocket: Grep for `\.on\(["']([^"']+)` in handler/listener directories
  - Extract: `{channel_name, source_file, source_line, technology}`
- **Step 3:** Cross-reference publishers vs subscribers:
  - Exact match: `publisher.channel_name == subscriber.channel_name` -> OK
  - Near-miss: Levenshtein distance <= 2 OR one is substring of the other -> flag as MISMATCH
  - Orphaned publisher: channel exists in publishers but not in subscribers -> flag as ORPHAN
  - Orphaned subscriber: channel exists in subscribers but not in publishers -> flag as ORPHAN

**Layer 2 Context Analysis (MANDATORY):**
- If channel name comes from shared config constant or env var (e.g., `CHANNEL = os.environ["EVENT_CHANNEL"]`) and both publisher and subscriber use same source -> NOT a mismatch
- If channel uses dynamic suffix pattern (e.g., `job_events:{job_id}`) and both sides use same template -> NOT orphaned
- Exclude test files (`**/test*/**`, `**/*.test.*`) from both publisher and subscriber discovery

**Severity:**
- **CRITICAL:** Channel name mismatch (near-miss: publisher sends to `job_events`, subscriber listens on `job_event`)
- **HIGH:** Orphaned publisher -- events sent but never consumed (data loss risk if events carry state changes)
- **MEDIUM:** Orphaned subscriber -- listener registered but no publisher found (dead code or future feature)

**Recommendation:**
- For mismatches: unify channel name to a single constant shared between publisher and subscriber
- For orphaned publishers: add subscriber or remove unused NOTIFY/publish
- For orphaned subscribers: add publisher or remove dead listener

**Effort:** S (fix typo/add constant) to M (design missing subscriber/publisher)

1. **Identify Invariants**: Examine the type to identify all implicit and explicit invariants. Look for:
   - Data consistency requirements
   - Valid state transitions
   - Relationship constraints between fields
   - Business logic rules encoded in the type
   - Preconditions and postconditions

5. **Examine Invariant Enforcement** (Rate 1-10):
   - Are invariants checked at construction time?
   - Are all mutation points guarded?
   - Is it impossible to create invalid instances?
   - Are runtime checks appropriate and comprehensive?

   - If related updates can leave state half-applied, push for a more atomic structure.
