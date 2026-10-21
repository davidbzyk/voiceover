"""Merge findings that point at the same code.

Two findings are duplicates when they share a file and side and their line ranges overlap or
lie within `window` lines. Groups are anchored on their first member, so a long run of close
findings never chains into one group. A finding that claims more than MAX_SPAN lines stands
alone: otherwise one reviewer could claim a whole file and absorb everyone else's findings.
"""

from __future__ import annotations

from review_core.aggregator.confidence import severity_rank
from review_core.contracts.models import MAX_SPAN
from review_core.envelope import MERGE_WINDOW


def _preference(finding: dict) -> tuple:
    """Sort key that puts the finding to keep first: severity, confidence, line, reviewer."""
    return (
        severity_rank(finding["severity"]),
        -finding["confidence"],
        finding["line_start"],
        finding["reviewer"],
    )


def _groups(findings: list[dict], window: int) -> list[list[dict]]:
    """Split findings into duplicate groups."""
    by_place: dict[tuple[str, str], list[dict]] = {}
    for finding in findings:
        by_place.setdefault((finding["file"], finding["side"]), []).append(finding)
    groups = []
    for place in sorted(by_place):
        ordered = sorted(by_place[place], key=lambda x: (x["line_start"], x["line_end"]))
        open_group: list[dict] | None = None
        for finding in ordered:
            if _too_wide(finding):
                groups.append([finding])
            elif open_group and finding["line_start"] <= open_group[0]["line_end"] + window:
                open_group.append(finding)
            else:
                open_group = [finding]
                groups.append(open_group)
    return groups


def _too_wide(finding: dict) -> bool:
    """True when the finding claims more lines than any single place holds."""
    return finding["line_end"] - finding["line_start"] + 1 > MAX_SPAN


def dedup(findings: list[dict], window: int = MERGE_WINDOW) -> tuple[list[dict], list[dict]]:
    """Return (kept, removed). Each kept finding lists the other reviewers of its group."""
    kept, removed = [], []
    for group in _groups(findings, window):
        winner = min(group, key=_preference)
        others = sorted({x["reviewer"] for x in group if x is not winner} - {winner["reviewer"]})
        kept.append({**winner, "also_raised_by": others})
        removed.extend(x for x in group if x is not winner)
    return kept, removed
