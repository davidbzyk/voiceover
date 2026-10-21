# Evidence and scope

the working tree is **not** the reviewed head. Do **not** use Read/Grep on workspace paths for any file that belongs to the reviewed tree — the changed-file list, and any other file the review points you at, such as a criteria file. They may not match the branch or PR under review, and an unchanged file is not exempt: the checkout can hold a version the reviewed head never had.

Instead:

- Do not treat local workspace contents as evidence for findings on changed files.

Recall depends on how you find related code. A diff-local read plus a text `grep` misses callers reached through re-exports, aliases, and barrel files, and mis-hits identifiers inside strings, comments, or longer names. When a claim depends on a symbol's callers, implementations, or whether a construct appears elsewhere, use the strongest search your harness actually exposes, preferring in this order and falling through when a tier is unavailable:

1. **Symbol-aware search** — a references/definitions/implementations capability (LSP or an equivalent MCP tool) that follows renames, re-exports, and barrels text search cannot. Most reviewer harnesses do not expose one; when it is absent, drop to the next tier without ceremony.
2. **Structural (AST) search** — a syntax-tree matcher such as `ast-grep` (optional; may not be installed). For "does construct X occur elsewhere" it beats regex: it matches the parsed tree, ignoring formatting and skipping the string/comment hits `grep` reports as false positives.
3. **Text search (`grep`)** — always available; correct for genuinely lexical checks (config keys, string literals, log messages), and the fallback when the tiers above are not reachable.

No tool is complete: dynamic dispatch, reflection, dependency injection, string-keyed routes/config, generated code, and external consumers hide usages from all of them. This only bites a claim that rests on *exhaustive* coverage — "this symbol is unused," "nothing else calls this," "safe to change."
