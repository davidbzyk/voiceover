---
id: standards/example-standard
schema: okf/schemas/v1/standard.json
type: Standard
title: Example Standard Title
description: Clear, single-sentence summary of the engineering standard.
domain: governance
tags:
  - standard
  - protocol
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
standard_scope: repository-wide
conformance_level: mandatory
governance_body: core-engineering
enforcement: automated-ci
sources:
  - id: legacy-doc
    resource: docs/specs/example-standard.md
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
  part_of: standards
---

# Example Standard Title

## Scope
Standard requirements and specifications.
