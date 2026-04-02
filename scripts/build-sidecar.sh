#!/bin/bash
# Build the TTS sidecar binary and copy it to the Tauri binaries directory.
#
# Usage: ./scripts/build-sidecar.sh [--skip-tests]
#
# Steps:
#   1. Activate the sidecar venv
#   2. Build with PyInstaller
#   3. Run binary tests (unless --skip-tests)
#   4. Copy to src-tauri/binaries/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.sidecar-venv"
SIDECAR_DIR="$PROJECT_DIR/src-tauri/sidecar"
BINARIES_DIR="$PROJECT_DIR/src-tauri/binaries"
TARGET_BINARY="$BINARIES_DIR/voiceover-tts-aarch64-apple-darwin"
SKIP_TESTS=false

for arg in "$@"; do
    case $arg in
        --skip-tests) SKIP_TESTS=true ;;
    esac
done

echo "═══════════════════════════════════════════════════"
echo " Building TTS Sidecar"
echo "═══════════════════════════════════════════════════"

# 1. Activate venv
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Sidecar venv not found at $VENV_DIR"
    echo "Create it with: python3 -m venv .sidecar-venv && source .sidecar-venv/bin/activate && pip install -r src-tauri/sidecar/requirements.txt"
    exit 1
fi
source "$VENV_DIR/bin/activate"
echo "Using Python: $(python --version) at $(which python)"

# 2. Build with PyInstaller
echo ""
echo "─── Building with PyInstaller ───"
cd "$SIDECAR_DIR"
pyinstaller voiceover-tts.spec --noconfirm
DIST_BINARY="$SIDECAR_DIR/dist/voiceover-tts"

if [ ! -f "$DIST_BINARY" ]; then
    echo "ERROR: PyInstaller build failed — no binary at $DIST_BINARY"
    exit 1
fi

DIST_SIZE=$(du -h "$DIST_BINARY" | awk '{print $1}')
echo "Built: $DIST_BINARY ($DIST_SIZE)"

# 3. Run binary tests
if [ "$SKIP_TESTS" = false ]; then
    echo ""
    echo "─── Running binary tests ───"
    bash "$SIDECAR_DIR/test_binary.sh" "$DIST_BINARY"
fi

# 4. Copy to Tauri binaries
echo ""
echo "─── Copying to Tauri binaries ───"
mkdir -p "$BINARIES_DIR"
cp "$DIST_BINARY" "$TARGET_BINARY"
echo "Copied to: $TARGET_BINARY"
ls -lh "$TARGET_BINARY"

echo ""
echo "═══════════════════════════════════════════════════"
echo " Done. Run 'pnpm tauri build' to bundle into app."
echo "═══════════════════════════════════════════════════"
