---
id: lineage/evidence/hf-cache-set-after-import
schema: okf/schemas/v1/lineage.json
type: Lineage
title: Models loaded from ~/.cache/huggingface, not the app's models folder
description: The sidecar set HF_HUB_CACHE after transformers had imported huggingface_hub, so every bare-repo model load used the default cache; found and fixed 2026-10-23.
domain: sidecar
tags:
  - lineage
  - evidence
  - huggingface
freshness: "2026-10-23T23:36:54Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 1
source_root: src-tauri/sidecar/
trial_matrix:
  env_set_after_import_old_stack: constants.HF_HUB_CACHE stayed ~/.cache/huggingface/hub
  env_set_after_import_new_stack: same
  frozen_binary_before_fix: Whisper loaded in 1 s while /models/status said nothing was downloaded
  env_set_before_import: test_engines.py::test_models_land_in_the_data_dir_not_the_default_hf_cache
key_findings:
  - huggingface_hub fixes HF_HUB_CACHE when first imported; server.py imported transformers at the top (for a qwen-tts patch) and set the variable later in main().
  - The Models page downloads with an explicit cache_dir, so it filled the app's folder while generation loaded, or silently downloaded, a second copy under ~/.cache/huggingface.
  - Some engines fetch a second repo inside generate (MOSS-TTS Local pulls OpenMOSS-Team/MOSS-Audio-Tokenizer-v2), which only an import-time setting can catch.
  - server.py now sets HF_HUB_CACHE from --data-dir before any heavy import.
sources:
  - id: server
    resource: src-tauri/sidecar/server.py
    type: local_doc
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-23T23:30:00Z"
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

# Models loaded from ~/.cache/huggingface, not the app's models folder

## Synthesis
Setting an environment variable inside `main()` looked right and did nothing: by then the hub had
read it. The fix moves the assignment above every import that can load the hub, and a test runs the
import in a clean interpreter to hold it there.

## Repos an engine fetches by itself
With the cache fixed, those downloads land in the models folder too, which exposed them: three engines
fetch a second repo the Models page did not know about. Generating each engine once with
`HF_HUB_OFFLINE=1` and only its row's repo present named them (2026-10-23): MOSS-TTS Local fetches
`OpenMOSS-Team/MOSS-Audio-Tokenizer-v2` (8.5 GB, in `generate`), Chatterbox `mlx-community/S3TokenizerV2`
(0.5 GB, at load) and CosyVoice3 `mlx-community/S3TokenizerV3` (1.0 GB, with its tokenizers). A row lists
them as `extra_repos`, which the Models page downloads, counts as part of "downloaded" and deletes with
the row. The CosyVoice3 row does; the MOSS-TTS Local and Chatterbox rows must when those engines are added.
