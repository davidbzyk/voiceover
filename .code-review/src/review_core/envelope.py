"""Build a run envelope from the per-reviewer findings files an output folder holds.

Standard library only: the aggregator script reuses this inside containers. A reviewer that
never wrote its file shows as not_run, never as empty.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path

from review_core.contracts.models import (
    DROP_REASONS,
    SCHEMA_VERSION,
    SUCCESS_OUTCOMES,
    ContractError,
    FindingsDoc,
    quote_lines,
    read_json,
    safe_relpath,
    salvage_findings,
)

# A reviewer file is written by an agent that read untrusted code, so it is read defensively.
MAX_REVIEWER_FILE_BYTES = 5_000_000
# No reviewer has this many real findings on one change; more is a flood, not a review.
MAX_FINDINGS_PER_REVIEWER = 500
# Findings in the same file and side count as one report when the later one starts no more than
# this many lines after the earlier one ends: 0 means their line ranges share a line. A wider
# window merged distinct defects a few lines apart, and bought almost nothing on tuning runs.
MERGE_WINDOW = 0

DROP_COUNTS = DROP_REASONS


def reviewer_file(out_dir: Path | str, reviewer: str) -> Path:
    """Path of one reviewer's findings file."""
    return Path(out_dir) / f"findings.{reviewer}.json"


def too_many_findings(raw, limit: int) -> bool:
    """True when a parsed document lists more findings than the limit; checked before validating."""
    findings = raw.get("findings") if isinstance(raw, dict) else None
    return isinstance(findings, list) and len(findings) > limit


def read_reviewer(
    out_dir: Path | str, reviewer: str, ran: set[str] | None = None
) -> tuple[str, FindingsDoc | None, int]:
    """Return the reviewer's outcome, its sound findings if any, and how many were dropped.

    Outcomes: ok, empty, not_run, malformed, or spawn_declined when `ran` is given and the
    reviewer is not in it, meaning the file exists but no sub-agent of that name ran. A file
    whose findings are all unusable is malformed; one with some sound findings is ok, and the
    rest are counted. The file speaks for one reviewer only.
    """
    path = reviewer_file(out_dir, reviewer)
    if not path.exists() and not path.is_symlink():
        return "not_run", None, 0
    if ran is not None and reviewer not in ran:
        return "spawn_declined", None, 0
    # A link could point anywhere on disk, and a huge file is not a findings list.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REVIEWER_FILE_BYTES:
        return "malformed", None, 0
    try:
        raw = read_json(path)
        if too_many_findings(raw, MAX_FINDINGS_PER_REVIEWER):
            return "malformed", None, 0
        doc, bad = salvage_findings(raw, reviewer)
    except ContractError:
        return "malformed", None, 0
    if bad and not doc.findings:
        return "malformed", None, bad
    return ("ok" if doc.findings else "empty"), doc, bad


def fingerprint(finding: dict) -> str:
    """sha256 of the normalised path, the side and the quoted lines with indentation removed.

    Nothing a model words freely and no line number goes in, so the same quoted code gives the
    same fingerprint whoever raises it and however a later push moves it. Two places that quote
    identical lines share a fingerprint; callers that need identity add the line range.
    """
    path = safe_relpath(finding["file"]) or finding["file"]
    parts = [path, finding["side"], *quote_lines(finding["quote"])]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def collect_findings(
    out_dir: Path | str, planned: list[str], ran: set[str] | None = None
) -> tuple[list[dict], list[str]]:
    """Concatenate every reviewer's sound findings, fingerprints filled.

    Also returns the reviewer's name once for each of its findings dropped as malformed.
    """
    merged = []
    dropped: list[str] = []
    for reviewer in planned:
        _, doc, bad = read_reviewer(out_dir, reviewer, ran)
        dropped += [reviewer] * bad
        for finding in doc.findings if doc else ():
            item = asdict(finding)
            item["fingerprint"] = fingerprint(item)
            item["also_raised_by"] = []
            merged.append(item)
    return merged, dropped


def run_status(outcomes: list[str]) -> str:
    """failed when no reviewer succeeded, complete when all did, otherwise partial."""
    good = [o in SUCCESS_OUTCOMES for o in outcomes]
    if not any(good):
        return "failed"
    return "complete" if all(good) else "partial"


def build_envelope(
    out_dir: Path | str, planned: list[str], run_meta: dict, ran: set[str] | None = None
) -> dict:
    """Return a run document with an empty findings list.

    run_meta carries runner, model, effort, cli_version and sandbox_mode. `ran`, when known,
    is the set of reviewers whose sub-agent actually ran.
    """
    rows = []
    for reviewer in planned:
        outcome, doc, _ = read_reviewer(out_dir, reviewer, ran)
        count = len(doc.findings) if doc else 0
        rows.append(
            {"reviewer": reviewer, "outcome": outcome, "retries": 0, "findings_count": count}
        )
    envelope = {
        "status": run_status([r["outcome"] for r in rows]),
        "reviewers_planned": list(planned),
        "reviewers": rows,
        "runner": run_meta["runner"],
        "model": run_meta["model"],
        "effort": run_meta["effort"],
        "cli_version": run_meta["cli_version"],
        "sandbox_mode": run_meta["sandbox_mode"],
        "dropped": dict.fromkeys(DROP_COUNTS, 0),
    }
    return {"schema_version": SCHEMA_VERSION, "envelope": envelope, "findings": []}
