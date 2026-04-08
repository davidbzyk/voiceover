#!/bin/bash
# Test suite for the PyInstaller sidecar binary.
# Run this BEFORE copying to binaries/ and building the .app.
#
# Usage: ./test_binary.sh [path-to-binary] [path-to-ffmpeg]

set -euo pipefail

BINARY="${1:-./dist/voiceover-tts}"
FFMPEG="${2:-ffmpeg}"
PORT=18999
DATA_DIR="/tmp/voiceover-binary-test-$$"
PASS=0
FAIL=0
TESTS=()

cleanup() {
    kill $SIDECAR_PID 2>/dev/null || true
    wait $SIDECAR_PID 2>/dev/null || true
    rm -rf "$DATA_DIR" /tmp/test-sine-*.wav /tmp/test-gen-*.wav 2>/dev/null || true
}
trap cleanup EXIT

pass() { PASS=$((PASS + 1)); TESTS+=("✅ $1"); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); TESTS+=("❌ $1: $2"); echo "  ❌ $1: $2"; }

echo "═══════════════════════════════════════════════════"
echo " Sidecar Binary Test Suite"
echo " Binary: $BINARY"
echo " FFmpeg: $FFMPEG"
echo "═══════════════════════════════════════════════════"
echo ""

# Create test audio
ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -ar 16000 -ac 1 /tmp/test-sine-$$.wav -y -loglevel warning

# Start sidecar
echo "Starting sidecar on port $PORT..."
rm -rf "$DATA_DIR"
$BINARY --port $PORT --data-dir "$DATA_DIR" --parent-pid $$ --ffmpeg "$FFMPEG" 2>&1 &
SIDECAR_PID=$!

# Wait for health
echo "Waiting for sidecar to become healthy..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo "Sidecar healthy after ${i}s"
        break
    fi
    if ! kill -0 $SIDECAR_PID 2>/dev/null; then
        echo "FATAL: Sidecar process died during startup"
        exit 1
    fi
    sleep 1
done

