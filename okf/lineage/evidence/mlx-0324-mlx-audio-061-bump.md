---
id: lineage/evidence/mlx-0324-mlx-audio-061-bump
schema: okf/schemas/v1/lineage.json
type: Lineage
title: "mlx 0.32.4 and mlx-audio 0.6.1: faster engines, one MLX thread"
description: The sidecar's move from mlx 0.31.1 and mlx-audio 0.5.8, measured on six engines, Whisper and CosyVoice, and the thread bug it exposed, 2026-10-25.
domain: voice-models
tags:
  - lineage
  - evidence
  - mlx-audio
  - dependencies
freshness: "2026-10-25T22:35:00Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 3
source_root: src-tauri/sidecar/
trial_matrix:
  six_engines_seed0: 144 of 144 clips on both pin sets; long-line RTF lower on every engine
  moss_five_seeds: 2 of 120 bad clips (WER over 0.2) on the old pins, 3 of 120 on the new
  voxcpm2_three_seeds: 3 of 72 bad clips on both
  qwen_xvector_short_line: drops "Thanks for watching" on 1 of 8 voices, against 3 of 8
  whisper_turbo_30s: same transcript word for word; warm 0.46 s old, 0.49 s new
  cosyvoice_vc_30s_warm: 3.35-3.62 s old, 2.83-2.86 s new; 29.99 s out on both
  frozen_binary_60s_sample: Replace Voice failed on the new pins until the MLX-thread fix, completes after
key_findings:
  - mlx-audio 0.6.1 pins mlx==0.32.4 exactly, so the two move together; the principal approved taking them before the 14-day age rule cleared.
  - Every engine is faster on the new pins (long-line RTF, old to new) and CosyVoice conversion is about 17% faster warm; MOSS and VoxCPM2 show no change in bad clips across seeds.
  - mlx 0.32 ties an array not yet evaluated to the thread that made it; the sidecar's MLX work hopped threads, so every MLX computation now runs on one thread (tts.run_mlx, tts.call_mlx).
  - 0.6.0's resampler fix (PR 1021) cuts imaging above 8 kHz in a 16 kHz reference upsampled for the engines from about 1e-4 to 2e-8 of the energy, so every engine hears a cleaner reference.
  - The frozen binary grows from 188 MB to 228 MB because mlx's Metal kernel library grows from 131 MB to 214 MB.
sources:
  - id: engine-tests
    resource: src-tauri/sidecar/test_engines.py
    type: local_doc
  - id: server-tests
    resource: src-tauri/sidecar/test_server_integration.py
    type: local_doc
  - id: mlx-audio-0-6-0
    resource: https://github.com/Blaizzy/mlx-audio/releases/tag/v0.6.0
    type: url
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-25T22:35:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - lineage/evidence/mlx-audio-058-engine-bench
    - standards/engine-admission
    - domains/voice-models/engines
  implements: []
  supersedes: []
  superseded_by: null
  part_of: lineage/evidence
---

# mlx 0.32.4 and mlx-audio 0.6.1: faster engines, one MLX thread

## Synthesis
The bench reran the [0.5.8 bench](./mlx-audio-058-engine-bench.md) on the sidecar's path
(`model.generate` with only text and the reference; 8 voices, 3 lines), with the new venv identical
to the old one except mlx, mlx-metal, mlx-audio and `sentencepiece` (now a core dependency).

Bad clips are Whisper WER over 0.2 (seed 0, plus seeds 1-4 where shown); leaks count clips that
speak the reference transcript's words.

| Engine | Long-line RTF old | New | Bad clips old | New |
| --- | --- | --- | --- | --- |
| Qwen3-TTS 1.7B (x-vector) | 0.30 | 0.25 | 3 of 24 (1 leak) | 1 of 24 (no leak) |
| VoxCPM2 | 0.80 | 0.66 | 3 of 72 | 3 of 72 |
| MOSS-TTS Local | 0.46 | 0.31 | 2 of 120 | 3 of 120 |
| OmniVoice | 0.19 | 0.14 | 5 of 24 (3 leaks) | 3 of 24 (3 leaks) |
| Fish S2 Pro | 1.53 | 1.03 | 2 of 24 | 0 of 24 |
| Chatterbox | 0.36 | 0.31 | 1 of 24 | 1 of 24 |

A fixed seed reproduces audio only within one mlx version, so seed 0 alone could not tell a
regression from chance; MOSS ran five seeds and VoxCPM2 three, on both pin sets. The bad clips are
short lines that lose their opening phrase, on both versions.

The frozen binary on the new pins failed Replace Voice with a 60 s sample: the reference was trimmed
to 30 s on the event-loop thread and read on a worker, "There is no Stream(gpu, 2) in current
thread". A lazy slice made on one thread fails on another on mlx 0.32.4 and works on 0.31.1; an
evaluated array crosses either way. Qwen also decoded its reference and generated on different
executor threads. All MLX computation now runs on one dedicated thread, and voice conversion hands
it one chunk at a time so a transcription waits at most one chunk inside the app's 120 s budget.
