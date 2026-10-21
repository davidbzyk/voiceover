"""Read run metadata from Codex rollout files. Standard library only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class RunMeta:
    """What the agent CLI's own record says about a run."""

    model: str | None
    effort: str | None
    cli_version: str | None
    sandbox: str | None
    subagents: tuple[str, ...]
    usage: dict | None = None


def _first_payload(path: Path) -> dict:
    """Payload of the first line of a rollout, or an empty dict when unreadable."""
    try:
        with path.open() as fh:
            return json.loads(fh.readline()).get("payload", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def _joined(values: set[str]) -> str | None:
    """One value as is, several joined so a mismatch cannot hide, none as None."""
    return ",".join(sorted(values)) or None


class RolloutActivity:
    """When one Codex run last wrote anything: the main agent's rollout or a sub-agent's.

    The main agent prints nothing while it waits for its sub-agents, so its output alone cannot
    tell a working run from a stalled one. Their rollout files can: each grows as its agent works.
    """

    def __init__(self, env: dict[str, str]) -> None:
        """Remember where this run's sessions are written."""
        self.sessions = Path(env["CODEX_HOME"]) / "sessions"
        self.family: set[Path] = set()
        self.strangers: set[Path] = set()

    def latest(self, events: list[dict]) -> float | None:
        """Newest modification time among the run's rollouts, or None before the run has any."""
        thread = next(
            (e.get("thread_id") for e in list(events) if e.get("type") == "thread.started"), None
        )
        if not thread:
            return None
        today = date.today()
        for day in (today - timedelta(days=1), today, today + timedelta(days=1)):
            for path in (self.sessions / f"{day:%Y/%m/%d}").glob("rollout-*.jsonl"):
                if path in self.family or path in self.strangers:
                    continue
                meta = _first_payload(path)
                if thread in (meta.get("id"), meta.get("parent_thread_id")):
                    self.family.add(path)
                elif meta:  # an unreadable first line may only be half written; look again later
                    self.strangers.add(path)
        times = []
        for path in self.family:
            try:
                times.append(path.stat().st_mtime)
            except OSError:
                continue
        return max(times, default=None)


TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_output_tokens", "total_tokens")  # fmt: skip


def _read_usage(paths: dict[str, Path]) -> dict | None:
    """Tokens per session and the subscription allowance reading, from token_count lines.

    A session's figure is its last running total. The allowance is the first and the last
    reading by timestamp across every session of the run. None when no line carries usage.
    """
    sessions: dict[str, dict[str, int]] = {}
    readings: list[tuple[str, dict, str | None]] = []
    for name, path in paths.items():
        with path.open() as fh:
            for line in fh:
                if '"token_count"' not in line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = item.get("payload") or {}
                total = (payload.get("info") or {}).get("total_token_usage")
                if isinstance(total, dict):
                    sessions[name] = {f: int(total.get(f) or 0) for f in TOKEN_FIELDS}
                limits = payload.get("rate_limits") or {}
                if isinstance(limits.get("primary"), dict):
                    stamp = str(item.get("timestamp") or "")
                    readings.append((stamp, limits["primary"], limits.get("plan_type")))
    if not sessions:
        return None
    usage: dict = {
        "sessions": sessions,
        "total": {f: sum(s[f] for s in sessions.values()) for f in TOKEN_FIELDS},
        "allowance": None,
    }
    if readings:
        readings.sort(key=lambda r: r[0])
        usage["allowance"] = {
            "window_minutes": readings[-1][1].get("window_minutes"),
            "used_percent_first": readings[0][1].get("used_percent"),
            "used_percent_last": readings[-1][1].get("used_percent"),
            "plan_type": readings[-1][2],
        }
    return usage


def parse_codex_rollout(events: list[dict], env: dict[str, str]) -> RunMeta | None:
    """Find the root rollout of the run's thread under CODEX_HOME and read its metadata.

    Model, effort and sandbox come from turn_context lines, the CLI version from the first
    session_meta line, and subagent names from the agent_path of child rollouts whose
    parent_thread_id is the root thread. Returns None when no rollout is found.
    """
    thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
    if not thread:
        return None
    sessions = Path(env["CODEX_HOME"]) / "sessions"
    roots = sorted(sessions.glob(f"*/*/*/rollout-*-{thread}.jsonl"))
    if not roots:
        return None
    root = roots[0]
    day = date(*(int(p) for p in root.parent.parts[-3:]))
    days = [root.parent, sessions / f"{day + timedelta(days=1):%Y/%m/%d}"]
    models, efforts, sandboxes = set(), set(), set()
    for line in root.read_text().splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "turn_context":
            continue
        payload = item.get("payload", {})
        models.add(payload.get("model"))
        efforts.add(payload.get("effort"))
        sandboxes.add((payload.get("sandbox_policy") or {}).get("type"))
    subagents = set()
    paths = {"main": root}
    for folder in days:
        for path in folder.glob("rollout-*.jsonl"):
            meta = _first_payload(path)
            if meta.get("parent_thread_id") == thread and meta.get("agent_path"):
                name = meta["agent_path"].rsplit("/", 1)[-1]
                subagents.add(name)
                paths.setdefault(name, path)
    return RunMeta(
        model=_joined(models - {None}),
        effort=_joined(efforts - {None}),
        cli_version=_first_payload(root).get("cli_version"),
        sandbox=_joined(sandboxes - {None}),
        subagents=tuple(sorted(subagents)),
        usage=_read_usage(paths),
    )
