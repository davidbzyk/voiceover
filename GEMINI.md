# VoiceOver -- Gemini CLI Instructions

Read `CLAUDE.md` in this directory for full project context (architecture, build commands, conventions). This file covers Gemini-specific adaptations.

## Quick Reference

```bash
pnpm test          # Frontend tests (vitest)
pnpm test:rust     # Rust tests (cargo test)
pnpm check         # Type checking (svelte-check)
pnpm tauri dev     # Full dev environment
```

## Key Constraints

- Svelte 5 runes only (`$state()`, `$derived()`, `$effect()`). Never use Svelte 4 syntax (`$:`, `export let`, `$$props`)
- All Tauri IPC goes through `src/lib/tauri.ts` `tauriInvoke<T>()` wrapper
- Frontend never calls sidecar HTTP directly; always through Rust Tauri commands
- Secrets use OS keyring (`keyring` crate), never stored in config files
- Python sidecar targets Apple Silicon only (MLX, no CUDA)

## File Layout

- Frontend: `src/` (SvelteKit 5, TypeScript)
- Backend: `src-tauri/src/` (Rust, Tauri v2)
- Sidecar: `src-tauri/sidecar/` (Python, FastAPI)
- Tests: co-located (`*.test.ts` for frontend, `#[cfg(test)]` for Rust)

## When Modifying

- New Tauri command: implement in Rust module, register in `src-tauri/src/lib.rs` `invoke_handler`, call via `tauriInvoke` on frontend
- New sidecar endpoint: add to `src-tauri/sidecar/server.py`, wrap in Rust command, expose to frontend
- State changes: modify `src/lib/state.svelte.ts` `appState` object
- Config changes: update `src-tauri/src/config.rs` (Rust struct + persistence)

## Verification

Always run before completing: `pnpm test && pnpm test:rust && pnpm check`
