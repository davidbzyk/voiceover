---
id: standards/engine-admission
schema: okf/schemas/v1/standard.json
type: Standard
title: Voice engine admission
description: A voice engine joins the sidecar only if it runs on a runtime the app already ships, with no conflicting dependency pins.
domain: voice-models
tags:
  - standard
  - sidecar
  - dependencies
freshness: "2026-10-25T15:40:42Z"
version: 0.1.0
status: draft
standard_scope: src-tauri/sidecar
conformance_level: mandatory
governance_body: principal
enforcement: manual-review
sources:
  - id: multi-model-tombstone
    resource: okf/tombstones/multi-model-backends-2026-04.md
    type: local_doc
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
    - domains/voice-models/engines
  implements: []
  supersedes:
    - tombstones/multi-model-backends-2026-04
  superseded_by: null
  part_of: standards
---

# Voice engine admission

## Rule
1. An engine runs on the runtime the sidecar ships: mlx-audio. Model code mlx-audio lacks is copied
   into its own package beside the sidecar (as `cosyvoice_mlx`), never installed over mlx-audio.
2. Adding it changes no pinned version another engine relies on. A conflict is a no, not a venv.
3. Where the runtime already supports the model (mlx-audio's model list), the engine is a registry
   row, not new loader code. A text-to-speech row names its repo, licence, and whether the
   engine gets the sample's transcript (`ref_text`). Every row names the other repos its engine
   fetches by itself (`extra_repos`), found by generating once with `HF_HUB_OFFLINE=1` and only the
   row's repos in the models folder; an engine that fails that run is missing one.
4. The app ships with no models installed; the user downloads models from the Models page. When per-conversion model choice lands, nothing is preselected.
5. Every package the sidecar imports is pinned in `requirements.txt` (`test_requirements.py` checks the
   sidecar's modules and `cosyvoice_mlx`). The build venv adds only tools the
   binary never imports, each at the version the build docs pin: PyInstaller to build, pytest and httpx
   to run the sidecar tests.

## Why
The April seven-backend sidecar died on exactly these conflicts; see the
[tombstone](../tombstones/multi-model-backends-2026-04.md). Rule 5 comes from CosyVoice running for
months on a fork nobody had listed; see the
[fork evidence](../lineage/evidence/cosyvoice-from-mlx-audio-plus.md).

## Status
Draft from the 2026-10-22 restore-Qwen plan; becomes stable when that plan's PR merges.
