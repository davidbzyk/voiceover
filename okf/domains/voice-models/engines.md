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
freshness: "2026-10-25T22:35:00Z"
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
    - lineage/evidence/mlx-audio-058-engine-bench
    - lineage/evidence/cosyvoice-from-mlx-audio-plus
    - lineage/evidence/hf-cache-set-after-import
    - tombstones/multi-model-backends-2026-04
    - tombstones/qwen-pytorch-path-2026-10
  implements: []
  supersedes: []
  superseded_by: null
  part_of: domains/voice-models
---

# Voice engines in VoiceOver

## Context
The app ships with no models installed; the user downloads each model from the Models page. Every
local engine runs on MLX through mlx-audio 0.6.1 (mlx 0.32.4) in the sidecar, every MLX computation on
one thread; there is no PyTorch. Text-to-speech
engines are rows in `MODEL_REGISTRY` (`server.py`) and share one generate path (`tts.generate_speech`).

| Engine | Job | Runtime | Notes |
| --- | --- | --- | --- |
| Qwen3-TTS 1.7B Base (MLX bf16) | Create Voice preview; text-to-speech | mlx-audio | The principal's preferred engine. Clones from the speaker embedding only (no transcript), which stops the ICL leak. The PyTorch path it replaced: [tombstone](../../tombstones/qwen-pytorch-path-2026-10.md). |
| VoxCPM2, MOSS-TTS Local v1.5, Chatterbox | Text-to-speech | mlx-audio | Apache-2.0 / Apache-2.0 / MIT. No leak measured. |
| OmniVoice | Text-to-speech | mlx-audio | CC-BY-NC weights. Leaks the T2 reference transcript 3 of 24. |
| Fish S2 Pro | Text-to-speech | mlx-audio | Fish Audio Research licence (non-commercial). Slowest, RTF about 1.5. |
| CosyVoice3 0.5B 8-bit | Speech-to-speech replacement | `cosyvoice_mlx` (copied, on mlx-audio) | Keeps timing; see the fork evidence. |
| ElevenLabs eleven_multilingual_sts_v2 | Speech-to-speech replacement | Hosted API | Needs the user's API key. |
| Whisper large-v3-turbo / medium (`-asr` repos) | Transcribe the reference and the recording | mlx-audio | Loop guard: see evidence. |

## Adding an engine
Follow [engine admission](../../standards/engine-admission.md). The 2026-10-22 Hugging Face scan of
candidates lives in `.notes/research/2026-10-22-hf-voice-models-scan.md` (principal's notes repo).
