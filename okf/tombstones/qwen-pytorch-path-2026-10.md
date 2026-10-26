---
id: tombstones/qwen-pytorch-path-2026-10
schema: okf/schemas/v1/tombstone.json
type: Tombstone
title: Tombstone — Qwen3-TTS on PyTorch (qwen-tts 0.1.1), October 2026
description: The sidecar's PyTorch Qwen engine, its transformers patch and its voice-prompt cache, replaced by Qwen on MLX through mlx-audio.
domain: voice-models
tags:
  - tombstone
  - sidecar
  - qwen3-tts
freshness: "2026-10-23T23:30:00Z"
version: 1.0.0
status: tombstone
kcc_action: kill
killed_at: "2026-10-23T00:00:00Z"
killed_by: human:principal
tombstone_reason: Qwen runs on MLX through mlx-audio at RTF about 0.3 against about 1.5 on PyTorch MPS, and qwen-tts pinned transformers 4.57.3 while mlx-audio 0.5.8 needs 5.14 or newer.
prior_path: src-tauri/sidecar/tts.py (load_qwen_model, create_voice_prompt, generate_speech) and server.py (check_model_inputs patch), main before PR 1 of the voice engines plan
superseded_by: domains/voice-models/engines
sources:
  - id: tts-before
    resource: src-tauri/sidecar/tts.py
    type: local_doc
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-23T23:30:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - lineage/evidence/qwen3-tts-icl-reference-leak
    - lineage/evidence/mlx-audio-058-engine-bench
  implements: []
  supersedes: []
  superseded_by: domains/voice-models/engines
  part_of: tombstones
---

# Tombstone — Qwen3-TTS on PyTorch (qwen-tts 0.1.1), October 2026

## What was tried
`Qwen/Qwen3-TTS-12Hz-1.7B-Base` through `qwen_tts.Qwen3TTSModel` on PyTorch MPS, with an in-context
voice prompt built from the last sample and its transcript, cached as a torch `.prompt` file per
sample hash under the data dir's `cache/`. A no-op patch of `transformers.check_model_inputs` let
qwen-tts 0.1.1's decorators run on transformers 4.56–4.57. A one-word warm-up generation primed
the MPS shaders on load.

## Why it ended
- Speed: about 1.5 real-time factor on MPS; the same model on MLX runs at about 0.3.
- Leak: the in-context prompt carried the transcript, and Qwen sometimes spoke its last words.
- Pins: qwen-tts held transformers at 4.57.3, so the sidecar needed `--no-deps` installs, and it
  blocked mlx-audio 0.5.8 (transformers 5.14 or newer).

## What carries forward
Qwen stays under the same registry key, `qwen-tts-1.7B`, now on `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`
in x-vector-only mode. Old `.prompt` files in the data dir's `cache/` folder are unused and safe to delete.
