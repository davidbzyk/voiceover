# Multi-Agent Coordination -- VoiceOver

## Project Boundaries

This is a Tauri v2 desktop app with three distinct layers. Agents should respect layer boundaries:

| Layer | Path | Language | Owner concern |
|-------|------|----------|---------------|
| Frontend | `src/` | TypeScript / Svelte 5 | UI, recording, state |
| Backend | `src-tauri/src/` | Rust | IPC commands, pipeline, APIs, sidecar management |
| Sidecar | `src-tauri/sidecar/` | Python | TTS inference, model management, voice profiles |

## File Ownership Rules

When multiple agents work in parallel, avoid conflicts by assigning file ownership:

- **Frontend agent**: owns `src/` -- may read but not modify Rust or Python files
- **Backend agent**: owns `src-tauri/src/` -- may read but not modify frontend or sidecar files
- **Sidecar agent**: owns `src-tauri/sidecar/` -- may read but not modify Rust or frontend files
- **Config/build agent**: owns root config files (`package.json`, `Cargo.toml`, `tauri.conf.json`, `vite.config.ts`, etc.)

If a task spans layers (e.g., adding a new Tauri command + frontend caller), coordinate by defining the Rust command signature first, then implementing both sides.

## Shared Interfaces

These are the coordination points between layers:

1. **Tauri commands** (`lib.rs` `invoke_handler`): the contract between frontend and backend. Any new command must be registered here and have a corresponding `tauriInvoke` call on the frontend.
2. **Sidecar HTTP API** (`server.py` FastAPI routes): the contract between Rust backend and Python sidecar. Rust calls these via `reqwest`; frontend never calls them directly.
3. **App state** (`state.svelte.ts`): single source of truth for frontend state. Multiple components read from `appState`.
4. **Config schema** (`config.rs`): persisted app configuration. Changes here affect both backend reads and frontend `get_config`/`save_config` calls.

## Verification Before Completion

Before declaring any task done:

1. `pnpm test` passes (frontend)
2. `cd src-tauri && cargo test` passes (backend)
3. `pnpm check` passes (type checking)
4. No new clippy warnings: `cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings`

## Agent Communication Protocol

When handing off between agents or resuming work:

- Reference files by absolute path from project root
- State current branch and what commits are yours
- List any new Tauri commands, sidecar endpoints, or state fields added
- Note any config schema changes that require migration

## Common Multi-Agent Tasks

**Adding a new feature end-to-end:**
1. Backend agent: add Rust command in appropriate module, register in `lib.rs`
2. Sidecar agent (if TTS-related): add FastAPI endpoint in `server.py`
3. Frontend agent: add `tauriInvoke` call, update state/UI

**Adding a new sidecar endpoint:**
1. Sidecar agent: implement in `server.py`, test standalone
2. Backend agent: add Rust wrapper in `local_tts.rs` or new module, expose as Tauri command
3. Frontend agent: call via `tauriInvoke` (never direct HTTP)
