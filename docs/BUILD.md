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
| .dmg installer | `src-tauri/target/release/bundle/dmg/VoiceOver_0.1.0_aarch64.dmg` |

The .dmg is what you distribute. Users drag VoiceOver.app into their Applications folder.

## Creating a GitHub Release

1. Tag the version:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. Create the release with the .dmg attached:
   ```bash
   gh release create v0.1.0 \
     src-tauri/target/release/bundle/dmg/VoiceOver_0.1.0_aarch64.dmg \
     --title "VoiceOver v0.1.0" \
     --notes "Initial release. macOS Apple Silicon only."
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
python src-tauri/sidecar/server.py --port 8123 --data-dir /tmp/voiceover-tts
```

To build the sidecar as a standalone binary (bundled into the app for distribution):

```bash
cd src-tauri/sidecar && pyinstaller voiceover-tts.spec
```

## Notes

- **Code signing**: The build is configured with `signingIdentity: "Developer ID Application"` and hardened runtime. If a valid Developer ID certificate is in your keychain, the app will be signed automatically. Without the certificate, the app will be unsigned and users will see a macOS Gatekeeper warning on first launch (right-click → "Open" → "Open").
- **ffmpeg is bundled**: The static ffmpeg binary is included inside the .app so users don't need to install it separately. It's ~60MB and excluded from git via `.gitignore`.
- **Settings location**: App config is stored at `~/Library/Application Support/com.voiceover.app/config.json`, not inside the .app bundle.
