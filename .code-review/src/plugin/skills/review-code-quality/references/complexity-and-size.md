## Audit Rules (Priority: MEDIUM)

### 1. Cyclomatic Complexity
**What:** Too many decision points in single function (> 10)

**Detection:**
- Count if/else, switch/case, ternary, &&, ||, for, while
- Use tools: `eslint-plugin-complexity`, `radon` (Python), `gocyclo` (Go)

**Severity:**
- **HIGH:** Complexity > 20 (extremely hard to test)
- **MEDIUM:** Complexity 11-20 (refactor recommended)
- **LOW:** Complexity 8-10 (acceptable but monitor)
- **Downgrade when:** Enum/switch dispatch, state machines, parser grammars -> downgrade to LOW or skip

**Recommendation:** Split function, extract helper methods, use early returns

**Effort:** M-L (depends on complexity)

### 2. Deep Nesting (> 4 levels)
**What:** Nested if/for/while blocks too deep

**Detection:**
- Count indentation levels
- Pattern: if { if { if { if { if { ... } } } } }

**Severity:**
- **HIGH:** > 6 levels (unreadable)
- **MEDIUM:** 5-6 levels
- **LOW:** 4 levels
- **Downgrade when:** Nesting from early-return guard clauses (structurally deep but linear logic) -> downgrade

**Recommendation:** Extract functions, use guard clauses, invert conditions

**Effort:** M (refactor structure)

### 3. Long Methods (> 50 lines)
**What:** Functions too long, doing too much

**Detection:**
- Count lines between function start and end
- Exclude comments, blank lines

**Severity:**
- **HIGH:** > 100 lines
- **MEDIUM:** 51-100 lines
- **LOW:** 40-50 lines (borderline)
- **Downgrade when:** Orchestrator functions with sequential delegation; data transformation pipelines -> downgrade

**Recommendation:** Split into smaller functions, apply Single Responsibility

**Effort:** M (extract logic)

### 4. God Classes/Modules (> 500 lines)
**What:** Files with too many responsibilities

**Detection:**
- Count lines in file (exclude comments)
- Check number of public methods/functions

**Severity:**
- **HIGH:** > 1000 lines
- **MEDIUM:** 501-1000 lines
- **LOW:** 400-500 lines
- **Downgrade when:** Config/schema/migration files, generated code, barrel/index files -> skip

**Recommendation:** Split into multiple files, apply separation of concerns

**Effort:** L (major refactor)

### 5. Too Many Parameters (> 5)
**What:** Functions with excessive parameters

**Detection:**
- Count function parameters
- Check constructors, methods

**Severity:**
- **MEDIUM:** 6-8 parameters
- **LOW:** 5 parameters (borderline)
- **Downgrade when:** Builder/options pattern constructor; framework-required signatures (middleware, hooks) -> skip

**Recommendation:** Use parameter object, builder pattern, default parameters

**Effort:** S-M (refactor signature + calls)

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

### 8. Constants Management (NEW)
**What:** Magic numbers/strings, decentralized constants, duplicates

**Detection:**

| Issue | Pattern | Example |
|-------|---------|---------|
| Magic numbers | Hardcoded numbers in conditions/calculations | `if (status === 2)` |
| Magic strings | Hardcoded strings in comparisons | `if (role === 'admin')` |
| Decentralized | Constants scattered across files | `MAX_SIZE = 100` in 5 files |
| Duplicates | Same value multiple times | `STATUS_ACTIVE = 1` in 3 places |
| No central file | Missing `constants.ts` or `config.py` | No single source of truth |

**Severity:**
- **HIGH:** Magic numbers in business logic (payment amounts, statuses)
- **MEDIUM:** Duplicate constants (same value defined 3+ times)
- **MEDIUM:** No central constants file
- **LOW:** Magic strings in logging/debugging
- **Downgrade when:** HTTP status codes (200, 404, 500) -> skip. Math constants (0, 1, -1) in algorithms -> skip. Test data -> skip

**Recommendation:**
- Create central constants file (`constants.ts`, `config.py`, `constants.go`)
- Extract magic numbers to named constants: `const STATUS_ACTIVE = 1`
- Consolidate duplicates, import from central file
- Use enums for related constants

**Effort:** M (extract constants, update imports, consolidate)

### 9. Method Signature Quality
**What:** Poor method contracts reducing readability and maintainability

**Detection:**

