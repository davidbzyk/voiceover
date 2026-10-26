#!/usr/bin/env bash
# Check src-tauri/sidecar/cosyvoice_mlx against the mlx-audio-plus 0.1.8 wheel it was copied from.
# Applies the copy's only edits (import paths, conversion scripts removed) to the wheel and diffs:
# no output and exit 0 means the copy is the wheel's code. Our own files (loader.py, README.md,
# LICENSE, the package __init__ files) are left out. Usage: ./scripts/check-cosyvoice-copy.sh
set -euo pipefail

WHEEL=mlx_audio_plus-0.1.8-py3-none-any.whl
SHA256=2e44ad5a65d46391db59b694ad4b9e9b1a739ea79c1e6013ad8f7db5cea9472b  # PyPI's digest for $WHEEL
COPY="$(cd "$(dirname "$0")/.." && pwd)/src-tauri/sidecar/cosyvoice_mlx"
WORK="${XDG_CACHE_HOME:-$HOME/.cache}/voiceover/cosyvoice-copy-check"

rm -rf "$WORK" && mkdir -p "$WORK/wheel"
URL=$(curl -fsS https://pypi.org/pypi/mlx-audio-plus/0.1.8/json \
  | python3 -c "import sys, json; print(next(u['url'] for u in json.load(sys.stdin)['urls'] if u['filename'] == '$WHEEL'))")
curl -fsSL -o "$WORK/$WHEEL" "$URL"
echo "$SHA256  $WORK/$WHEEL" | shasum -a 256 -c --quiet
unzip -q "$WORK/$WHEEL" -d "$WORK/wheel"

status=0
for dir in tts/models/cosyvoice2 tts/models/cosyvoice3 codec/models/s3gen codec/models/s3tokenizer; do
  src="$WORK/wheel/mlx_audio/$dir"
  rm -rf "$src/scripts"
  find "$src" -name '*.py' -exec perl -pi -e '
    s/\bmlx_lm\.models\./mlx_audio.lm.models./g;
    s/\bmlx_audio\.codec\.models\.(s3gen|s3tokenizer)\b/cosyvoice_mlx.codec.models.$1/g;
    s/^(\s*)from \.\.base import/$1from mlx_audio.tts.models.base import/;
    $_ = "" if /from \.scripts\.convert import convert_from_source|^\s*"convert_from_source",\s*$/;
  ' {} +
  diff -r -x __pycache__ "$src" "$COPY/$dir" || status=1
done
exit $status
