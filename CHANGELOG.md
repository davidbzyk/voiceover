# Changelog

## [0.1.0] - 2026-04-02

**86 files | 12,367 lines | 18 PRs | 99 commits**

### 🌟 New Features

- Record your screen with voice-over narration, then transform your voice using AI — locally or via ElevenLabs cloud (#1–#18)
- **Local TTS engine** — bundled CosyVoice3 Python sidecar, no external server needed. Whisper-powered transcription on Apple Silicon MLX (#13, #15)
- **Voice conversion mode** — speech-to-speech cloning that preserves your exact timing and prosody (#16)
- **Timestamp-synced TTS** — generates speech per-segment at Whisper word timestamps, preserving original pacing with proportional silence insertion (#16)
- **Voice creation wizard** — extract voices from YouTube URLs or upload audio samples, auto-transcribe reference text (#13, #15)
- **Capture modes** — fullscreen, window, or drag-to-select region with live preview and canvas cropping (#12)
- **Webcam overlay** — circular PiP bubble composited into video output, toggleable position (#11)
- **Sidebar navigation** — Record, Library, Settings views with active state highlighting (#18)
- **Video library** — browse past recordings with lazy-loaded thumbnails, sort, play, delete, upload to Google Drive (#18)
- **Settings tabs** — Voice, Recording, Cloud with persistence on blur (#18)
- **Transcript export** — `.txt` file alongside output video with word-level timing (#16)
- **Provider toggle** — switch between ElevenLabs and Local TTS on the main recording page (#13)

### 🔐 Security Hardening

- Credentials stored in macOS Keychain instead of plaintext JSON (#11)
- `torch.load` → `weights_only=True` to prevent arbitrary code execution (#16)
- Path traversal validation on all file commands and sidecar endpoints (#1, #16)
- CSP policy: self + ElevenLabs + Google + blob only (#1)
- `sidecar_fetch` URL allowlist, `generation_id` format validation (#16)
- MD5 → SHA-256 for cache keys (#16)
- OAuth state parameter for CSRF protection (#11)
- API key logging truncated to last 4 chars (#11)

### 🐛 Critical Bug Fixes

- CSP blocking audio playback in production builds (#16)
- Status string mismatch `"error"` vs `"failed"` causing silent pipeline failures (#16)
- Video duration (not audio) used for TTS assembly — prevents truncation from WebRTC clock skew (#16)
- Natural TTS speed with silence padding instead of time-stretching that distorted speech (#16)
- 7× `.unwrap()` on non-UTF8 paths replaced with safe handling (#16)
- `CosyVoice2→3` naming mismatch across sidecar (#16)
- Odd-pixel screen dimensions crashing libx264 — `pad` filter added (#8)
- Voice selection not persisting to disk during processing (#6)
- Config loading fallback chain: Tauri app data → static seed → defaults (#4, #5)
- `getDisplayMedia` guard for environments without Screen Capture API (#3)
- Tauri v2.10 compilation errors resolved (#2)
- Dangling promise in `cleanup()` permanently disabling record button (#12)

### 🛠️ Architecture & Infrastructure

- **Three-layer stack**: SvelteKit frontend → Rust/Tauri backend → Python FastAPI sidecar
- Shared `HttpClient` in Tauri state with per-request `tokio::time::timeout()` (#17)
- `tokio::sync::Mutex` for sidecar state, `tokio::sync::Notify` replacing polling loops (#17)
- `poll_and_download()` helper eliminating ~70 lines of Rust duplication (#16)
- Typed `LocalTtsMode` enum, `WebcamPosition` enum with custom serde (#11, #16)
- Compositor throttled to 30fps, resolution capped at 1080p, 5s chunk intervals (#11)
- Stale recording artifact cleanup on startup (#16)
- Claude Code GitHub Actions integration (#14)
- Lefthook pre-commit hooks: frontend tests, Rust tests, typecheck in parallel (#9)
- CI pipeline: tests, typecheck, clippy, audit (#11)
- PyInstaller spec with NVIDIA excludes, stdout/stderr protection (#16)

### 🧪 Testing

- **~300 tests total**: 120 Rust, 90 frontend (Vitest), 70+ Python sidecar (pytest)
- Coverage: 59% statements, 52% branches, 70% functions
- Tests span config, recording pipeline, voice processing, security validation, UI state
- `test_binary.sh` — 11-endpoint sidecar integration suite
