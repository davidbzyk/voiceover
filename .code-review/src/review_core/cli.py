"""Command line: python -m review_core.cli review --repo DIR --base REF --head REF."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from review_core.ci.github import CredentialInOutput, _check, _encodings, credentials
from review_core.launcher.run import run_review

DEFAULT_SKILLS = Path(__file__).resolve().parents[1] / "plugin" / "skills"
# A backstop after the run's own credentials: any long token-shaped run is blanked too.
WITHHELD = "[withheld: this line holds a credential of the run]"
_TOKEN = re.compile(r"[A-Za-z0-9_\-.]{40,}")


def agent_errors(run_dir: Path, secrets: list[str] | None = None, tail: int = 5) -> list[str]:
    """The agent's own error messages from its saved events, else the end of its stderr.

    Every form of `secrets` the poster's guard knows is blanked, then long token-shaped runs, and
    each line is cut to 300 characters; a missing file gives none.
    """
    found: list[str] = []
    events = run_dir / "events.jsonl"
    for raw in events.read_text(errors="replace").splitlines() if events.is_file() else []:
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        message = ""
        if event.get("type") == "error":
            message = str(event.get("message", ""))
        # Review (PR 1238), shown not to occur: a string `error` here would raise, but Codex
        # 0.161.0 writes it as an object, as run 40588745870's events show.
        elif event.get("type") == "turn.failed":
            message = str((event.get("error") or {}).get("message", ""))
        if message.strip():
            found.append(message)
    if not found:
        stderr = run_dir / "stderr.txt"
        lines = stderr.read_text(errors="replace").splitlines() if stderr.is_file() else []
        found = [line for line in lines if line.strip()][-tail:]
    needles = sorted({n for secret in secrets or [] for n in _encodings(secret)}, key=len)[::-1]
    shown = []
    for line in found:
        for needle in needles:
            line = line.replace(needle, "[redacted]")
        line = _TOKEN.sub("[redacted]", " ".join(line.split()))[:300]
        try:  # a credential split by spaces or backslashes survives the replace: drop the line
            _check([line], secrets or [])
        except CredentialInOutput:
            line = WITHHELD
        shown.append(line)
    return [line for line in shown if line]


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
    review.add_argument(
        "--secret-file", type=Path, action="append", default=[],
        help="login file whose values are blanked in printed agent errors",
    )  # fmt: skip
    review.add_argument(
        "--secret-env", action="append", default=[],
        help="variable whose value is blanked in printed agent errors",
    )  # fmt: skip
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
        try:
            secrets = credentials(args.secret_file, args.secret_env)
        except CredentialInOutput as exc:  # an unread login cannot be blanked: print nothing
            print(f"agent error lines withheld: {exc}", file=sys.stderr)
        else:
            for line in agent_errors(result.run_dir, secrets):
                print(f"agent said: {line}", file=sys.stderr)
    return 1 if result.status == "failed" or stopped else 0


if __name__ == "__main__":
    sys.exit(main())
