# Comment rules

Quality standards for code comments and docstrings.

## Core Principle: WHY not WHAT

Comments should explain **intent and rationale**, not restate code behavior.

### Good Comments (WHY)

```
// Retry 3 times because external API has occasional timeouts
// Using binary search here for O(log n) instead of O(n) linear scan
// Cache expires after 5 min to balance freshness vs performance
// Skip validation for admin users per security policy SEC-2024
```

### Bad Comments (WHAT)

```
// Increment counter     ← Obvious from code
// Loop through array    ← Restates code
// Return the result     ← Unnecessary
// Set x to 5           ← Just reading code
```

### When to Comment

| Comment | Don't Comment |
|---------|---------------|
| Non-obvious algorithm choice | Simple assignments |
| Business rule rationale | Standard patterns |
| Performance optimization reason | Loop iterations |
| Security constraint explanation | Variable declarations |
| Workaround with context | Obvious conditionals |

---

## Density Guidelines

### Target: 15-20% Comment Ratio

| Ratio | Assessment | Action |
|-------|------------|--------|
| <10% | Under-commented | Add context for complex logic |
| 10-15% | Slightly low | Add WHY comments for non-obvious code |
| **15-20%** | **Optimal** | Maintain quality |
| 20-25% | Slightly high | Review for obvious comments |
| >25% | Over-commented | Remove WHAT comments |

### Calculation

```
Comment Ratio = (comment lines / total lines) × 100
```

Exclude:
- Blank lines
- Import statements
- Boilerplate (license headers)

---

## Forbidden Content

### Never Include in Comments

| Forbidden | Reason | Where It Belongs |
|-----------|--------|------------------|
| Dates ("Updated 2024-01-15") | Git tracks this | Git blame |
| Author names | Git tracks this | Git log |
| Historical notes ("was X, now Y") | Clutters code | CHANGELOG |
| Code examples | Belongs in tests/docs | Documentation |

> **Note:** Task/Epic/Story IDs, ADR references — allowed as **spec/requirement links** (`See API-409`, `Per ADR-003`, `RFC 9457`). Forbidden as **development history** (`EP4_07 added filtering`, `Created in Sprint 5`).

### Detection Patterns

```regex
# Dates in comments
(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])

# Historical language
(was|were|used to|previously|before|changed from|migrated from)

# Author references
(Author:|Written by:|Created by:|@author)
```

---

## Comment Compression

**Principle:** Comments should be as concise as possible while preserving meaning.

### Length Limits

| Comment Type | Max Length | Example |
|--------------|------------|---------|
| Inline comment | 1 line (~80 chars) | `// Retry 3x for flaky API` |
| Block comment | 3 lines | Short explanation of complex logic |
| Docstring (function) | 5 lines | Purpose, params, return |
| Docstring (class/module) | 10 lines | Purpose, usage, key methods |

### Compression Techniques

| Verbose | Concise |
|---------|---------|
| `// This function is used to calculate the total` | `// Calculate total` |
| `// We need to do this because...` | `// Because: [reason]` |
| `// The following code will iterate through...` | (remove, obvious from code) |
| `// TODO: In the future we should consider...` | `// TODO: [specific action]` |

### Structured Docstrings

When documenting >3 parameters, use structured format:

```
Good (structured):
/**
 * @param {string} name - User name
 * @param {number} age - User age
 * @param {boolean} active - Is active
 */

Bad (prose):
/**
 * This function takes a name which is the user's name,
 * an age which represents how old the user is, and
 * a boolean active flag that indicates whether...
 */
```

---

## Docstrings Quality

### Must Match

- Function/method name
- All parameters (name, type, description)
- Return type and description
- Raised exceptions

### Red Flags

| Issue | Problem |
|-------|---------|
| Missing parameter | Docstring incomplete |
| Wrong parameter name | Copy-paste error |
| Missing return type | Unclear contract |
| Outdated description | Code changed, doc didn't |
| Generic description | "Does the thing" - unhelpful |

### Validation Checklist

- [ ] All public functions have docstrings
- [ ] Parameter names match function signature
- [ ] Types accurate (if language supports)
- [ ] Return value described
- [ ] Exceptions listed (if any)
- [ ] Examples are runnable

---

## Actuality Checks

### Comment vs Code Mismatch

When comment says one thing and code does another:

1. **Code is truth** - always
2. Flag comment as stale
3. Suggest: "Update comment to match code behavior"

### Stale Indicators

- References removed variables
- Describes different algorithm than implemented
- Mentions features that don't exist
- Links to deleted files/functions

---

## Legacy Cleanup

### Must Remove

| Pattern | Example | Why Remove |
|---------|---------|------------|
| TODO without context | `// TODO: fix this` | No actionable info |
| Old TODO with dates | `// TODO (2023-01): cleanup` | Clearly abandoned |
| Commented-out code | `// oldFunction()` | Git has history |
| Deprecated notes | `// DEPRECATED: use newFunc` | Should be deleted, not noted |
| "Temporary" markers | `// TEMP: workaround` | Often permanent |

### Keep Only If

- TODO has specific action + owner
- Comment explains current behavior
- Note is genuinely temporary (<7 days old)

1. **Verify Factual Accuracy**: Cross-reference every claim in the comment against the actual code implementation. Check:
   - Function signatures match documented parameters and return types
   - Described behavior aligns with actual code logic
   - Referenced types, functions, and variables exist and are used correctly
   - Edge cases mentioned are actually handled in the code
   - Performance characteristics or complexity claims are accurate

2. **Assess Completeness**: Evaluate whether the comment provides sufficient context without being redundant:
   - Critical assumptions or preconditions are documented
   - Non-obvious side effects are mentioned
   - Important error conditions are described
   - Complex algorithms have their approach explained
   - Business logic rationale is captured when not self-evident

3. **Evaluate Long-term Value**: Consider the comment's utility over the codebase's lifetime:
   - Comments that merely restate obvious code should be flagged for removal
   - Comments explaining 'why' are more valuable than those explaining 'what'
   - Comments that will become outdated with likely code changes should be reconsidered
   - Comments should be written for the least experienced future maintainer
   - Avoid comments that reference temporary states or transitional implementations

4. **Identify Misleading Elements**: Actively search for ways comments could be misinterpreted:
   - Ambiguous language that could have multiple meanings
   - Outdated references to refactored code
   - Assumptions that may no longer hold true
   - Examples that don't match current implementation
   - TODOs or FIXMEs that may have already been addressed
