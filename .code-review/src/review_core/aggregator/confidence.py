"""The confidence floor.

Confidence is never raised because several reviewers agree: they share one model family, so
agreement is weak evidence.
"""

from __future__ import annotations

DEFAULT_FLOOR = 50


def passes_floor(finding: dict, floor: int) -> bool:
    """True when the finding's confidence is at least the floor."""
    return finding["confidence"] >= floor
