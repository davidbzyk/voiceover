# Runtime performance hazards per language
### 1. Blocking IO in Async
**What:** Synchronous file/network operations inside async functions, blocking event loop

**Detection (Python):**
- Find `async def` functions
- Inside them, grep for blocking calls:
  - File: `open(`, `.read_bytes()`, `.read_text()`, `.write_bytes()`, `.write_text()`, `Path(...).(read|write)`
  - Network: `requests.get`, `requests.post`, `urllib.request`
  - Subprocess: `subprocess.run(`, `subprocess.call(`
- Exclude: calls wrapped in `await asyncio.to_thread(...)` or `await loop.run_in_executor(...)`

**Detection (Node.js):**
- Inside `async function` or arrow async, grep for `fs.readFileSync`, `fs.writeFileSync`, `child_process.execSync`

**Severity:**
- **HIGH:** Blocking IO in API request handler (blocks entire event loop)
- **MEDIUM:** Blocking IO in background task/worker
- **Downgrade when:** Blocking IO in `__init__`/setup/bootstrap (not request path) -> LOW. Small file (<1KB) read in non-hot path -> skip

**Recommendation:** Use `aiofiles`, `asyncio.to_thread()`, or `loop.run_in_executor()` for file operations; use `httpx.AsyncClient` instead of `requests`

**Effort:** S (wrap in to_thread or switch to async library)

### 2. Unnecessary List Allocation
**What:** List comprehension where generator expression suffices

**Detection:**
- `len([x for x in ...])` - allocates list just to count; use `sum(1 for ...)`
- `any([x for x in ...])` - allocates list for short-circuit check; use `any(x for ...)`
- `all([x for x in ...])` - same pattern; use `all(x for ...)`
- `set([x for x in ...])` - use set comprehension `{x for x in ...}`
- `"".join([x for x in ...])` - use generator directly `"".join(x for x in ...)`

**Severity:**
- **MEDIUM:** Unnecessary allocation in hot path (API handler, loop)
- **LOW:** Unnecessary allocation in infrequent code

**Recommendation:** Replace `[...]` with generator `(...)` or set comprehension `{...}`

**Effort:** S (syntax change only)

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

### 6. Redundant Data Copies
**What:** Unnecessary `.copy()`, `list()`, `dict()` when data is only read, not mutated

**Detection:**
- `data = list(items)` where `data` is only iterated (never modified)
- `config = config_dict.copy()` where `config` is only read
- `result = dict(original)` where `result` is returned without modification

**Severity:**
- **LOW:** Redundant copy in most contexts (minor memory overhead)
- **MEDIUM:** Redundant copy of large data in hot path

**Recommendation:** Remove unnecessary copy; pass original if not mutated

**Effort:** S (remove copy call)
