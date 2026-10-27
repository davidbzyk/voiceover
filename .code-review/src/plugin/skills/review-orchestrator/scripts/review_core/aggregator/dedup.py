"""Group findings that point at the same code; no finding is dropped for its place.

Two findings share a place when they share a file and side and their line ranges overlap or
lie within `window` lines. Groups are anchored on their first member, so a long run of close
findings never chains into one group. A finding that claims more than MAX_SPAN lines stands
alone, so one reviewer claiming a whole file cannot gather everyone else's findings.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from review_core.contracts.models import MAX_SPAN
from review_core.envelope import MERGE_WINDOW

Place = tuple[str, str, int, int]


def _at(finding: dict) -> Place:
    """A finding document's file, side, first line and last line."""
    return finding["file"], finding["side"], finding["line_start"], finding["line_end"]


def place_groups(
    findings: Sequence[Any], window: int = MERGE_WINDOW, at: Callable[[Any], Place] = _at
) -> list[list[Any]]:
    """Split findings into groups at one place, in file, side and line order; `at` reads a
    finding's place, so CI groups its `Finding` objects by the same rule."""
    by_place: dict[tuple[str, str], list] = {}
    for finding in findings:
        by_place.setdefault(at(finding)[:2], []).append(finding)
    groups = []
    for place in sorted(by_place):
        ordered = sorted(by_place[place], key=lambda x: at(x)[2:])
        open_group: list | None = None
        for finding in ordered:
            if _too_wide(at(finding)):
                groups.append([finding])
            elif open_group and at(finding)[2] <= at(open_group[0])[3] + window:
                open_group.append(finding)
            else:
                open_group = [finding]
                groups.append(open_group)
    return groups


def _too_wide(place: Place) -> bool:
    """True when the finding claims more lines than any single place holds."""
    return place[3] - place[2] + 1 > MAX_SPAN


def group_by_place(findings: list[dict], window: int = MERGE_WINDOW) -> list[dict]:
    """Every finding, in the order given, each listing the other reviewers with a finding at its
    place; run again after verdicts so a declined finding's reviewer is no longer listed."""
    others: dict[int, list[str]] = {}
    for group in place_groups(findings, window):
        reviewers = {x["reviewer"] for x in group}
        others.update({id(x): sorted(reviewers - {x["reviewer"]}) for x in group})
    return [{**x, "also_raised_by": others[id(x)]} for x in findings]
