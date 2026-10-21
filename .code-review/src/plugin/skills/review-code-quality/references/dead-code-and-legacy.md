## Audit Rules
### 1. Unreachable Code
**Detection:**
- Linter rules: `no-unreachable` (ESLint)
- Check code after `return`, `throw`, `break`

**Severity:** MEDIUM

### 2. Unused Imports/Variables/Functions
**Detection:**
- ESLint: `no-unused-vars`
- TypeScript: `noUnusedLocals`, `noUnusedParameters`
- Python: `flake8` with `F401`, `F841`

**Severity:**
- **MEDIUM:** Unused functions (dead weight)
- **LOW:** Unused imports (cleanup needed)

### 3. Commented-Out Code
**Detection:**
- Grep for `//.*{` or `/*.*function` patterns
- Large comment blocks (>10 lines) with code syntax

**Severity:** LOW

**Recommendation:** Delete (git preserves history)

### 4. Legacy Code & Backward Compatibility
**What:** Backward compatibility shims, deprecated patterns, old code that should be removed

**Detection:**
- Renamed variables/functions with old aliases:
  - Pattern: `const oldName = newName` or `export { newModule as oldModule }`
  - Pattern: `function oldFunc() { return newFunc(); }` (wrapper for backward compatibility)
- Deprecated exports/re-exports:
  - Grep for `// DEPRECATED`, `@deprecated` JSDoc tags
  - Pattern: `export.*as.*old.*` or `export.*legacy.*`
- Conditional code for old versions:
  - Pattern: `if.*legacy.*` or `if.*old.*version.*` or `isOldVersion ? oldFunc() : newFunc()`
- Migration shims and adapters:
  - Pattern: `migrate.*`, `Legacy.*Adapter`, `.*Shim`, `.*Compat`
- Comment markers:
  - Grep for `// backward compatibility`, `// legacy support`, `// TODO: remove in v`
  - Grep for `// old implementation`, `// deprecated`, `// kept for backward`

**Severity:**
- **HIGH:** Backward compatibility shims in critical paths (auth, payment, core features)
- **MEDIUM:** Deprecated exports still in use, migration code from >6 months ago
- **LOW:** Recent migration code (<3 months), planned deprecation with clear removal timeline

**Recommendation:**
- Remove backward compatibility shims - breaking changes are acceptable when properly versioned
- Delete old implementations - keep only the correct/new version
- Remove deprecated exports - update consumers to use new API
- Delete migration code after grace period (3-6 months)
- Clean legacy support comments - git history preserves old implementations

**Effort:**
- **S:** Remove simple aliases, delete deprecated exports
- **M:** Refactor code using old APIs to new APIs
- **L:** Remove complex backward compatibility layer affecting multiple modules
## Critical Rules
- **Do not auto-fix:** Report only, never delete code
- **Age-aware severity:** Legacy shims >6 months = MEDIUM, <3 months = LOW
- **Effort realism:** S = <1h, M = 1-4h, L = >4h
- **Exclusions:** Skip generated code, vendor, migrations, test fixtures
- **Git-aware:** Recommend deletion confidently -- git history preserves old code
