"""Command line for the aggregator: the commands `first-pass`, `finalize` and `report`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from review_core.aggregator.confidence import DEFAULT_FLOOR
from review_core.aggregator.pipeline import finalize, first_pass
from review_core.aggregator.report import render_report
from review_core.aggregator.validate import plain_file
from review_core.contracts.models import ContractError, read_json
from review_core.envelope import MERGE_WINDOW

MAX_SUMMARY_BYTES = 64 * 1024


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser for both commands."""
    parser = argparse.ArgumentParser(prog="review_core.aggregator.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("first-pass", help="gate, filter and dedup the reviewers' findings")
    first.add_argument("--out", required=True)
    first.add_argument("--repo", required=True)
    first.add_argument("--base", required=True)
    first.add_argument("--head", required=True)
    first.add_argument("--confidence-floor", type=int, default=DEFAULT_FLOOR)
    first.add_argument("--window", type=int, default=MERGE_WINDOW)
    last = sub.add_parser("finalize", help="apply the validator's verdicts, write findings.json")
    last.add_argument("--out", required=True)
    # The agent that runs this rarely knows these; whoever launched it records what it observed.
    for name in ("model", "effort", "runner", "cli-version", "sandbox-mode"):
        last.add_argument(f"--{name}", default="unknown")
    show = sub.add_parser("report", help="write report.md from findings.json and pr-summary.md")
    show.add_argument("--out", required=True)
    return parser


def _read_summary(path: Path) -> str | None:
    """The main agent's summary, or None when it is absent, a link, too big or not UTF-8 text."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_SUMMARY_BYTES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def report(out_dir: Path | str) -> str:
    """Write <out>/report.md from findings.json and, when usable, pr-summary.md; return the text.

    Raises ContractError when findings.json is missing or breaks the run contract, or when
    report.md is a link or not a plain file.
    """
    out = Path(out_dir)
    found = out / "findings.json"
    if not plain_file(found):
        raise ContractError(f"{found} is missing or not a plain file; run finalize first")
    text = render_report(read_json(found), _read_summary(out / "pr-summary.md"))
    target = out / "report.md"
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ContractError(f"{target} is a link or not a plain file; it was not written")
    target.write_bytes(text.encode("utf-8"))
    return text


def _print(text: str) -> None:
    """Print the text exactly as written to report.md, whatever the terminal's encoding."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass
    sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    """Run one command; exit 0 on success, otherwise print one line to stderr and return 1."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "first-pass":
            first_pass(
                args.out, args.repo, args.base, args.head, args.confidence_floor, args.window
            )
        elif args.command == "report":
            _print(report(args.out))
        else:
            meta = {
                "runner": args.runner,
                "model": args.model,
                "effort": args.effort,
                "cli_version": args.cli_version,
                "sandbox_mode": args.sandbox_mode,
            }
            finalize(args.out, meta)
    except ContractError as exc:
        print(f"error: {exc}".splitlines()[0], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
