---
id: architecture/voice-replacement
schema: okf/schemas/v1/architecture.json
type: Architecture
title: How Replace Voice picks and runs an engine
description: The path from the engine picker to the sidecar job that replaces a recording's voice, and what a new engine costs.
domain: voice-models
tags:
  - architecture
  - voice-models
  - sidecar
freshness: "2026-10-27T18:00:00Z"
version: 1.0.0
status: stable
architecture_layer: runtime-execution
components:
  - name: Engine store
    path: src/lib/localVoice.svelte.ts
    role: Holds the local profiles and the sidecar's engine rows for every screen
  - name: EnginePicker
    path: src/lib/EnginePicker.svelte
    role: The engine dropdown on the home screen, Settings, the voice picker and Create Voice
  - name: Conversion contract
    path: src-tauri/src/conversion.rs
    role: Resolves the voice and engine, then runs ElevenLabs or the local engine
  - name: Replace route
    path: src-tauri/sidecar/server.py
    role: /voice-convert routes the job by the engine's registry category
interfaces:
  - name: MODEL_REGISTRY row
    specification: standards/engine-admission
decisions_ref: []
sources:
  - id: engine-picker-plan
    resource: https://claude.ai/artifact/XhCXNBfxnfSY6skp1uPo2r
    type: url
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-27T15:00:00Z"
verified: []
relations:
  depends_on:
    - domains/voice-models/engines
  relates_to:
    - standards/engine-admission
    - lineage/evidence/qwen3-tts-icl-reference-leak
    - lineage/evidence/tts-runaway-and-mlx-cache
  implements: []
  supersedes: []
  superseded_by: null
  part_of: architecture
---

# How Replace Voice picks and runs an engine

## Overview
A conversion is a `VoiceChoice`: an ElevenLabs voice, or a local voice profile plus an `engine`, which is a
`MODEL_REGISTRY` key. Nothing preselects an engine. A local conversion uses the choice's engine, else the
one saved as `local_engine` on the home screen, and otherwise asks the user to pick one
(`conversion::resolve_voice`). The Convert and Save buttons stay disabled until a local voice has an engine.

The sidecar's `/voice-convert` decides what the engine does from its registry row:

| Row category | What the job does |
| --- | --- |
| `voice-conversion` (CosyVoice3) | Converts the speech itself in 25 s chunks, keeping the speaker's pacing. Loads that row's repo. |
| `tts` (Qwen3-TTS and the five others) | Transcribes the recording with the chosen Whisper model, then speaks each phrase at its original timestamp (`_do_generate` with segments). Timing inside a phrase follows the engine. |

Either job is one entry in the sidecar's serial queue, so transcription waits its turn, shows as status
`transcribing`, and is cancelled like the rest. The app's progress label follows the job's status
(Loading, Transcribing, Converting voice) and its chunk counts. A job fails only when it stops reporting
new chunks for the stall window (`local_tts::STALL_AFTER_SECS`), never on total length.

## Bounds on each phrase and on memory
A text-to-speech engine samples one token at a time and stops when it samples an end token, so a phrase
can run on. Each phrase gets a budget of `SPEECH_BUDGET_RATIO` times its spoken length plus
`SPEECH_BUDGET_PAD_S`, passed as the engine's `max_tokens` through the row's `tokens_per_second`. A
phrase that reaches the budget is spoken again with a new seed (status `retrying`), and a second run to
the budget fails the job naming the engine. Engines that take a target length get the phrase's spoken
length, which leaves out the pauses `pad_audio_to_match_timing` puts back
(`chunked_tts.reinserted_gap_seconds`), so the padded phrase still fits its slot. MLX keeps at most
`tts.MLX_CACHE_LIMIT_BYTES` of freed buffers for reuse, set when the sidecar starts.
[Runaway evidence](../lineage/evidence/tts-runaway-and-mlx-cache.md).

## Where the engine list comes from
Every picker reads one store (`localVoice.svelte.ts`), filled from `/models/status`, so a download or a
pick on one screen shows on the others. The store replaced three separate profile loaders; the status bar
used to read its profile once at mount, before the config had loaded, and showed "No profile". Engines that
are not downloaded stay in the list, greyed. Each registry row's `license`, `size_gb` and `non_commercial`
fields fill the Models cards.

## Results
`meta.json` records `engine` (the key) and `engineName` (the display name, "ElevenLabs" for ElevenLabs).
Preview, Convert again and the Library card show "voice · engine". Recordings made before 2026-10-27 have
no engine recorded and show none.

## What a new engine costs
One `MODEL_REGISTRY` row with `category`, `license`, `size_gb`, `tokens_per_second` for a
text-to-speech engine and, when they apply, `non_commercial` and `length_hint`
([engine admission](../standards/engine-admission.md)). The pickers, the Models card, the replace route and
the saved metadata all come from the registry, so no app file changes.
