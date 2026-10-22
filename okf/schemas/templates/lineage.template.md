---
id: lineage/evidence/example-lineage
schema: okf/schemas/v1/lineage.json
type: Lineage
title: Example Lineage & Evidence Summary
description: Condensed distillation of high-volume trial logs and raw execution data.
domain: evaluations
tags:
  - lineage
  - evidence
  - summary
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
kcc_action: condense
source_file_count: 10
source_root: docs/evidence/example/
trial_matrix:
  baseline: Baseline trial run
key_findings:
  - Key finding synthesized from raw evidence.
sources:
  - id: raw-evidence
    resource: docs/evidence/example/
    type: local_dir
generated:
  by: process:kcc-condenser
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
  part_of: lineage/evidence
---

# Example Lineage & Evidence Summary

## Synthesis
Summary analysis and empirical findings from condensed source files.
