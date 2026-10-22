---
id: MIGRATION_LEDGER
schema: okf/schemas/v1/standard.json
type: Standard
title: Migration Ledger
description: Provenance ledger mapping every source document to its target concept in this bundle.
domain: governance
tags:
  - ledger
  - migration
  - provenance
freshness: "2026-10-22T18:35:58Z"
version: 0.1.0
status: draft
standard_scope: repository-wide
conformance_level: mandatory
governance_body: core-engineering
enforcement: automated-ci
generated:
  by: process:okf_init
  at: "2026-10-22T18:35:41Z"
relations:
  depends_on: []
  relates_to: []
---

# Migration Ledger

## Statistics

- **Sources accounted for**: `2`
- **Coverage**: `100.0%`
- **keep-verbatim**: `2`

## Ledger Table

| Source Path | Action | Target | Entity ID | Notes |
|:---|:---|:---|:---|:---|
| `BUILD.md` | keep-verbatim | `BUILD.md` | `BUILD` | keep-verbatim from `docs` |
| `plans/2026-03-31-001-feat-timestamp-synced-tts-plan.md` | keep-verbatim | `plans/2026-03-31-001-feat-timestamp-synced-tts-plan.md` | `plans/2026-03-31-001-feat-timestamp-synced-tts-plan` | keep-verbatim from `docs` |
