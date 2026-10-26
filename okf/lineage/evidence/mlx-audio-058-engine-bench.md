---
id: lineage/evidence/mlx-audio-058-engine-bench
schema: okf/schemas/v1/lineage.json
type: Lineage
title: Six TTS engines on mlx-audio 0.5.8, and the helper that broke MOSS
description: Bench of the six shipped TTS engines on the sidecar's pins (mlx-audio 0.5.8, mlx 0.31.1), 8 voices x 3 lines, 2026-10-23.
domain: voice-models
tags:
  - lineage
  - evidence
  - mlx-audio
freshness: "2026-10-25T22:35:00Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 1
source_root: .notes/scratch/2026-10-22-voice-bench/
trial_matrix:
  generate_audio_helper_moss: looped to the 96 s limit on 13 of 24 clips, WER 0.258
  model_generate_direct_moss: 24 of 24 clean, WER 0.009
  qwen_xvector_short_line_0_5_8: speech starts 0.35-0.85 s in, 3 of 8 voices lose "Thanks for watching"
  qwen_xvector_short_line_0_6_1: speech starts about 0.05 s in, 1 of 8 loses it
  sidecar_end_to_end: all six engines plus a 30 s voice conversion through the HTTP API
key_findings:
  - mlx-audio 0.5.8's generate_audio helper forces temperature 0.7 and top_p 0.9 over each model's own defaults (fixed upstream in 0.6.0, PR 1043); the sidecar calls model.generate and passes only text and the voice reference.
  - On the planned pins all six engines produce 24 of 24 clips; median long-line RTF Qwen 0.30, VoxCPM2 0.81, MOSS 0.47, OmniVoice 0.19, Fish S2 Pro 1.53, Chatterbox 0.36.
  - mlx 0.32.4 ran 15-40% faster than 0.31.1 on most engines; the pin stays at 0.31.1 so Whisper and CosyVoice do not move.
  - OmniVoice still leaks the T2 reference transcript (3 of 24); the other five leak nothing.
sources:
  - id: engine-tests
    resource: src-tauri/sidecar/test_engines.py
    type: local_doc
  - id: upstream-1043
    resource: https://github.com/Blaizzy/mlx-audio/pull/1043
    type: url
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-23T22:50:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - domains/voice-models/engines
    - lineage/evidence/qwen3-tts-icl-reference-leak
    - lineage/evidence/mlx-0324-mlx-audio-061-bump
  implements: []
  supersedes: []
  superseded_by: null
  part_of: lineage/evidence
---

# Six TTS engines on mlx-audio 0.5.8, and the helper that broke MOSS

## Synthesis
The bench harness (in the principal's notes repo, `.notes/scratch/2026-10-22-voice-bench/`) first called mlx-audio's `generate_audio` helper. On 0.5.8 that helper sets
`temperature=0.7, top_p=0.9` for every model, and MOSS-TTS Local repeated phrases ("What
changed? What changed?") until its 96 s limit. Calling `model.generate` directly, which leaves
sampling to the model's own defaults, gave MOSS a WER of 0.009. The sidecar's engine path does the
same; `test_engines.py::test_generate_speech_leaves_sampling_to_the_model` holds it there.

## Resolved
Qwen x-vector started short lines late on 0.5.8. The sidecar moved to mlx-audio 0.6.1 and mlx 0.32.4
on 2026-10-25, with the principal's yes ahead of the 14-day age rule; the
[bump evidence](./mlx-0324-mlx-audio-061-bump.md) has the rerun.
