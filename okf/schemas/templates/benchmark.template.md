---
id: domains/evaluations/example-benchmark
schema: okf/schemas/v1/benchmark.json
type: Benchmark
title: Example Benchmark Defect Ledger
description: Defect ledger, rubric evaluation criteria, and upstream mitigations.
domain: evaluations
tags:
  - benchmark
  - defects
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
benchmark_family: SWE-Bench
upstream_repositories:
  - princeton-nlp/SWE-bench
defect_classes:
  - Rubric Criterion Collisions
active_mitigations: []
sources:
  - id: legacy-defects
    resource: docs/upstream-benchmark-defects.md
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

# Example Benchmark Defect Ledger

## Defect Summary
Overview of tracked benchmark defects.
