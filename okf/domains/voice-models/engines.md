---
id: domains/voice-models/engines
schema: okf/schemas/v1/domain.json
type: Domain
title: Voice engines in VoiceOver
description: Which engines create, preview and replace voices today, what runs them, and the rule for adding more.
domain: voice-models
tags:
  - domain
  - voice-models
freshness: "2026-10-22T18:36:00Z"
version: 1.0.0
status: stable
domain_code: VOICE
lead_owner: principal
bounded_context: VoiceEngines
subdomains:
  - voice-models
sources:
  - id: sidecar
    resource: src-tauri/sidecar/
    type: local_dir
  - id: restore-qwen-plan
    resource: https://claude.ai/artifact/KtH1sro38KtHDNyLX2YfpM
    type: url
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-22T18:36:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - standards/engine-admission
    - lineage/evidence/qwen3-tts-icl-reference-leak
    - lineage/evidence/whisper-reference-transcript-loop
    - tombstones/multi-model-backends-2026-04
  implements: []
  supersedes: []
  superseded_by: null
  part_of: domains/voice-models
---

# Voice engines in VoiceOver

## Context
The app ships with no models installed; the user installs an engine and picks it per conversion.

| Engine | Job | Runtime | Notes |
| --- | --- | --- | --- |
| Qwen3-TTS-12Hz-1.7B-Base (qwen_tts 0.1.1) | Create Voice preview; text re-speak replacement | PyTorch MPS | The principal's preferred engine. Replacement mode was removed in PR #23 and is being restored (2026-10-22). ICL leak: see evidence. |
| CosyVoice3 0.5B 8-bit | Speech-to-speech replacement | MLX (mlx-audio 0.4.2) | Keeps timing; no reference leak measured. |
| ElevenLabs eleven_multilingual_sts_v2 | Speech-to-speech replacement | Hosted API | Needs the user's API key. |
| Whisper large-v3-turbo | Transcribe the reference and the recording | MLX (mlx-audio) | Loop guard: see evidence. |

## Adding an engine
Follow [engine admission](../../standards/engine-admission.md). The 2026-10-22 Hugging Face scan of
candidates lives in `.notes/research/2026-10-22-hf-voice-models-scan.md` (principal's notes repo).
