---
id: tombstones/multi-model-backends-2026-04
schema: okf/schemas/v1/tombstone.json
type: Tombstone
title: Tombstone — Seven-backend sidecar (feat/multi-model, April 2026)
description: The April 2026 attempt to run seven TTS/VC engines in one sidecar, abandoned over dependency conflicts and frozen-binary imports.
domain: voice-models
tags:
  - tombstone
  - sidecar
  - dependencies
freshness: "2026-10-22T18:36:00Z"
version: 1.0.0
status: tombstone
kcc_action: kill
killed_at: "2026-04-05T00:00:00Z"
killed_by: human:principal
tombstone_reason: Three of seven engines could not share the sidecar's Python environment, and per-engine venvs could not import code from the frozen PyInstaller binary.
prior_path: branch feat/multi-model (7236e11, 1d39cd6, ba38421)
superseded_by: standards/engine-admission
sources:
  - id: branch-multi-model
    resource: git:feat/multi-model
    type: git_ref
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-22T18:36:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - domains/voice-models/engines
  implements: []
  supersedes: []
  superseded_by: standards/engine-admission
  part_of: tombstones
---

# Tombstone — Seven-backend sidecar (feat/multi-model, April 2026)

## What was tried
Commit `7236e11` (2026-04-05) split the sidecar into pluggable backends: Qwen3-TTS, CosyVoice3,
Chatterbox, F5-TTS (MLX), Fish Speech 1.5, GPT-SoVITS v3 and OpenVoice V2, with a registry and a
backend picker. `1d39cd6` added per-backend Python venvs run as HTTP subprocesses. `ba38421` is
titled "last one before abandoning". None of it reached `main`.

## Why it died
- Only four engines could share one venv. Fish Speech pins `torch==2.8.0` (sidecar: 2.11.0);
  GPT-SoVITS pins `numpy<2.0` and `transformers<=4.50`; OpenVoice pins `numpy==1.22.0`.
- The sidecar already needed `pip install --no-deps`: mlx-audio wants `transformers>=5`, qwen-tts
  pins `transformers==4.57.3`.
- Per-engine venvs could not import the backend runner from the frozen PyInstaller binary
  (`sys._MEIPASS`); the April spec review (kept only in the principal's untracked `docs/plans`)
  called this an implementation blocker.
- The principal (2026-10-22): the attempt was rushed and the exact failure is not recalled. Qwen
  stayed on PyTorch throughout; MLX Qwen was never shipped.

## What carries forward
New engines follow [engine admission](../standards/engine-admission.md): one shipped runtime, no
conflicting pins, added as data where the runtime already supports the model.
