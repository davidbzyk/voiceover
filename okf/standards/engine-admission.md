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
freshness: "2026-10-22T18:36:00Z"
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
1. An engine runs on a runtime the sidecar already ships: mlx-audio, or the existing torch stack.
2. Adding it changes no pinned version another engine relies on. A conflict is a no, not a venv.
3. Where the runtime already supports the model (mlx-audio's model list), the engine is a registry
   row, not new loader code.
4. The app ships with no models installed. The user installs one and picks it; nothing is preselected.

## Why
The April seven-backend sidecar died on exactly these conflicts; see the
[tombstone](../tombstones/multi-model-backends-2026-04.md).

## Status
Draft from the 2026-10-22 restore-Qwen plan; becomes stable when that plan's PR merges.
