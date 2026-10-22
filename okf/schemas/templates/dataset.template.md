---
id: domains/evaluations/example-dataset
schema: okf/schemas/v1/dataset.json
type: Dataset
title: Example Dataset Catalog
description: Overview and manifest metadata for dataset assets.
domain: evaluations
tags:
  - datasets
  - catalog
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
dataset_count: 1
total_size_bytes: 1048576
tier_breakdown:
  tier_1_count: 1
  tier_2_count: 0
  tier_3_count: 0
transport_protocols:
  - git-lfs
storage_root: data/
manifest_path: datasets.tsv
sources:
  - id: legacy-survey
    resource: docs/dataset-survey.md
    type: local_doc
generated:
  by: human:dave
  at: "2026-08-29T15:00:00Z"
verified:
  - by: process:scripts/verify_okf.py
    at: "2026-08-29T15:30:00Z"
relations:
  depends_on: []
  relates_to: []
  implements: []
  supersedes: []
  superseded_by: null
  part_of: domains/evaluations
---

# Example Dataset Catalog

## Dataset Manifest
Dataset summary details.
