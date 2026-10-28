"""Read the validator's verdicts and apply them.

validation.json is `{"verdicts": [{"id", "verdict": "upheld" | "declined", "reason"}]}`, where
`id` is copied from validator-input.json.
It is written by an agent, so any deviation from that shape counts as a validator failure, and
a verdict only ever acts on a finding the validator was actually given.
"""

from __future__ import annotations

import json
from pathlib import Path

from review_core.contracts.models import ContractError, read_json
from review_core.envelope import MAX_REVIEWER_FILE_BYTES

VERDICTS = ("upheld", "declined")
# Only these severities are sent to the validator, so only these can be declined.
VALIDATED_SEVERITIES = ("P0", "P1")
# The sub-agent that writes validation.json must run under this name.
VALIDATOR = "validator"


def plain_file(path: Path) -> bool:
    """True for a regular file of reasonable size; a link or a huge file is not read."""
    return (
        path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_REVIEWER_FILE_BYTES
    )


def verdict_id(finding: dict) -> str:
    """The name a verdict uses for a finding: its fingerprint, its lines and its reviewer.

    The fingerprint alone is not enough: the same line quoted at two places in a file gives two
    findings one fingerprint, and two reviewers can report two problems on the same lines.
    """
    # Review (pre-push), shown not to occur: one reviewer's two findings on one quote and lines
    # would share an id, and none of 545 findings in 50 real trials did.
    lines = f"{finding['line_start']}-{finding['line_end']}"
    return f"{finding['fingerprint']}:{lines}:{finding['reviewer']}"


def read_verdicts(path: Path | str) -> dict[str, dict] | None:
    """Return id -> verdict row, or None when the file is missing or malformed.

    If an id appears twice, the later row wins.
    """
    path = Path(path)
    if not plain_file(path):
        return None
    try:
        doc = read_json(path)
    except ContractError:
        return None
    if (
        not isinstance(doc, dict)
        or set(doc) != {"verdicts"}
        or not isinstance(doc["verdicts"], list)
    ):
        return None
    rows: dict[str, dict] = {}
    for row in doc["verdicts"]:
        if not isinstance(row, dict) or set(row) != {"id", "verdict", "reason"}:
            return None
        if not all(isinstance(row[k], str) for k in row) or row["verdict"] not in VERDICTS:
            return None
        rows[row["id"]] = row
    return rows


def _row(finding: dict, verdicts: dict[str, dict]) -> dict | None:
    """The verdict for a finding, or None when it was not sent to the validator or has none."""
    if finding["severity"] not in VALIDATED_SEVERITIES:
        return None
    return verdicts.get(verdict_id(finding))


def apply_verdicts(
    findings: list[dict], verdicts: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    """Return (kept, declined). A verdict acts only on the finding it names, and only on one
    the validator was given; anything else is ignored.

    Two findings share an id only when one reviewer reports the same lines twice. A decline that
    fits more than one finding removes none: a finding is not dropped on a verdict that might
    have been about another.
    """
    given = [verdict_id(x) for x in findings if x["severity"] in VALIDATED_SEVERITIES]
    shared = {i for i in given if given.count(i) > 1}
    kept, declined = [], []
    for finding in findings:
        row = _row(finding, verdicts)
        if row is not None and row["verdict"] == "declined" and row["id"] not in shared:
            declined.append(
                {
                    "id": verdict_id(finding),
                    "fingerprint": finding["fingerprint"],
                    "reviewer": finding["reviewer"],
                    "reason": row["reason"],
                }
            )
        else:
            kept.append(finding)
    return kept, declined


def unvalidated(findings: list[dict], verdicts: dict[str, dict]) -> int:
    """How many P0 or P1 findings carry no upheld verdict.

    A result that shows such a finding was not fully validated, whatever the reason: no verdict
    file, a broken one, a validator that skipped it, or a declined finding left in.
    """
    return sum(
        1
        for finding in findings
        if finding["severity"] in VALIDATED_SEVERITIES
        and (_row(finding, verdicts) or {}).get("verdict") != "upheld"
    )


def append_declined(path: Path | str, declined: list[dict]) -> None:
    """Append rows to declined.json (a JSON array), skipping ids already recorded."""
    path = Path(path)
    existing = []
    if plain_file(path):
        try:
            loaded = read_json(path)
        except ContractError:
            loaded = []
        existing = loaded if isinstance(loaded, list) else []
    seen = {row.get("id") for row in existing if isinstance(row, dict)}
    existing.extend(row for row in declined if row["id"] not in seen)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
