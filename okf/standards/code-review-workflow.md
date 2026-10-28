---
id: standards/code-review-workflow
schema: okf/schemas/v1/standard.json
type: Standard
title: Code review workflow runs
description: Which pull request events start, skip or replace a code review run, so an edit never cancels one.
domain: infrastructure
tags:
  - standard
  - ci
  - code-review
freshness: "2026-10-28T20:55:00Z"
version: 1.0.0
status: stable
standard_scope: infrastructure
conformance_level: mandatory
governance_body: principal
enforcement: manual-review
sources:
  - id: workflow
    resource: .github/workflows/code-review.yml
    type: local_doc
generated:
  by: claude-code/claude-opus-5-5
  at: "2026-10-28T20:55:00Z"
verified: []
relations:
  depends_on: []
  relates_to: []
  implements: []
  supersedes: []
  superseded_by: null
  part_of: standards
---

# Code review workflow runs

`.github/workflows/code-review.yml` reviews a pull request on `opened`, `synchronize`,
`reopened` and `ready_for_review`, and on `edited` only when the base branch changed.
Drafts, forks and Dependabot pull requests are skipped.

## Concurrency
- A push or a base change shares the group `code-review-<number>` with
  `cancel-in-progress`, so it replaces the stale run for the old head.
- A title or body edit gets its own group, `code-review-<number>-edit-<run id>`. The job
  then skips it, so the edit can no longer cancel a review that is still running.

Before this fix (PR #37, 2026-10-28), an `edited` event joined the pull request's group and
cancelled the running review for the head just pushed (seen on PR #30, 2026-10-22), and the
run had to be restarted with `gh run rerun`.

## Model
The review runs `gpt-6-luna` at Codex effort `max` unless the repository variables
`CODE_REVIEW_MODEL` or `CODE_REVIEW_EFFORT` say otherwise.
