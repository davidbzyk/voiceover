"""Command line: python -m review_core.cli review --repo DIR --base REF --head REF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from review_core.launcher.run import run_review

DEFAULT_SKILLS = Path(__file__).resolve().parents[1] / "plugin" / "skills"


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="review_core.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review", help="run a multi-agent review of base..head")
    review.add_argument("--repo", required=True, help="directory holding the repository")
    review.add_argument("--base", required=True)
    review.add_argument("--head", required=True)
    review.add_argument("--runner", default="codex")
    review.add_argument("--model", default="gpt-6-luna")
    review.add_argument("--effort", default="high")
    review.add_argument("--skills", default=str(DEFAULT_SKILLS))
    review.add_argument("--out", default=None, help="findings folder (default REPO/.review)")
    review.add_argument("--runs", default=None, help="runs folder (default <project>/runs)")
    review.add_argument("--timeout-sec", type=int, default=1800)
    review.add_argument("--registry", default=None, help="runners.toml instead of the packaged one")
    review.add_argument("--path", action="append", help="limit the review to this file; repeat")
    review.add_argument("--task-text", default=None, help="what the change is meant to do")
    review.add_argument("--context-command", default=None, help="search command of a context store")
    review.add_argument("--case", default="adhoc", help="case name recorded in the manifest")
    review.add_argument("--store", default=None, help="built context store for this run's arm")
    review.add_argument(
        "--env-file", default=None, help="file the search command reads the key from"
    )
    review.add_argument("--idle-sec", type=int, default=600, help="stop a run silent this long")
    review.add_argument(
        "--prior-review", default=None, help="file of this pull request's earlier findings"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command and return the exit code: 1 when the run failed or its agent did."""
    args = _parser().parse_args(argv)
    result = run_review(
        workdir=args.repo, base=args.base, head=args.head, skills_dir=args.skills,
        runner=args.runner, model=args.model, effort=args.effort, timeout_sec=args.timeout_sec,
        out_dir=args.out, runs_dir=args.runs, registry_path=args.registry,
        slice_paths=args.path, task_text=args.task_text, context_command=args.context_command,
        case=args.case, idle_sec=args.idle_sec, store=args.store, env_file=args.env_file,
        prior_review=args.prior_review,
    )  # fmt: skip
    for row in result.document["envelope"]["reviewers"]:
        print(f"{row['reviewer']}: {row['outcome']} ({row['findings_count']} findings)")
    print(f"status: {result.status}")
    for reason in result.reasons:
        print(f"reason: {reason}", file=sys.stderr)
    print(f"review.json: {result.review_path}")
    # An agent that crashed or was stopped may still have left files that parse: not trustworthy.
    stopped = result.exit_code != 0 or result.timed_out
    if stopped:
        print(f"reason: the agent exited {result.exit_code}"
              f"{' after a timeout' if result.timed_out else ''}", file=sys.stderr)  # fmt: skip
    return 1 if result.status == "failed" or stopped else 0


if __name__ == "__main__":
    sys.exit(main())
