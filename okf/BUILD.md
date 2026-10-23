---
id: BUILD
schema: okf/schemas/v1/base.json
type: Concept
title: Build
description: Build, migrated verbatim from BUILD.md.
domain: meta
tags:
  - build
  - meta
  - migrated
freshness: "2026-10-23T23:36:54Z"
version: 1.0.0
status: stable
sources:
  - id: build_md
    resource: docs/BUILD.md
    title: Build
    type: local_doc
    sha256: e9693fb845bf8bae915e687f9be22284d95a714ea3d95e85a233b40f232dfcaf
generated:
  by: process:okf_migrate
  at: "2026-10-22T18:35:58Z"
relations:
  depends_on: []
  relates_to: []
  implements: []
  supersedes: []
  superseded_by: null
  part_of: null
---

# Build

<!-- okf:verbatim:start docs/BUILD.md -->
# Building & Releasing VoiceOver

> **macOS only.** VoiceOver builds and runs on macOS (Apple Silicon or Intel). The local TTS sidecar uses MLX and works best on Apple Silicon.

## Prerequisites

- **macOS** (Apple Silicon or Intel)
- **Xcode** — install from the App Store, then run:
  ```bash
  xcode-select --install
  ```
- **Rust** — install via [rustup](https://rustup.rs):
  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```
- **pnpm** — install via [pnpm.io](https://pnpm.io/installation):
  ```bash
  npm install -g pnpm
  ```
- **Static ffmpeg binary** — required for bundling inside the app

## Setup

1. Clone the repo:
   ```bash
   git clone git@github.com:davidbzyk/voiceover.git
   cd voiceover
   ```

2. Install frontend dependencies:
   ```bash
   pnpm install
   ```

3. Download a static ffmpeg binary for your architecture:

   **Apple Silicon (M1/M2/M3/M4):**
   ```bash
   mkdir -p src-tauri/binaries
   curl -L -o src-tauri/binaries/ffmpeg.zip \
     "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
   unzip -o src-tauri/binaries/ffmpeg.zip -d src-tauri/binaries/
   mv src-tauri/binaries/ffmpeg src-tauri/binaries/ffmpeg-aarch64-apple-darwin
   rm src-tauri/binaries/ffmpeg.zip
   chmod +x src-tauri/binaries/ffmpeg-aarch64-apple-darwin
   ```

   **Intel Mac:**
   ```bash
   mkdir -p src-tauri/binaries
   curl -L -o src-tauri/binaries/ffmpeg.zip \
     "https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/release/ffmpeg.zip"
   unzip -o src-tauri/binaries/ffmpeg.zip -d src-tauri/binaries/
   mv src-tauri/binaries/ffmpeg src-tauri/binaries/ffmpeg-x86_64-apple-darwin
   rm src-tauri/binaries/ffmpeg.zip
   chmod +x src-tauri/binaries/ffmpeg-x86_64-apple-darwin
   ```

   Verify it works:
   ```bash
   src-tauri/binaries/ffmpeg-*-apple-darwin -version
   ```

## Development

Run the app in dev mode (hot-reloading frontend + Rust backend):

```bash
pnpm tauri dev
```

## Building for Release

Build the .app bundle and .dmg installer:

```bash
pnpm tauri build
```

Output files:

| Artifact | Location |
|----------|----------|
| .app bundle | `src-tauri/target/release/bundle/macos/VoiceOver.app` |
| .dmg installer | `src-tauri/target/release/bundle/dmg/VoiceOver_<version>_aarch64.dmg` |

The .dmg is what you distribute. Users drag VoiceOver.app into their Applications folder.

## Creating a GitHub Release

The version comes from `src-tauri/tauri.conf.json` (bumped with `scripts/bump-version.sh`), so read it
instead of typing it:

1. Tag the version on `main`:
   ```bash
   VERSION=$(jq -r .version src-tauri/tauri.conf.json)
   git tag "v$VERSION"
   git push origin "v$VERSION"
   ```

2. Create the release with the notarized, stapled .dmg attached:
   ```bash
   gh release create "v$VERSION" \
     "src-tauri/target/release/bundle/dmg/VoiceOver_${VERSION}_aarch64.dmg" \
     --title "VoiceOver v$VERSION" \
     --notes-file <(sed -n "/^## \[$VERSION\]/,/^## \[/p" CHANGELOG.md | sed '$d')
   ```

## Running Tests

```bash
pnpm test:all          # Frontend + Rust tests
pnpm test              # Frontend only
pnpm test:rust         # Rust only
```

## Sidecar Development

The Python TTS sidecar can be run standalone for development and testing:

```bash
python3 -m venv .sidecar-venv
source .sidecar-venv/bin/activate
pip install -r src-tauri/sidecar/requirements.txt
pip install pytest==8.3.3 httpx==0.28.1   # the sidecar tests; the pre-commit hook runs them from this venv
python src-tauri/sidecar/server.py --port 8123 --data-dir ./.sidecar-data --parent-pid $$
```

`--parent-pid` is required: the sidecar exits when that process dies, so pass your shell's PID.

Build the venv from `requirements.txt` alone and rebuild it when that file changes. A venv made
before the mlx-audio 0.5.8 update still holds `mlx-audio-plus`, `qwen-tts` and torch, and the
fork's files would shadow mlx-audio's: `rm -rf .sidecar-venv` first.

To build the sidecar as a standalone binary (bundled into the app for distribution), install
PyInstaller into the same venv and run the build script. It builds, runs `test_binary.sh` against the
binary, and copies it to `src-tauri/binaries/voiceover-tts-aarch64-apple-darwin`, the path Tauri bundles:

```bash
pip install pyinstaller==6.19.0
./scripts/build-sidecar.sh
```

## Notes

- **Code signing**: The build is configured with `signingIdentity: "Developer ID Application"` and hardened runtime. If a valid Developer ID certificate is in your keychain, the app will be signed automatically. Without the certificate, the app will be unsigned and users will see a macOS Gatekeeper warning on first launch (right-click → "Open" → "Open").
- **ffmpeg is bundled**: The static ffmpeg binary is included inside the .app so users don't need to install it separately. It's ~60MB and excluded from git via `.gitignore`.
- **Settings location**: App config is stored at `~/Library/Application Support/com.voiceover.app/config.json`, not inside the .app bundle.
<!-- okf:verbatim:end -->