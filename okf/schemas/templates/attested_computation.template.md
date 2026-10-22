---
id: standards/example-attested-computation
schema: okf/schemas/v1/attested_computation.json
type: Attested Computation
title: Example Attested Computation Specification
description: Deterministic verification harness and attestation contract.
domain: governance
tags:
  - attestation
  - verification
  - test-automation
freshness: "2026-08-29T15:00:00Z"
version: 1.0.0
status: stable
runtime: python3
parameters:
  - name: bundle_root
    type: string
    required: true
    default: okf
executor:
  resource: scripts/verify_okf.py
receipt:
  - exit_code
  - total_files_scanned
  - total_errors
attester:
  resource: scripts/verify_okf.py
sources:
  - id: verify-script
    resource: scripts/verify_okf.py
    type: local_script
generated:
  by: human:dave
  at: "2026-08-29T15:00:00Z"
verified:
  - by: process:ci-gate
    at: "2026-08-29T15:30:00Z"
relations:
  depends_on: []
  relates_to: []
  implements: []
  supersedes: []
  superseded_by: null
  part_of: standards
---

# Example Attested Computation Specification

## Verification Harness
Specification of parameters, execution contracts, and receipt validation.
