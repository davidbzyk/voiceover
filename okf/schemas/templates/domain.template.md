---
id: domains/evaluations/example-domain
schema: okf/schemas/v1/domain.json
type: Domain
title: Example Domain Overview
description: Overview of domain boundaries, context maps, and owned concepts.
domain: evaluations
tags:
  - domain
  - overview
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
domain_code: EVAL
lead_owner: team-evaluations
bounded_context: EvaluationsContext
subdomains:
  - evaluations/benchmarks
  - evaluations/datasets
sources:
  - id: legacy-domain-doc
    resource: docs/agents/domain.md
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
  part_of: domains
---

# Example Domain Overview

## Context
Domain description and boundary model.
