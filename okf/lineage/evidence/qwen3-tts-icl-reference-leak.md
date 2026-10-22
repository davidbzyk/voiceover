---
id: lineage/evidence/qwen3-tts-icl-reference-leak
schema: okf/schemas/v1/lineage.json
type: Lineage
title: Qwen3-TTS in-context cloning leaks the reference's last words
description: Qwen3-TTS ICL voice cloning can open its output with the tail of the reference transcript; measured on VoiceOver profiles 2026-10-22.
domain: voice-models
tags:
  - lineage
  - evidence
  - qwen3-tts
freshness: "2026-10-22T18:36:00Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 1
source_root: .notes/research/
trial_matrix:
  full_clip_t2: leaked 2 of 2
  trimmed_29s_t2: leaked
  cut_25_0s_midword: leaked "God"
  cut_25_7s_sentence_end: clean 3 of 3
  djt_biden_profiles: clean
  cosyvoice_vc_same_refs: clean 4 of 4
key_findings:
  - The trigger is how the reference ends, not trailing noise; a reference ending on a finished sentence did not leak.
  - Upstream QwenLM/Qwen3-TTS issue 341 is open with no fix; greedy decoding and repetition_penalty did not help.
  - faster-qwen3-tts appends 0.5 s of silence to the reference because ICL prefill ends on the reference's last codec token.
  - In replacement mode Qwen runs once per segment, so one leaky profile can hit every segment.
sources:
  - id: upstream-341
    resource: https://github.com/QwenLM/Qwen3-TTS/issues/341
    type: url
  - id: faster-qwen3-tts
    resource: https://github.com/andimarafioti/faster-qwen3-tts
    type: url
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
  superseded_by: null
  part_of: lineage/evidence
---

# Qwen3-TTS in-context cloning leaks the reference's last words

## Synthesis
In ICL mode (`create_voice_clone_prompt(ref_audio, ref_text)` then `generate_voice_clone`),
generated speech sometimes opens with the reference's final words ("Yes, Mike. Bye. Hello...").
Trials on 2026-10-22 point at the reference ending: clips cut on a finished sentence were clean,
mid-word cuts leaked. CosyVoice3 speech-to-speech with the same references did not leak.

## Open
The fix belongs where the voice prompt is built (`tts.create_voice_prompt`) so preview and
replacement share it; candidates under test are a 0.5 s silence pad, sentence-end trimming and
x-vector-only mode.
