- **Turbo/Stimulus/React timing mistakes** -- state created in the wrong lifecycle hook, code that assumes a node stays mounted, or async callbacks that mutate the DOM after a swap, remount, or disconnect.
- **Concurrent interaction bugs** -- two operations that can overlap when they should be mutually exclusive, boolean flags that cannot represent the true UI state (prefer explicit state constants via `Symbol()` and a transition function over ad-hoc booleans), or repeated triggers that overwrite one another without cancelation.
- **Promise and timer flows that leave stale work behind** -- missing `finally()` cleanup, unhandled rejections, overwritten timeouts that are never canceled, or animation loops that keep running after the UI moved on.

5. **Unnecessary existence checks**: pre-checking file/resource existence before operating (TOCTOU anti-pattern) — operate directly and handle the error

**Unified severity escalation:** For ALL checks -- if finding affects payment/auth/financial code -> escalate to **CRITICAL** regardless of other factors.

### 1. Async/Event-Loop Races (CWE-362)

**What:** Shared state corrupted across await/yield boundaries in single-threaded async code.

**Layer 1 -- Grep patterns:**

| Language | Pattern | Grep |
|----------|---------|------|
| JS/TS | Read-modify-write across await | `\w+\s*[+\-*/]?=\s*.*await` (e.g., `result += await something`) |
| JS/TS | Check-then-initialize race | `if\s*\(!?\w+\)` followed by `\w+\s*=\s*await` in same block |
| Python | Read-modify-write across await | `\w+\s*[+\-*/]?=\s*await` inside `async def` |
| Python | Shared module-level state in async | Module-level `\w+\s*=` + modified inside `async def` |
| All | Shared cache without lock | `\.set\(|\.put\(|\[\w+\]\s*=` in async function without lock/mutex nearby |

**Layer 2 -- Critical questions:**
- Is the variable shared (module/global scope) or local?
- Can two async tasks interleave at this await point?
- Is there a lock/mutex/semaphore guarding the access?

**Severity:** CRITICAL (payment/auth) | HIGH (user-facing) | MEDIUM (background)

**Safe pattern exclusions:** Local variables, `const` declarations, single-use await (no interleaving possible).

**Effort:** M

### 2. Thread/Goroutine Safety (CWE-366)

**What:** Shared mutable state accessed from multiple threads/goroutines without synchronization.

**Layer 1 -- Grep patterns:**

| Language | Pattern | Grep |
|----------|---------|------|
| Go | Map access without mutex | `map\[.*\].*=` in struct without `sync.Mutex` or `sync.RWMutex` |
| Go | Variable captured by goroutine | `go func` + variable from outer scope modified |
| Python | Global modified in threads | `global\s+\w+` in function + `threading.Thread` in same file |
| Java | HashMap shared between threads | `HashMap` + `Thread\|Executor\|Runnable` in same class without `synchronized\|ConcurrentHashMap` |
| Rust | Rc in multi-thread context | `Rc<RefCell` + `thread::spawn\|tokio::spawn` in same file |
| Node.js | Worker Threads shared state | `workerData\|SharedArrayBuffer\|parentPort` + mutable access without `Atomics` |

**Layer 2 -- Critical questions:**
- Is this struct/object actually shared between threads? (single-threaded code -> FP)
- Is mutex/lock in embedded struct or imported module? (grep may miss it)
- Is `go func` capturing by value (safe) or by reference (unsafe)?

**Severity:** CRITICAL (payment/auth) | HIGH (data corruption possible) | MEDIUM (internal)

**Safe pattern exclusions:** Go map in `init()` or `main()` before goroutines start. Rust `Arc<Mutex<T>>` (already safe). Java `Collections.synchronizedMap()`.

**Effort:** M

### 3. TOCTOU -- Time-of-Check Time-of-Use (CWE-367)

**What:** Resource state checked, then used, but state can change between check and use.

**Layer 1 -- Grep patterns:**

| Language | Check | Use | Grep |
|----------|-------|-----|------|
| Python | `os.path.exists()` | `open()` | `os\.path\.exists\(` near `open\(` on same variable |
| Python | `os.access()` | `os.open()` | `os\.access\(` near `os\.open\(\|open\(` |
| Node.js | `fs.existsSync()` | `fs.readFileSync()` | `existsSync\(` near `readFileSync\(\|readFile\(` |
| Node.js | `fs.accessSync()` | `fs.openSync()` | `accessSync\(` near `openSync\(` |
| Go | `os.Stat()` | `os.Open()` | `os\.Stat\(` near `os\.Open\(\|os\.Create\(` |
| Java | `.exists()` | `new FileInputStream` | `\.exists\(\)` near `new File\|FileInputStream\|FileOutputStream` |

