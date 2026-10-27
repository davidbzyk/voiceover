# Changelog

## [0.4.0] - 2026-10-27

**50 app files | 3,167 additions | 765 deletions | 5 PRs | 40 commits** (excluding the OKF notes, the vendored CosyVoice copy and lockfiles)

### 🌟 New Features

- **Pick the engine for every local conversion** — CosyVoice (speech to speech, keeps your pacing) or a text-to-speech engine that speaks each phrase at its original time. Pick it on the Record screen, in Settings, in the voice picker on Preview and the Library, and in Create Voice (#34)
- **Five more text-to-speech engines** — VoxCPM2, MOSS-TTS Local v1.5, OmniVoice, Fish S2 Pro and Chatterbox, beside Qwen3-TTS 1.7B (#31)
- **The engine shows wherever the voice does** — Preview, Convert again and Library cards read "voice · engine", and the progress bar names the engine at work (#34)
- **Models cards show size and licence**, with a Non-commercial mark on OmniVoice and Fish S2 Pro (#34)

### 🐛 Bug Fixes

- **A conversion could use up the Mac's memory** — an engine could keep speaking past the end of a phrase while MLX held on to freed memory, past 40 GB on one phrase. Each phrase now stops at 3× its length plus 2 s and is spoken again once if it runs that long, and MLX keeps at most 2 GB of freed memory. All seven engines replaced a 6m50s recording at 10–31 GB peak (#34)
- **The status bar said "No profile"** with a profile picked (#34)
- **One dropped connection failed a whole conversion** — the status check now tries again; a job with nothing new for 240 s still fails (#34)
- **Create Voice** stayed stuck after Retry Connection found the engine, and had no way forward when no text-to-speech engine was downloaded (#34)

### 🛠️ Other Improvements

- **No PyTorch in the voice engine** — it runs entirely on MLX (mlx 0.32.4, mlx-audio 0.6.1). Qwen replaced the 6m50s recording in 84 s, down from 10 minutes on PyTorch (#33)
- After updating, Whisper and CosyVoice's tokenizer download once more; the old PyTorch Qwen and Whisper downloads (about 7 GB) are no longer used (#33)
- Replacing a voice is no longer always speech-to-speech, as 0.3.0 had it: CosyVoice and the text-to-speech engines are each one pick away (#34)
- CosyVoice3's MLX code ships as its own package, checked against its source by `scripts/check-cosyvoice-copy.sh` (#32)
- What we learn about engines, the sidecar and releases is kept in `okf/` (#30)

## [0.3.0] - 2026-10-22

**29 app files | 2,449 additions | 943 deletions | 6 PRs | 16 commits** (excluding the vendored code reviewer and lockfiles)

### 🌟 New Features

- **Pick any voice per conversion** — choose an ElevenLabs voice or a local CosyVoice profile right on Preview, instead of one global setting (#23)
- **Convert again** — every converted recording keeps its original voice as `<name>.original.m4a`, so you can redo it in another voice from Preview or a Library card (🎙️) (#23)
- **Hear the result right away** — after saving, Preview plays the converted video (#23)
- **Cancel** — stop a conversion at any step; the sidecar job stops too (#23)
- **Live progress** — the bar moves chunk by chunk instead of sitting at 15% (#23)

### 🐛 Bug Fixes

- **Long recordings time out** — a 6m50s recording failed with "Local TTS timed out after 300s". Local replacement now uses speech-to-speech (CosyVoice) like ElevenLabs: about 40s instead of 10 minutes on the same recording, with no total time limit (#23)
- **Voice drifting out of sync** on long files — chunk stitching repeated half a second at every seam (8.5s over 410s); output now matches the input length (#23)
- **ElevenLabs recordings over 5 minutes** — split at pauses into ≤290s pieces and rejoined at exact lengths (#23)
- **A retry queued behind a timed-out job** — abandoned jobs are now cancelled instead of holding the engine (#23)
- **"Convert again" safety** — a crash or full disk can no longer leave a half-written video; deleting a recording mid-conversion can't bring it back (#23)
- **12 dependency security advisories** cleared, including `rustls` and `rustls-webpki` (TLS for ElevenLabs and Drive), `h2`, `quick-xml` and `rkyv` (#25)
- **CI back to green** — lockfile drift and new clippy lints fixed (#26, #28)

### 🛠️ Other Improvements

- **Code review CI** — every PR gets an automated review at max effort (#24, #27)
- Declared minimum Rust is now 1.88, matching what the dependencies need (#28)
- The TTS/VC toggle is gone: replacing a voice is always speech-to-speech; Qwen is still used to speak the test sentence when creating a voice (#23)

## [0.2.0] - 2026-04-08

**57 files | 3,086 additions | 608 deletions | 3 PRs | 29 commits**

### 🌟 New Features

- **Model Settings panel** — dedicated sidebar page to browse, download, and manage AI models with category tags, recommended badges, and Whisper model selection (#21)
- **Video rename** — rename recordings directly from the library view (#20)
- **Auto-detect `ELEVENLABS_API_KEY`** from environment variables — no manual entry needed if already exported (#20)
- **Version bump tooling** — `bump.sh` script for consistent release versioning

### 🐛 Bug Fixes

- **Slow/deep voice on first generation** after switching voices — TTS engine now reinitializes properly on voice change
- **Video clipping** in both TTS and voice conversion modes — output duration now matches source (#20)
- **TTS timing and transcription accuracy** improvements — better duration probing and segment alignment (#20)
- **Model cache not refreshing** after download completes — cache invalidation added (#21)
- **CosyVoice3 missing** from prerequisites UI and download JSON parsing error (#20)
- **Sidecar code signing** added to PyInstaller build for macOS Gatekeeper (#20)
- **84 findings** from comprehensive codebase review resolved — spanning error handling, edge cases, and code quality
- **22 model-related bugs** fixed in consolidated review (#21)
- **`whisper-small` removed** — too low quality for production use (#21)
- **Models nav alignment** fixed in sidebar (#21)
- **`yt-dlp` options** corrected for voice extraction

### 🛠️ Other Improvements

- Models page moved from settings sub-tab to dedicated sidebar route with `ModelInfo` struct enriched with `category` and `recommended` fields (#21)
- `cleanup_stale_recordings` test made deterministic (#21)
- README updated: Linux references removed (macOS-only app), visual architecture diagram replaces ASCII, TTS audio cutoff added to known issues (#19, #20)
- Integration tests updated for CosyVoice3 three-model setup (#20)
- Unused CI workflow files cleaned up (#20)

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
