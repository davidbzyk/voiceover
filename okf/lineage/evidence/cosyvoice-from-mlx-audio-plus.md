---
id: lineage/evidence/cosyvoice-from-mlx-audio-plus
schema: okf/schemas/v1/lineage.json
type: Lineage
title: CosyVoice came from an undeclared fork; the sidecar now carries its code
description: Replace Voice ran on mlx-audio-plus 0.1.8 installed by hand over mlx-audio 0.4.2; its CosyVoice3 code now lives in src-tauri/sidecar/cosyvoice_mlx on mlx-audio 0.5.8.
domain: voice-models
tags:
  - lineage
  - evidence
  - cosyvoice
  - dependencies
freshness: "2026-10-25T15:21:22Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 1
source_root: src-tauri/sidecar/cosyvoice_mlx/
trial_matrix:
  mlx_audio_0_4_2_to_0_6_1_wheels: no cosyvoice3 module in any release
  sidecar_venv: mlx-audio 0.4.2 plus mlx-audio-plus 0.1.8 over it, 506 files overlapping
  copied_package_on_0_5_8: 20 s clip in, 20.0 s out, warm 1.6 s (fork build 1.6 s)
  sidecar_end_to_end: 30 s source, 29.99 s out, 2 chunks
key_findings:
  - requirements.txt never listed mlx-audio-plus, so a build from it had no Replace Voice; the shipped binary worked only because of the hand-built .sidecar-venv.
  - mlx-audio-plus pins transformers<5 (still on its main branch) and mlx-audio 0.5.8 needs >=5.14, so the fork and the upgrade cannot share one environment.
  - The copied package changes only import paths (mlx_lm to mlx_audio.lm, the codec modules to cosyvoice_mlx) and adds loader.py; it needs librosa, which the old binary already bundled.
  - CosyVoice transcribes its reference only when no source_audio is given, so voice conversion never used the stt_model the sidecar named.
sources:
  - id: mlx-audio-plus
    resource: https://github.com/DePasqualeOrg/mlx-audio-plus
    type: url
  - id: package
    resource: src-tauri/sidecar/cosyvoice_mlx/
    type: local_dir
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-23T22:50:00Z"
verified: []
relations:
  depends_on: []
  relates_to:
    - domains/voice-models/engines
    - standards/engine-admission
    - tombstones/multi-model-backends-2026-04
  implements: []
  supersedes: []
  superseded_by: null
  part_of: lineage/evidence
---

# CosyVoice came from an undeclared fork; the sidecar now carries its code

## Synthesis
No mlx-audio release has CosyVoice. The sidecar loaded it from `mlx-audio-plus` 0.1.8, which
installs into the same `mlx_audio` package and overwrites 506 of its files. Upgrading mlx-audio for
the new engines would have broken it, the same clash that killed the April multi-backend sidecar.
Copying only the CosyVoice code (MIT, from the 0.1.8 wheel) into its own package keeps one
runtime: it imports mlx-audio's shared pieces and replaces nothing.
`scripts/check-cosyvoice-copy.sh` re-derives the copy from the wheel (fetched by its PyPI digest, the
same import edits applied) and diffs; it prints nothing and exits 0 while the copy is unchanged.

## Open
Upkeep: the copy does not follow the fork. The fork's main branch has CosyVoice3 alignment work from
2026-04-10 that 0.1.8 lacks; pulling it in is a separate measured change.
