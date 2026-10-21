"""Severity order and the confidence floor.

Confidence is never raised because several reviewers agree: they share one model family, so
agreement is weak evidence.
"""

from __future__ import annotations

from review_core.contracts.models import SEVERITIES

DEFAULT_FLOOR = 50


def severity_rank(severity: str) -> int:
    """Position of a severity, 0 for the worst (P0)."""
    return SEVERITIES.index(severity)


def passes_floor(finding: dict, floor: int) -> bool:
    """True when the finding's confidence is at least the floor."""
    return finding["confidence"] >= floor