**Layer 2 -- Critical questions:**
- Is the check used for control flow (vulnerable) or just logging (safe)?
- Is there a lock/retry around the check-then-use sequence?
- Is the file in a temp directory controlled by the application (lower risk)?
- Could an attacker substitute the file (symlink attack)?

**Severity:** CRITICAL (security-sensitive: permissions, auth tokens, configs) | HIGH (user-facing file ops) | MEDIUM (internal/background)

**Safe pattern exclusions:** Check inside try/catch with retry. Check for logging/metrics only. Check + use wrapped in file lock.

**Effort:** S-M (replace check-then-use with direct use + error handling)

### 4. Deadlock Potential (CWE-833)

**What:** Lock acquisition in inconsistent order, or lock held during blocking operation.

**Layer 1 -- Grep patterns:**

| Language | Pattern | Grep |
|----------|---------|------|
| Python | Nested locks | `with\s+\w+_lock:` (multiline: two different locks nested) |
| Python | Lock in loop | `for.*:` with `\.acquire\(\)` inside loop body |
| Python | Lock + external call | `\.acquire\(\)` followed by `await\|requests\.\|urllib` before release |
| Go | Missing defer unlock | `\.Lock\(\)` without `defer.*\.Unlock\(\)` on next line |
| Go | Nested locks | Two `\.Lock\(\)` calls in same function without intervening `\.Unlock\(\)` |
| Java | Nested synchronized | `synchronized\s*\(` (multiline: nested blocks with different monitors) |
| JS | Async mutex nesting | `await\s+\w+\.acquire\(\)` (two different mutexes in same function) |

**Layer 2 -- Critical questions:**
- Are these the same lock (reentrant = OK) or different locks (deadlock risk)?
- Is the lock ordering consistent across all call sites?
- Does the external call inside lock have a timeout?

**Severity:** CRITICAL (payment/auth) | HIGH (app freeze risk)

**Safe pattern exclusions:** Reentrant locks (same lock acquired twice). Locks with explicit timeout (`asyncio.wait_for`, `tryLock`).

**Effort:** L (lock ordering redesign)

### 5. Blocking I/O in Async Context (CWE-400)

**What:** Synchronous blocking calls inside async functions or event loop handlers.

**Layer 1 -- Grep patterns:**

| Language | Blocking Call | Grep | Replacement |
|----------|--------------|------|-------------|
| Python | `time.sleep` in async def | `time\.sleep` inside `async def` | `await asyncio.sleep` |
| Python | `requests.*` in async def | `requests\.(get\|post\|put\|delete)` inside `async def` | `httpx` or `aiohttp` |
| Python | `open()` in async def | `open\(` inside `async def` | `aiofiles.open` |
| Node.js | `fs.readFileSync` in async | `fs\.readFileSync\|fs\.writeFileSync\|fs\.mkdirSync` | `fs.promises.*` |
| Node.js | `execSync` in async | `execSync\|spawnSync` in async handler | `exec` with promises |
| Node.js | Sync crypto in async | `crypto\.pbkdf2Sync\|crypto\.scryptSync` | `crypto.pbkdf2` (callback) |

**Layer 2 -- Critical questions:**
- Is this in a hot path (API handler) or cold path (startup script)?
- Is the blocking duration significant (>100ms)?
- Is there a legitimate reason (e.g., sync read of small config at startup)?

**Severity:** HIGH (blocks event loop/async context) | MEDIUM (minor blocking <100ms)

**Safe pattern exclusions:** Blocking call in `if __name__ == "__main__"` (startup). `readFileSync` in config loading at init time. Sync crypto for small inputs.

**Effort:** S-M (replace with async alternative)

### 6. Resource Contention (CWE-362)

**What:** Multiple concurrent accessors compete for same resource without coordination.

**Layer 1 -- Grep patterns:**

