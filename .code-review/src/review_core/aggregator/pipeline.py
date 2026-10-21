"""The two aggregator passes: gate and merge, then fold in the validator's verdicts."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from review_core.aggregator.confidence import DEFAULT_FLOOR, passes_floor
from review_core.aggregator.dedup import dedup
from review_core.aggregator.gates import (
    GitReader,
    Reader,
    apply_path_and_quote_gates,
    ref_exists,
)
from review_core.aggregator.validate import (
    VALIDATED_SEVERITIES,
    append_declined,
    apply_verdicts,
    plain_file,
    read_verdicts,
    unvalidated,
    verdict_id,
)
from review_core.contracts.models import (
    REVIEWERS,
    ContractError,
    load_final_findings,
    load_run_envelope,
    read_json,
)
from review_core.envelope import DROP_COUNTS, MERGE_WINDOW, build_envelope, collect_findings

VALIDATOR_FIELDS = (
    "fingerprint", "file", "side", "line_start", "line_end", "quote", "title", "description",
    "severity",
)  # fmt: skip


def _write(path: Path, doc) -> None:
    """Write a JSON document with a trailing newline."""
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def gate_and_merge(
    collected: tuple[list[dict], list[str]],
    reader: Reader,
    floor: int = DEFAULT_FLOOR,
    window: int = MERGE_WINDOW,
) -> tuple[list[dict], dict, list[dict]]:
    """Apply the path gate, the quote gate, the confidence floor and the merge.

    `collected` is what `collect_findings` returns: the sound findings, and one reviewer name
    per finding already dropped as malformed. Returns the merged findings in a fixed order,
    the count of drops by reason, and one row per dropped finding. Pure: it reads code and
    writes nothing.
    """
    findings, malformed = collected
    dropped = dict.fromkeys(DROP_COUNTS, 0)
    dropped["malformed"] = len(malformed)
    # A malformed finding has no usable place or quote, so its row carries no fingerprint.
    detail: list[dict] = [
        {"fingerprint": None, "reviewer": name, "reason": "malformed"} for name in malformed
    ]

    def drop(items: list[dict], reason: str) -> None:
        """Count each item under the reason and keep a row for the report."""
        for item in items:
            dropped[reason] += 1
            detail.append(
                {"fingerprint": item["fingerprint"], "reviewer": item["reviewer"], "reason": reason}
            )

    kept, gated = apply_path_and_quote_gates(findings, reader)
    for reason in ("out_of_snapshot", "quote_gate"):
        drop([x for x in gated if x["reason"] == reason], reason)
    strong = [x for x in kept if passes_floor(x, floor)]
    drop([x for x in kept if not passes_floor(x, floor)], "confidence_floor")
    merged, removed = dedup(strong, window)
    drop(removed, "duplicate")
    merged.sort(key=lambda x: (x["file"], x["line_start"], x["side"], x["reviewer"]))
    return merged, dropped, detail


def validator_input(merged: list[dict]) -> dict:
    """What the validator is handed: the merged findings severe enough to need a verdict."""
    to_check = [x for x in merged if x["severity"] in VALIDATED_SEVERITIES]
    return {
        "findings": [{"id": verdict_id(x), **{k: x[k] for k in VALIDATOR_FIELDS}} for x in to_check]
    }


def _check_inputs(out: Path, repo: Path | str, base: str, head: str) -> None:
    """Raise ContractError when the output folder, the repository or a ref is unusable."""
    if not out.is_dir():
        raise ContractError(f"output folder {out} does not exist")
    if not Path(repo).is_dir():
        raise ContractError(f"repository {repo} does not exist")
    for ref in (base, head):
        if not ref_exists(repo, ref):
            raise ContractError(f"ref {ref} is not a commit in {repo}")


def first_pass(
    out_dir: Path | str,
    repo: Path | str,
    base: str,
    head: str,
    floor: int = DEFAULT_FLOOR,
    window: int = MERGE_WINDOW,
) -> dict:
    """Gate, filter and dedup the findings; write candidates.json and validator-input.json.

    Raises ContractError when the output folder, repository or a ref is unusable.
    """
    out = Path(out_dir)
    _check_inputs(out, repo, base, head)
    merged, dropped, detail = gate_and_merge(
        collect_findings(out, list(REVIEWERS)), GitReader(repo, base, head), floor, window
    )
    candidates = {"findings": merged, "dropped": dropped, "dropped_detail": detail}
    _write(out / "candidates.json", candidates)
    _write(out / "validator-input.json", validator_input(merged))
    return candidates


def _settle(run: dict, dropped: dict, unchecked) -> None:
    """Record the drop counts; a run that would be complete is partial when a strong finding
    went unchecked or any finding was thrown away for its form.

    The second rule keeps the gate closed: a change that talks a reviewer into writing a broken
    finding gets that finding dropped, but it does not get a clean result for it.
    """
    run["envelope"]["dropped"] = dropped
    if (unchecked or dropped["malformed"]) and run["envelope"]["status"] == "complete":
        run["envelope"]["status"] = "partial"


def rebuild(
    out_dir: Path | str,
    reader: Reader,
    run_meta: dict,
    *,
    ran: set[str] | None = None,
    validator_ran: bool = True,
    floor: int = DEFAULT_FLOOR,
    window: int = MERGE_WINDOW,
    planned: Sequence[str] = REVIEWERS,
) -> tuple[dict, int]:
    """Compute the run document from the reviewer files and validation.json alone.

    This is what a party that does not trust the main agent calls: a launcher, a grader, a CI
    job. It reads nothing the main agent aggregated (not candidates.json, not findings.json),
    applies the gates with its own settings, and writes nothing. `reader` serves the code the
    quotes are checked against; a caller whose repository the agent could write passes a
    `BlobReader` over commits it copied out beforehand. `ran` is the set of sub-agents known to have
    run; `validator_ran` says whether verdicts may count. `planned` is the reviewers the run set
    out to start, all of them unless the caller chose fewer. Returns the document and the number
    of P0 or P1 findings left without an upheld verdict.
    """
    out = Path(out_dir)
    if not out.is_dir():
        raise ContractError(f"output folder {out} does not exist")
    merged, dropped, _ = gate_and_merge(
        collect_findings(out, list(planned), ran), reader, floor, window
    )
    verdicts = (read_verdicts(out / "validation.json") if validator_ran else None) or {}
    findings, declined = apply_verdicts(merged, verdicts)
    dropped["validator_declined"] += len(declined)
    run = build_envelope(out, list(planned), run_meta, ran)
    loose = unvalidated(findings, verdicts)
    _settle(run, dropped, loose)
    run["findings"] = [] if run["envelope"]["status"] == "failed" else findings
    load_run_envelope(run)
    return run, loose


def _read_candidates(out: Path) -> dict:
    """Load candidates.json and check the parts finalize relies on."""
    path = out / "candidates.json"
    if not plain_file(path):
        raise ContractError(f"{path} is missing or not a plain file; run first-pass first")
    doc = read_json(path)
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("dropped"), dict)
        or set(doc["dropped"]) != set(DROP_COUNTS)
    ):
        raise ContractError(f"{path}: not a candidates document")
    # The file sits where the agent can write, so every finding is checked before it is used.
    load_final_findings(doc.get("findings"))
    return doc


def finalize(out_dir: Path | str, run_meta: dict) -> dict:
    """Apply validation.json to the candidates and write the final findings.json.

    A P0 or P1 finding stays unless it is declined. If any is left without an upheld verdict
    (no verdict file, a broken one, or a skipped finding) a complete run is marked partial.
    Raises ContractError for a missing
    candidates file or a result that breaks the run contract.
    """
    out = Path(out_dir)
    if not out.is_dir():
        raise ContractError(f"output folder {out} does not exist")
    candidates = _read_candidates(out)
    findings = candidates["findings"]
    verdicts = read_verdicts(out / "validation.json") or {}
    dropped = dict(candidates["dropped"])
    findings, declined = apply_verdicts(findings, verdicts)
    dropped["validator_declined"] += len(declined)
    if declined:
        append_declined(out / "declined.json", declined)
    validator_failed = unvalidated(findings, verdicts) > 0
    run = build_envelope(out, REVIEWERS, run_meta)
    _settle(run, dropped, validator_failed)
    run["findings"] = [] if run["envelope"]["status"] == "failed" else findings
    load_run_envelope(run)
    _write(out / "findings.json", run)
    return run
