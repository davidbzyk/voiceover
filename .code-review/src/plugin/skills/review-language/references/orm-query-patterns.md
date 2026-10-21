# ORM query, session and transaction patterns
### 1. Redundant Entity Fetch
**What:** Same entity fetched from DB twice in a call chain

**Detection:**
- Find function A that calls `repo.get(id)` or `session.get(Model, id)`, then passes `id` (not object) to function B
- Function B also calls `repo.get(id)` or `session.get(Model, id)` for the same entity
- Common pattern: `acquire_next_pending()` returns job, but `_process_job(job_id)` re-fetches it

**Detection patterns (Python/SQLAlchemy):**
- Grep for `repo.*get_by_id|session\.get\(|session\.query.*filter.*id` in service/handler files
- Trace: if function receives `entity_id: int/UUID` AND internally does `repo.get(entity_id)`, check if caller already has entity object
- Check `expire_on_commit` setting: if `False`, objects remain valid after commit

**Severity:**
- **HIGH:** Redundant fetch in API request handler (adds latency per request)
- **MEDIUM:** Redundant fetch in background job (less critical)
- **Downgrade when:** Fetch in initialization/migration code (runs once) -> LOW. Admin-only endpoint with low traffic -> downgrade one level

**Recommendation:** Pass entity object instead of ID, or remove second fetch when `expire_on_commit=False`

**Effort:** S (change signature to accept object instead of ID)

### 2. N-UPDATE/DELETE Loop
**What:** Loop of individual UPDATE/DELETE operations instead of single batch query

**Detection:**
- Pattern: `for item in items: await repo.update(item.id, ...)` or `for item in items: await repo.delete(item.id)`
- Pattern: `for item in items: session.execute(update(Model).where(...))`

**Detection patterns:**
- Grep for `for .* in .*:` followed by `repo\.(update|delete|reset|save|mark_)` within 1-3 lines
- Grep for `for .* in .*:` followed by `session\.execute\(.*update\(` within 1-3 lines

**Severity:**
- **HIGH:** Loop over >10 items (N separate round-trips to DB)
- **MEDIUM:** Loop over <=10 items
- **Downgrade when:** Loop in bootstrap/migration code (runs once) -> LOW. Admin-only endpoint -> downgrade one level

**Recommendation:** Replace with single `UPDATE ... WHERE id IN (...)` or `session.execute(update(Model).where(Model.id.in_(ids)))`

**Effort:** M (rewrite query + test)

### 3. Unnecessary Resolve
**What:** Re-resolving a value from DB when it is already available in the caller's scope

**Detection:**
- Method receives `profile_id` and resolves engine from it, but caller already determined `engine`
- Method receives `lang_code` and looks up dialect_id, but caller already has both `lang` and `dialect`
- Pattern: function receives `X_id`, does `get(X_id)`, extracts `.field`, when caller already has `field`

**Severity:**
- **MEDIUM:** Extra DB query per invocation, especially in high-frequency paths

**Recommendation:** Split method into two variants: `with_known_value(value, ...)` and `resolving_value(id, ...)`; or pass resolved value directly

**Effort:** S-M (refactor signature, update callers)

### 4. Over-Fetching
**What:** Loading full ORM model when only few fields are needed

**Detection:**
- `session.query(Model)` or `select(Model)` without `.options(load_only(...))` for models with >10 columns
- Especially in list/search endpoints that return many rows
- Pattern: loading full entity but only using 2-3 fields

**Severity:**
- **MEDIUM:** Large models (>15 columns) in list endpoints
- **LOW:** Small models (<10 columns) or single-entity endpoints

**Recommendation:** Use `load_only()`, `defer()`, or raw `select(Model.col1, Model.col2)` for list queries

**Effort:** S (add load_only to query)

### 5. Missing Bulk Operations
**What:** Sequential INSERT/DELETE/UPDATE instead of bulk operations

**Detection:**
- `for item in items: session.add(item)` instead of `session.add_all(items)`
- `for item in items: session.delete(item)` instead of bulk delete
- Pattern: loop with single `INSERT` per iteration

**Severity:**
- **MEDIUM:** Any sequential add/delete in loop (missed batch optimization)

**Recommendation:** Use `session.add_all()`, `session.execute(insert(Model).values(list_of_dicts))`, `bulk_save_objects()`

**Effort:** S (replace loop with bulk call)

### 6. Wrong Caching Scope
**What:** Request-scoped cache for data that rarely changes (should be app-scoped)

**Detection:**
- Service registered as request-scoped (e.g., via FastAPI `Depends()`) with internal cache (`_cache` dict, `_loaded` flag)
- Cache populated by expensive query (JOINs, aggregations) per each request
- Data TTL >> request duration (e.g., engine configurations, language lists, feature flags)

**Detection patterns:**
- Find classes with `_cache`, `_loaded`, `_initialized` attributes
- Check if class is created per-request (via DI registration scope)
- Compare: data change frequency vs cache lifetime

**Severity:**
- **HIGH:** Expensive query (JOINs, subqueries) cached only per-request
- **MEDIUM:** Simple query cached per-request

**Recommendation:** Move cache to app-scoped service (singleton), add TTL-based invalidation, or use CacheService with configurable TTL

**Effort:** M (change DI scope, add TTL logic)
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
