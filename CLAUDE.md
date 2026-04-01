# VoiceOver

Desktop screen recorder that replaces your voice with a character voice using ElevenLabs (cloud) or local TTS (Qwen via managed sidecar). Tauri v2 app: Rust backend, SvelteKit 5 + TypeScript frontend, Python FastAPI sidecar for local TTS.

## Build & Run

```bash
# Frontend dev server (port 5170)
pnpm dev

# Full Tauri dev (frontend + Rust backend + sidecar auto-start)
pnpm tauri dev

# Production build
pnpm build && pnpm tauri build
```

## Test Commands

```bash
# Frontend tests (vitest, jsdom)
pnpm test                    # single run
pnpm test:watch              # watch mode
pnpm test:coverage           # with v8 coverage

# Rust tests
pnpm test:rust               # cargo test
pnpm test:rust:coverage      # cargo llvm-cov (HTML report)

# All tests
pnpm test:all

# Type checking
pnpm check                   # svelte-check + tsc
```

## Lint & Quality

```bash
# Rust clippy (pre-push hook runs this)
cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings

# Lefthook runs pre-commit: pnpm test, cargo test, pnpm check
# Lefthook runs pre-push: clippy, pnpm audit, cargo audit
```

## Architecture

```
src/                          # SvelteKit 5 frontend (TypeScript)
  lib/
    state.svelte.ts           # Global app state (Svelte 5 runes)
    recorder.svelte.ts        # Screen/audio capture logic
    voicebox.ts               # Frontend client for TTS sidecar (via Tauri IPC)
    logger.ts                 # Structured logging ([VO:*] prefix)
    drive.ts                  # Google Drive upload client
    blobStore.ts              # In-memory blob storage
    tauri.ts                  # Thin tauriInvoke wrapper
    RegionSelector.svelte     # Region capture overlay
    WebcamBubble.svelte       # Webcam PiP bubble
  routes/
    +page.svelte              # Main recording screen
    settings/                 # Settings page
    create-voice/             # Voice profile creation flow
    preview/                  # Recording preview & processing
    widget/                   # Floating recording widget (always-on-top)

src-tauri/                    # Rust backend (Tauri v2)
  src/
    lib.rs                    # App setup, plugin registration, command handlers
    config.rs                 # App config persistence
    pipeline.rs               # Recording processing pipeline
    elevenlabs.rs             # ElevenLabs cloud API
    local_tts.rs              # Local TTS sidecar communication
    sidecar.rs                # Sidecar process lifecycle management
    tts_provider.rs           # Provider abstraction (cloud vs local)
    models.rs                 # Model download management
    ffmpeg.rs                 # FFmpeg operations
    google_drive.rs           # Google Drive OAuth2 + upload
    secrets.rs                # Keyring-based secret storage
    prerequisites.rs          # System dependency checks (ffmpeg)
    commands/
      recording.rs            # Recording chunk save/finalize
      window.rs               # Widget window management

src-tauri/sidecar/            # Python TTS sidecar (FastAPI)
  server.py                   # Main FastAPI server (transcription, TTS, profiles, models)
  tts.py                      # Qwen TTS synthesis
  profiles.py                 # Voice profile management
  chunked_tts.py              # Chunked generation for long text
  requirements.txt            # Python dependencies (mlx, qwen-tts, torch, etc.)
  voiceover-tts.spec          # PyInstaller spec for building sidecar binary
```

## Key Patterns & Conventions

- **Svelte 5 runes mode** is enforced globally via `svelte.config.js` (`runes: true`)
- **State management**: single `appState` object in `state.svelte.ts` using `$state()` runes
- **Tauri IPC**: all backend calls go through `tauriInvoke<T>()` wrapper in `tauri.ts`
- **Sidecar communication**: frontend never calls sidecar directly; always routes through Rust commands (`sidecar_fetch`, `sidecar_upload`)
- **Logging**: use `logger.ts` with `[VO:tag]` prefix pattern on frontend; `log::info!` etc. on Rust side
- **Test files**: co-located with source as `*.test.ts` or `*.svelte.test.ts`; Rust tests use `#[cfg(test)] mod tests` in the same file
- **Coverage thresholds**: 50% statements/branches/lines, 55% functions (frontend)
- **External binaries**: ffmpeg and voiceover-tts bundled in `src-tauri/binaries/` (gitignored, created at build time)
- **Secrets**: API keys stored via OS keyring (`keyring` crate), never in config files
- **Config stripping**: `vite.config.ts` removes `_config.json` from production builds
- **CSP**: defined in `tauri.conf.json` -- update when adding new external domains
- **Sidecar auto-start**: the TTS sidecar launches automatically on app startup; `sidecar::ensure_running()` guarantees it is up before any local TTS operation

## Sidecar Development

```bash
# Set up Python venv for sidecar development
python3 -m venv .sidecar-venv
source .sidecar-venv/bin/activate
pip install -r src-tauri/sidecar/requirements.txt

# Run sidecar standalone for testing
python src-tauri/sidecar/server.py --port 8123 --data-dir /tmp/voiceover-tts

# Build sidecar binary (PyInstaller, arm64 macOS)
cd src-tauri/sidecar && pyinstaller voiceover-tts.spec
```

## CI

GitHub Actions (`.github/workflows/ci.yml`): frontend job (ubuntu, pnpm check + test + audit) and rust job (macos, clippy + test + audit). Sidecar placeholder is created for Tauri build script in CI.

## Do Not

- Commit API keys, tokens, or `static/_config.json`
- Call sidecar HTTP endpoints directly from frontend code
- Use Svelte 4 syntax (`$:`, `export let`) -- this codebase uses Svelte 5 runes exclusively
- Add CUDA/NVIDIA deps to sidecar (Apple Silicon only via MLX)