echo ""
echo "─── Test 1: Health endpoint ───"
HEALTH=$(curl -sf http://127.0.0.1:$PORT/health)
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='healthy'" 2>/dev/null; then
    pass "GET /health returns healthy status"
else
    fail "GET /health" "$HEALTH"
fi

echo ""
echo "─── Test 2: Models status ───"
MODELS=$(curl -sf http://127.0.0.1:$PORT/models/status)
if echo "$MODELS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['models'])==4" 2>/dev/null; then
    pass "GET /models/status returns 4 models"
else
    fail "GET /models/status" "$MODELS"
fi

echo ""
echo "─── Test 3: Transcription ───"
TRANSCRIBE=$(curl -sf -X POST http://127.0.0.1:$PORT/transcribe -F "file=@/tmp/test-sine-$$.wav" 2>&1)
if echo "$TRANSCRIBE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'text' in d and 'duration' in d" 2>/dev/null; then
    pass "POST /transcribe returns text + duration"
else
    fail "POST /transcribe" "$(echo "$TRANSCRIBE" | head -1)"
fi

echo ""
echo "─── Test 4: Transcribe from path ───"
TPATH=$(curl -sf -X POST http://127.0.0.1:$PORT/transcribe-path \
    -H "Content-Type: application/json" \
    -d "{\"audio_path\": \"/tmp/test-sine-$$.wav\"}" 2>&1)
if echo "$TPATH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'text' in d" 2>/dev/null; then
    pass "POST /transcribe-path returns text"
else
    fail "POST /transcribe-path" "$(echo "$TPATH" | head -1)"
fi

echo ""
echo "─── Test 5: Create profile ───"
PROFILE=$(curl -sf -X POST http://127.0.0.1:$PORT/profiles \
    -H "Content-Type: application/json" \
    -d '{"name": "Test Voice", "language": "en"}' 2>&1)
PROFILE_ID=$(echo "$PROFILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
if [ -n "$PROFILE_ID" ]; then
    pass "POST /profiles creates profile ($PROFILE_ID)"
else
    fail "POST /profiles" "$PROFILE"
fi

echo ""
echo "─── Test 6: List profiles ───"
PROFILES=$(curl -sf http://127.0.0.1:$PORT/profiles 2>&1)
if echo "$PROFILES" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)==1" 2>/dev/null; then
    pass "GET /profiles lists 1 profile"
else
    fail "GET /profiles" "$PROFILES"
fi

echo ""
echo "─── Test 7: Upload sample ───"
SAMPLE=$(curl -sf -X POST "http://127.0.0.1:$PORT/profiles/$PROFILE_ID/samples" \
    -F "audio=@/tmp/test-sine-$$.wav" \
    -F "reference_text=Test reference text" 2>&1)
if echo "$SAMPLE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'id' in d" 2>/dev/null; then
    pass "POST /profiles/{id}/samples uploads sample"
else
    fail "POST /profiles/{id}/samples" "$SAMPLE"
fi

echo ""
echo "─── Test 8: TTS generation (end-to-end) ───"
# This is the critical test — exercises the full generate→poll→audio path
# that breaks in prod builds when qwen_tts source files aren't bundled.
# Requires Qwen model to be downloaded; skip gracefully if not available.
GEN_RESP=$(curl -sf -X POST "http://127.0.0.1:$PORT/generate" \
    -H "Content-Type: application/json" \
    -d "{\"profile_id\": \"$PROFILE_ID\", \"text\": \"Hello, this is a test.\", \"language\": \"en\"}" 2>&1)
GEN_ID=$(echo "$GEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
if [ -n "$GEN_ID" ]; then
    pass "POST /generate returns generation ID ($GEN_ID)"

    # Poll for completion (up to 5 minutes for model loading + inference)
    echo "  Polling generation status (up to 300s)..."
    GEN_STATUS="pending"
    for i in $(seq 1 150); do
        STATUS_RESP=$(curl -sf "http://127.0.0.1:$PORT/generate/$GEN_ID/status" 2>&1)
        GEN_STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
        if [ "$GEN_STATUS" = "completed" ] || [ "$GEN_STATUS" = "error" ]; then
            break
        fi
        sleep 2
    done

    if [ "$GEN_STATUS" = "completed" ]; then
        pass "Generation completed"

        # Fetch audio and check it's a valid non-empty WAV
        AUDIO_HTTP=$(curl -sf -o /tmp/test-gen-$$.wav -w "%{http_code}" "http://127.0.0.1:$PORT/audio/$GEN_ID" 2>&1)
        AUDIO_SIZE=$(stat -f%z /tmp/test-gen-$$.wav 2>/dev/null || echo "0")
        if [ "$AUDIO_HTTP" = "200" ] && [ "$AUDIO_SIZE" -gt 1000 ]; then
            pass "GET /audio/{id} returns WAV (${AUDIO_SIZE} bytes)"
        else
            fail "GET /audio/{id}" "HTTP=$AUDIO_HTTP size=$AUDIO_SIZE"
        fi
        rm -f /tmp/test-gen-$$.wav
    elif [ "$GEN_STATUS" = "error" ]; then
        GEN_ERR=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','unknown'))" 2>/dev/null)
        fail "Generation failed" "$GEN_ERR"
    else
        fail "Generation poll" "Timed out (status=$GEN_STATUS)"
    fi
else
    fail "POST /generate" "$GEN_RESP"
fi

echo ""
echo "─── Test 9: YouTube extraction ───"
YT=$(curl -sf -X POST http://127.0.0.1:$PORT/extract-youtube \
    -H "Content-Type: application/json" \
    -d '{"url": "https://www.youtube.com/watch?v=FQrGo1MJpYE", "start": "0", "duration": 5}' 2>&1)
if echo "$YT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'audio_path' in d" 2>/dev/null; then
    pass "POST /extract-youtube downloads and extracts audio"
else
    fail "POST /extract-youtube" "$(echo "$YT" | head -1)"
fi

echo ""
echo "─── Test 10: Model download (whisper) ───"
DL=$(curl -sf -X POST http://127.0.0.1:$PORT/models/download \
    -H "Content-Type: application/json" \
    -d '{"model_name": "whisper-large-v3-turbo"}' 2>&1)
if echo "$DL" | grep -q "Download complete\|progress"; then
    pass "POST /models/download accepts whisper model name"
else
    fail "POST /models/download" "$(echo "$DL" | head -1)"
fi

echo ""
echo "─── Test 11: Delete profile ───"
DEL=$(curl -sf -X DELETE "http://127.0.0.1:$PORT/profiles/$PROFILE_ID" 2>&1)
if echo "$DEL" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok')==True" 2>/dev/null; then
    pass "DELETE /profiles/{id} removes profile"
else
    fail "DELETE /profiles/{id}" "$DEL"
fi

PROFILES_AFTER=$(curl -sf http://127.0.0.1:$PORT/profiles 2>&1)
if echo "$PROFILES_AFTER" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)==0" 2>/dev/null; then
    pass "Profile list empty after delete"
else
    fail "Profile list after delete" "$PROFILES_AFTER"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════"
echo " Results: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════════════"
for t in "${TESTS[@]}"; do echo "  $t"; done
echo ""

if [ $FAIL -gt 0 ]; then
    echo "⚠️  Some tests failed. Fix before building .app."
    exit 1
else
    echo "✅ All tests passed. Safe to copy binary and build."
fi
