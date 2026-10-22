---
id: lineage/evidence/whisper-reference-transcript-loop
schema: okf/schemas/v1/lineage.json
type: Lineage
title: Whisper loops on Create Voice clips; looping segments are dropped
description: mlx-audio Whisper returned a 30 s clip as one word repeated hundreds of times; the compression-ratio guard plus dropping still-looping segments fixed it.
domain: voice-models
tags:
  - lineage
  - evidence
  - whisper
freshness: "2026-10-22T18:36:00Z"
version: 1.0.0
status: draft
kcc_action: condense
source_file_count: 1
source_root: src-tauri/sidecar/
trial_matrix:
  threshold_off: 1684 chars, "Rock" x223
  threshold_2_4_only: unchanged, last retry still looped
  drop_looped_segments: 569 chars, identical across runs
key_findings:
  - With compression_ratio_threshold off, Whisper large-v3-turbo emitted one word ~223 times for a 30 s clip.
  - Whisper's temperature fallback returns its last attempt even when every temperature still loops, so the threshold alone did not fix it.
  - Dropping segments whose compression ratio stays above 2.4, with mx.random.seed(0) for repeatable retries, fixed it on the real clip (commit 760883a on branch fix/release-prep, not yet on main).
  - The looping transcript fed Qwen as reference text and made Create Voice time out.
sources:
  - id: fix-commit
    resource: git:760883a
    type: git_ref
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-22T18:36:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - lineage/evidence/qwen3-tts-icl-reference-leak
  implements: []
  supersedes: []
  superseded_by: null
  part_of: lineage/evidence
---

# Whisper loops on Create Voice clips; looping segments are dropped

## Synthesis
Status: the fix is commit `760883a` on branch `fix/release-prep` and is not on `main` yet; this note
moves to stable when that commit merges. With the fix, `tts.transcribe` keeps Whisper's 2.4 compression-ratio guard, seeds MLX's sampler so retries are
repeatable, and drops any segment still above the threshold after all retries, logging its time
range. Tests (same commit): `TestTranscribeLoopGuard` in `src-tauri/sidecar/test_tts.py`.