| Pattern | Risk | Grep |
|---------|------|------|
| Shared memory without sync | Data corruption | `SharedArrayBuffer\|SharedMemory\|shm_open\|mmap` without `Atomics\|Mutex\|Lock` nearby |
| IPC without coordination | Message ordering | `process\.send\|parentPort\.postMessage` in concurrent loops |
| Concurrent file append | Interleaved writes | Multiple `appendFile\|fs\.write` to same path from parallel tasks |

**Layer 2 -- Critical questions:**
- Are multiple writers actually concurrent? (Sequential = safe)
- Is there OS-level atomicity guarantee? (e.g., `O_APPEND` for small writes)
- Is ordering important for correctness?

**Severity:** HIGH (data corruption) | MEDIUM (ordering issues)

**Safe pattern exclusions:** Single writer pattern. OS-guaranteed atomic operations (small pipe writes, `O_APPEND`). Message queues with ordering guarantees.

**Effort:** M

### 7. Cross-Process & Invisible Side Effects (CWE-362, CWE-421)

**What:** Multiple processes or process+OS accessing same exclusive resource, including operations with non-obvious side effects on shared OS resources.

**Layer 1 -- Grep entry points:**

| Pattern | Risk | Grep |
|---------|------|------|
| Clipboard dual access | OSC 52 + native clipboard in same flow | `osc52\|\\x1b\\]52` AND `clipboard\|SetClipboardData\|pbcopy\|xclip` in same file |
| Subprocess + shared file | Parent and child write same file | `spawn\|exec\|Popen` + `writeFile\|open.*"w"` on same path |
| OS exclusive resource | Win32 clipboard, serial port, named pipe | `OpenClipboard\|serial\.Serial\|CreateNamedPipe\|mkfifo` |
| Terminal escape sequences | stdout triggers terminal OS access | `\\x1b\\]\|\\033\\]\|writeOsc\|xterm` |
| External clipboard tools | Clipboard via spawned process | `pbcopy\|xclip\|xsel\|clip\.exe` |

**Layer 2 -- This check relies on reasoning more than any other:**

1. **Build Resource Inventory:**

   | Resource | Exclusive? | Accessor 1 | Accessor 2 | Sync present? |
   |----------|-----------|------------|------------|---------------|

2. **Trace Timeline:**
   ```
   t=0ms  operation_A() -> resource_X accessed
   t=?ms  side_effect   -> resource_X accessed by external process
   t=?ms  operation_B() -> resource_X accessed again -> CONFLICT?
   ```

3. **Critical Questions:**
   - Can another process (terminal, OS, child) access this resource simultaneously?
   - Does this operation have invisible side effects on shared OS resources?
   - What happens if the external process is slower/faster than expected?
   - What happens if user triggers this action twice rapidly?

**Severity:** CRITICAL (two accessors to exclusive OS resource without sync) | HIGH (subprocess + shared file without lock) | HIGH (invisible side effect detected via reasoning)

**Safe pattern exclusions:** Single accessor. Retry/backoff pattern present. Operations sequenced with explicit delay/await.

**Effort:** M-L (may require removing redundant access path)

### Session Ownership Rules

| Pattern | Detection | Severity |
|---------|-----------|----------|
| DI + Local mix | `Depends(get_session)` in API AND `AsyncSessionLocal()` in service/repo | HIGH |
| Service local session | `AsyncSessionLocal()` in service calling DI-based repo | MEDIUM |

### Async Consistency Rules

| Blocking Pattern | Detection in `async def` | Safe Alternative |
|------------------|-------------------------|------------------|
| File read | `\\.read_bytes\\(\\)\|\\.read_text\\(\\)` | `asyncio.to_thread()` |
| File write | `\\.write_bytes\\(\\)\|\\.write_text\\(\\)` | `asyncio.to_thread()` |
| open() | `(?<!aiofiles\\.)open\\(` | `aiofiles.open()` |
| time.sleep | `time\\.sleep\\(` | `asyncio.sleep()` |
| requests | `requests\\.(get\|post)` | `httpx.AsyncClient` |

### Fire-and-Forget Rules

| Pattern | Detection | Severity |
|---------|-----------|----------|
| Task without handler | `create_task\\(` without `.add_done_callback(` | MEDIUM |
| Task in loop | `for.*create_task\\(` without error collection | HIGH |

**Safe Patterns:**
- `# fire-and-forget` comment documenting intent
- Task assigned to variable with later `await`
- Explicit `.add_done_callback(handle_exception)`