| Issue | Pattern | Example |
|-------|---------|---------|
| Boolean flag params | >=2 boolean params in signature | `def process(data, is_async: bool, skip_validation: bool)` |
| Too many optional params | >=3 optional params with defaults | `def query(db, limit=10, offset=0, sort="id", order="asc")` |
| Inconsistent verb naming | Different verbs for same operation type in one module | `get_user()` vs `fetch_account()` vs `load_profile()` |
| Unclear return type | `-> dict`, `-> Any`, `-> tuple` without TypedDict/NamedTuple | `def get_stats() -> dict` instead of `-> StatsResponse` |

**Severity:**
- **MEDIUM:** Boolean flag params (use enum/strategy), unclear return types
- **LOW:** Too many optional params, inconsistent naming

**Recommendation:**
- Boolean flags: replace with enum, strategy pattern, or separate methods
- Optional params: group into config/options dataclass
- Naming: standardize verb conventions per module (`get_` for sync, `fetch_` for async, etc.)
- Return types: use TypedDict, NamedTuple, or dataclass instead of raw dict/tuple

**Effort:** S-M (refactor signatures + callers)

# Two-Layer Detection Methodology

Unified methodology for L3 audit workers. Replaces pure grep-based scanning with grep + agent reasoning.

## Why Two Layers

Grep (Layer 1) finds candidates fast but produces false positives. Agent reasoning (Layer 2) reads context, builds models, and filters FP — catching issues grep cannot detect alone (cross-process races, scope-dependent violations, architecture-level gaps).

## Layer 1: Pattern Scan

Fast, automated scan using Grep/Glob/Bash tools.

| Action | Tool | Purpose |
|--------|------|---------|
| Find code patterns | Grep | Match known anti-patterns, violation signatures |
| Find files by structure | Glob | Locate config files, entry points, test files |
| Run analysis tools | Bash | Execute linters, audit commands, type checkers |

**Output:** List of candidate locations (file:line) with matched pattern.

## Layer 2: Context Analysis

Agent reads surrounding code and applies domain reasoning to each candidate.

### Standard Steps

1. **Read Context** — Read 20-50 lines around candidate. Understand scope (function, module, process), data flow, synchronization present nearby.

2. **Build Model** (when applicable):
   - Resource model: Who accesses what? Is resource exclusive? Is sync present?
   - Data flow model: Where does input come from? Where does output go?
   - Dependency model: What depends on this? What does this depend on?

3. **Critical Questions** (domain-specific, defined per check):
   - Does the context change the severity or validity of this finding?
   - Is there a safe pattern nearby that mitigates the issue?
   - What's the blast radius if this is a real issue?

4. **Classify:**
   - **Confirmed** — Real issue with assigned severity
   - **False Positive** — Candidate not a real issue (document reason)
   - **Needs Context** — Cannot determine without more info (report as LOW with note)

### When Layer 2 Is Mandatory

| Situation | Layer 2 | Rationale |
|-----------|---------|-----------|
| Grep pattern has high FP rate (>30%) | **Mandatory** | Without context analysis, report is noise |
| Finding depends on scope/architecture | **Mandatory** | Grep cannot determine scope, lifecycle, or architecture |
| Finding involves cross-process/OS interaction | **Mandatory** | Domain knowledge required |
| Tool provides structured output with confidence | Optional | Tool already analyzed context (e.g., `npm audit` with CVSS) |
| Pattern is unambiguous (e.g., `time.sleep` in `async def`) | Optional | Low FP, context rarely changes verdict |

### Example: Clipboard Race Condition

**Layer 1 found:** `writeOsc52()` + `setClipboardText()` in same file.

**Layer 2 analysis:**
1. Read context: both called in sequence within same function
2. Build resource model: Win32 clipboard is exclusive (one `OpenClipboard()` at a time). `writeOsc52` → stdout → terminal calls `OpenClipboard()`. `setClipboardText` → FFI calls `OpenClipboard()`. Two accessors, one exclusive resource.
3. Trace timeline: ~1ms window where both compete for clipboard lock
4. Critical question: "Can terminal process the escape sequence before our native call?" → Yes, timing-dependent
5. Verdict: **CRITICAL** — two processes race for exclusive OS resource

**Without Layer 2:** Grep finds two clipboard-related calls but cannot understand that OSC 52 causes the terminal to access clipboard — this is domain knowledge about terminal emulators.
