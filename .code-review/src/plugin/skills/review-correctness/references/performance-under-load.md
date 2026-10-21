- **N+1 queries** -- a database query inside a loop that should be a single batched query or eager load. Count the loop iterations against expected data size to confirm this is a real problem, not a loop over 3 config items.
- **Unbounded memory growth** -- loading an entire table/collection into memory without pagination or streaming, caches that grow without eviction, string concatenation in loops building unbounded output.
- **Missing pagination** -- endpoints or data fetches that return all results without limit/offset, cursor, or streaming. Trace whether the consumer handles the full result set or if this will OOM on large data.
- **Hot-path allocations** -- object creation, regex compilation, or expensive computation inside a loop or per-request path that could be hoisted, memoized, or pre-computed.
- **Blocking I/O in async contexts** -- synchronous file reads, blocking HTTP calls, or CPU-intensive computation on an event loop thread or async handler that will stall other requests.

### 6. O(n^2) or Worse Algorithms
**What:** Inefficient nested loops over collections

**Detection:**
- Nested for loops: `for (i) { for (j) { ... } }`
- Nested array methods: `arr.map(x => arr.filter(...))`

**Severity:**
- **HIGH:** O(n^2) in hot path (API request handler)
- **MEDIUM:** O(n^2) in occasional operations
- **LOW:** O(n^2) on small datasets (n < 100)
- **Downgrade when:** Bounded n (n < 100 guaranteed by domain); one-time init/migration code -> downgrade to LOW or skip

**Recommendation:** Use hash maps, optimize with single pass, use better data structures

**Effort:** M (algorithm redesign)

### 7. N+1 Query Patterns
**What:** ORM lazy loading causing N+1 queries

**Detection:**
- Find loops with database queries inside
- Check ORM patterns: `users.forEach(u => u.getPosts())`

**Severity:**
- **CRITICAL:** N+1 in API endpoint (performance disaster)
- **HIGH:** N+1 in frequent operations
- **MEDIUM:** N+1 in admin panel
- **Downgrade when:** Admin-only endpoint called <=1x/day -> downgrade to LOW. Eager loading configured elsewhere in ORM -> skip

**Recommendation:** Use eager loading, batch queries, JOIN

**Effort:** M (change ORM query)

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

### 3. Sync Sleep in Async
**What:** `time.sleep()` inside async function blocks event loop

**Detection:**
- Grep for `time\.sleep` inside `async def` blocks
- Pattern: `await some_async_call()` ... `time.sleep(N)` ... `await another_call()`

**Severity:**
- **HIGH:** `time.sleep()` in async API handler (freezes all concurrent requests)
- **MEDIUM:** `time.sleep()` in async background task
- **Downgrade when:** `time.sleep` in CLI/script (not async server) -> skip

**Recommendation:** Replace with `await asyncio.sleep(N)`

**Effort:** S (one-line change)

### 4. String Concatenation in Loop
**What:** Building string via `+=` inside loop (O(n^2) for large strings)

**Detection:**
- Pattern: variable `result`, `output`, `html`, `text` with `+=` inside `for`/`while` loop
- Grep for: variable followed by `+=` containing string operand inside loop body

**Severity:**
- **MEDIUM:** String concat in loop processing large data (>100 iterations)
- **LOW:** String concat in loop with small iterations (<100)

**Recommendation:** Use `list.append()` + `"".join()`, or `io.StringIO`, or f-string with `"".join(generator)`

**Effort:** S (refactor to list + join)

### 5. Missing `to_thread` for CPU-Bound
**What:** CPU-intensive synchronous code in async handler without offloading to thread

**Detection:**
- Inside `async def`, find CPU-intensive operations:
  - JSON parsing large files: `json.loads(large_data)`, `json.load(file)`
  - Image processing: `PIL.Image.open`, `cv2.imread`
  - Crypto: `hashlib`, `bcrypt.hashpw`
  - XML/HTML parsing: `lxml.etree.parse`, `BeautifulSoup(`
  - Large data transformation without await points
- Exclude: operations already wrapped in `asyncio.to_thread()` or executor

**Severity:**
- **MEDIUM:** CPU-bound operation in async handler (blocks event loop proportionally to data size)

**Recommendation:** Wrap in `await asyncio.to_thread(func, *args)` (Python 3.9+) or `loop.run_in_executor(None, func, *args)`

**Effort:** S (wrap in to_thread)

    1. **Database performance**: N+1 queries, missing indexes, unoptimized queries, connection pool sizing
    2. **Memory management**: Memory leaks, unbounded collections, large object allocation
    3. **Caching opportunities**: Missing caching, stale cache risks, cache invalidation issues
    4. **I/O bottlenecks**: Synchronous blocking calls, missing pagination, large payloads
    5. **Concurrency issues**: Race conditions, deadlocks, thread safety
    6. **Frontend performance**: Bundle size, render performance, unnecessary re-renders, missing lazy loading
    7. **Scalability concerns**: Horizontal scaling barriers, stateful components, single points of failure

### Database

- [ ] No N+1 query patterns
- [ ] Queries use appropriate indexes
- [ ] No SELECT \* on large tables
- [ ] Pagination is implemented for list endpoints
- [ ] Connection pooling is configured

### Memory & Resources

- [ ] No memory leaks (event listeners cleaned up, streams closed)
- [ ] Large data sets are streamed, not loaded entirely into memory
- [ ] File handles and connections are properly closed
- [ ] Caching is used for expensive operations

### Computation

- [ ] No unnecessary re-computation or redundant operations
- [ ] Appropriate algorithm complexity for the data size
- [ ] Async operations used where I/O bound
- [ ] No blocking operations on the main thread

- [ ] No N+1 query patterns (use eager loading / joins)
- [ ] Queries have appropriate indexes
- [ ] List endpoints paginated (never `SELECT * FROM table`)
- [ ] Connection pooling configured

- [ ] No synchronous heavy computation in request handlers
- [ ] Bulk operations instead of loops of individual calls
