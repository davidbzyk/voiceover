---
id: lineage/evidence/tts-runaway-and-mlx-cache
schema: okf/schemas/v1/lineage.json
type: Lineage
title: A MOSS phrase that never stopped, and MLX's unbounded buffer cache
description: Why the first replace run with every engine nearly ran a 137 GB Mac out of memory, what each part measured, and the bounds that fixed it, 2026-10-27.
domain: voice-models
tags:
  - lineage
  - evidence
  - mlx
  - moss-tts
freshness: "2026-10-27T18:30:00Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 4
source_root: src-tauri/sidecar/
trial_matrix:
  moss_no_target_short_phrase: ran to the bound on 3 of 8 seeds ("My fellow Americans,") and 2 of 8 ("Whoever did this,")
  moss_target_13_or_20_tokens: ended exactly at the target 22 of 22 (three phrases)
  moss_target_10_to_12_tokens: never reached the bound 30 of 30 (three phrases)
  moss_target_under_10_tokens: ran on at 4 tokens 6 of 6, at 6 tokens 6 of 6, at 8 tokens 4 of 6 (three phrases)
  voxcpm2_cache_uncapped: 34.5 GB peak over seven phrases (5 GB of weights)
  voxcpm2_cache_2gb: 10.1 GB peak, same speed
  voxcpm2_cache_0: 8.5 GB peak, 2.5x slower
  replace_route_30s_all_engines: 7 of 7 completed, peak 7 to 20 GB per engine
  replace_route_410s_all_engines: 7 of 7 completed, no phrase reached its bound, sidecar peak 31 GB (Fish S2 Pro)
key_findings:
  - MOSS-TTS Local with no length target sometimes never samples its end token on a short phrase; unbounded it runs toward its 4,096-frame default (5.5 min of audio).
  - MLX keeps freed buffers for reuse with no limit; MOSS appends to its output array every step, so the kept buffers grew past 40 GB on one phrase and the principal's Mac neared out of memory.
  - MOSS takes a target length (the `tokens` field of its prompt) and stops there, but ignores a target under 10 tokens (0.8 s); Whisper timed "you know," at 0.3 s.
  - Each engine's max_tokens unit is a fixed slice of audio (seconds per unit = 1 / tokens_per_second); Qwen and MOSS 12.5 a second, Fish S2 Pro 21.53, Chatterbox 25, VoxCPM2 6.25. OmniVoice takes no max_tokens.
  - Healthy phrases from all six engines came out at most 2.1x their original speech, so a bound of 3x plus 2 s never cut one.
  - Fish S2 Pro's slowest phrase on the 410 s recording took 37.9 s between progress updates, against a 60 s stall window set when CosyVoice chunks (2.5 s) were the slowest.
sources:
  - id: engine-tests
    resource: src-tauri/sidecar/test_engines.py
    type: local_doc
  - id: server-tests
    resource: src-tauri/sidecar/test_server_integration.py
    type: local_doc
  - id: chunked-tests
    resource: src-tauri/sidecar/test_chunked_tts.py
    type: local_doc
  - id: registry
    resource: src-tauri/sidecar/server.py
    type: local_doc
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-27T18:30:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - architecture/voice-replacement
    - standards/engine-admission
    - lineage/evidence/mlx-audio-058-engine-bench
  implements: []
  supersedes: []
  superseded_by: null
  part_of: lineage/evidence
---

# A MOSS phrase that never stopped, and MLX's unbounded buffer cache

## Synthesis
The first replace run with every engine (engine picker branch, 2026-10-27) nearly ran the
principal's Mac out of memory on MOSS-TTS Local's first phrase. Two things combined. MOSS, given no
length, sometimes never samples its end token on a short phrase, and mlx-audio's default for that is
4,096 frames. Meanwhile MLX kept every freed GPU buffer for reuse: MOSS appends one frame to its
output array per step, so each step freed a buffer and asked for a slightly larger one. A probe with
a 40 GB kill switch reached it before MOSS's decode step. MOSS's weights are 13.4 GB.

A new seed rescues MOSS only some of the time (it ran on with 2 or 3 of 8 seeds), and a recording has
dozens of short phrases, so retrying alone would still fail most long jobs. MOSS's prompt takes a
target length in tokens. With a target of 10 tokens or more it never ran on (52 of 52 runs across
four phrases of 3 to 20 characters), and the 22 runs checked for length ended exactly at the target.

## Resolution
- `tts.MLX_CACHE_LIMIT_BYTES` (2 GB) is set when the sidecar starts and covers every engine,
  Whisper and CosyVoice included.
- Each text-to-speech phrase is bounded at 3x its spoken length plus 2 s through the row's
  `tokens_per_second`; a phrase that reaches the bound is spoken again with a new seed, and a second
  run to the bound fails the job naming the engine.
- MOSS's row carries `length_hint` (`tokens`, at least 10), set to the phrase's spoken length less the
  pauses the padder puts back (`chunked_tts.reinserted_gap_seconds`, shared with
  `pad_audio_to_match_timing`).
- `local_tts::STALL_AFTER_SECS` went from 60 s to 240 s for Fish's 37.9 s phrase.

After the fix, both recordings completed with all seven engines and no phrase reached its bound:

| Engine | 410 s wall | Longest gap | WER | Peak memory |
| --- | --- | --- | --- | --- |
| CosyVoice3 0.5B | 32.9 s | 2.0 s | 0.148 | 10 GB |
| Qwen3-TTS 1.7B | 84.4 s | 8.6 s | 0.060 | 10 GB |
| VoxCPM2 | 201.6 s | 21.2 s | 0.030 | 12 GB |
| MOSS-TTS Local v1.5 | 126.9 s | 12.1 s | 0.051 | 21 GB |
| OmniVoice | 86.9 s | 3.5 s | 0.105 | 18 GB |
| Fish S2 Pro | 326.8 s | 37.9 s | 0.045 | 31 GB |
| Chatterbox | 116.2 s | 17.7 s | 0.104 | 16 GB |

WER is the output re-transcribed against the source's transcript; peak memory is the sidecar's
footprint, which includes Whisper. Chatterbox added 22 words over the recording; the other engines
added none. The earlier PyTorch Qwen run took 10 min 01 s on the same recording.
