---
id: tombstones/example-tombstone
schema: okf/schemas/v1/tombstone.json
type: Tombstone
title: Tombstone — Example Deprecated Asset
description: Deprecation record and tribal knowledge preservation for obsolete asset.
domain: governance
tags:
  - tombstone
  - deprecated
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: tombstone
kcc_action: kill
killed_at: "2026-08-29T15:00:00Z"
killed_by: human:dave
tombstone_reason: Asset was temporary and has been superseded by canonical documentation.
prior_path: docs/example-obsolete.md
superseded_by: standards/example-standard
sources:
  - id: legacy-doc
    resource: docs/example-obsolete.md
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
  superseded_by: standards/example-standard
  part_of: tombstones
---

# Tombstone — Example Deprecated Asset

## Rationale
Explanation of deprecation and pointer to surviving canonical entities.
