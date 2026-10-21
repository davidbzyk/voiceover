"""Run the review team as separate agent processes: one per reviewer, then one validator.

The one-agent launch asks a main agent to start the reviewers as its sub-agents, and each of
those begins with the main agent's prompt and every skill its host lists. Here the launcher
starts each reviewer itself: a reviewer's process holds its own skill and its own message and
nothing of the team's. Who is on the team and the words each member is sent are read from the
orchestrator skill, so both launches say the same thing and a new reviewer is a row there.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from review_core.aggregator.confidence import DEFAULT_FLOOR
from review_core.aggregator.gates import Reader
from review_core.aggregator.pipeline import gate_and_merge, validator_input
from review_core.aggregator.validate import VALIDATOR
from review_core.envelope import MERGE_WINDOW, collect_findings
from review_core.launcher.render import WHERE_HERE
from review_core.launcher.rollout import TOKEN_FIELDS, RunMeta
from review_core.launcher.runners import RunnerEntry, agent_env

# The two ways a team is run: one main agent that starts the rest, or a process per member.
TEAMS = ("one", "separate")
ORCHESTRATOR = "review-orchestrator"
AGENTS_FOLDER = "agents"
VALIDATOR_INPUT = "validator-input.json"
# Template lines that are sent only when the launcher has that item; the text before the
# placeholder is the same lead `prompt_extras` writes.
OPTIONAL = ("<file list>", "<task text>", "<method>", "<command>", "<earlier review>")
_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*`([\w-]+)`\s*\|\s*$", re.MULTILINE)
_BLOCK = re.compile(r"^```\n(.*?)^```$", re.MULTILINE | re.DOTALL)
_SKILL = re.compile(r"Use the ([\w-]+) skill")
_UNFILLED = re.compile(r"<[a-z][a-z -]*>")


class TeamError(ValueError):
    """The orchestrator skill does not say who is on the team or what each member is sent."""


@dataclass(frozen=True)
class Team:
    """The team as the orchestrator skill lays it out."""

    reviewers: dict[str, str]  # reviewer name -> the skill it loads
    reviewer_message: str
    validator_skill: str
    validator_message: str


@dataclass(frozen=True)
class AgentRun:
    """One member's process: what it was asked to be, how it ended, what its record shows."""

    name: str
    model: str
    effort: str
    exit_code: int | None
    stopped: str | None
    seconds: float
    meta: RunMeta | None
    problems: tuple[str, ...]

    @property
    def counted(self) -> bool:
        """Whether this member's file may count: it ran, as the model and effort asked for."""
        return self.meta is not None and not self.problems


@dataclass(frozen=True)
class TeamOutcome:
    """What a separate run of the team produced, for the launcher to turn into a result."""

    runs: tuple[AgentRun, ...]
    validator: AgentRun | None
    reasons: tuple[str, ...]

    @property
    def ran(self) -> set[str]:
        """The members whose files count."""
        every = (*self.runs, *([self.validator] if self.validator else []))
        return {r.name for r in every if r.counted}


def read_team(skills_dir: Path | str) -> Team:
    """Read the team from the orchestrator skill: its table of reviewers and its two messages."""
    path = Path(skills_dir) / ORCHESTRATOR / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TeamError(f"cannot read the orchestrator skill at {path}: {exc}") from None
    reviewers = dict(_ROW.findall(text))
    blocks = _BLOCK.findall(text)
    to_reviewer = next((b for b in blocks if "<reviewer>" in b and "<skill>" in b), None)
    to_validator = next((b for b in blocks if "<reviewer>" not in b and "validator" in b), None)
    skill = _SKILL.search(to_validator or "")
    if not reviewers or to_reviewer is None or to_validator is None or skill is None:
        raise TeamError(f"{path} does not name the reviewers and the message each is sent")
    return Team(reviewers, to_reviewer.strip("\n"), skill.group(1), to_validator.strip("\n"))


def fill(template: str, values: Mapping[str, str], extras: Sequence[str], where: str) -> str:
    """A message from the skill's template: placeholders filled, lines for absent items dropped.

    `extras` are the optional lines as `prompt_extras` wrote them; each replaces the template
    line that starts the same way. A placeholder nothing fills is an error, never sent as is.
    """
    lines = []
    for line in template.splitlines():
        slot = next((s for s in OPTIONAL if s in line), None)
        if slot is not None:
            lead = line[: line.index(slot)]
            lines += [x for x in extras if x.startswith(lead)][:1]
            continue
        unknown = [p for p in _UNFILLED.findall(line) if p not in values]
        if unknown:
            raise TeamError(f"the skill's message has a placeholder nothing fills: {unknown[0]}")
        for key, value in values.items():
            line = line.replace(key, value)
        lines.append(line.replace(WHERE_HERE, where))
    return "\n".join(lines) + "\n"


def _write_plain(path: Path, text: str) -> bool:
    """Write a file the agents could have planted a link at, without following one."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True


def _problems(run_meta: RunMeta | None, model: str, effort: str, cli_version: str | None) -> list:
    """Why a member's record does not match what was asked for; empty when it does."""
    if run_meta is None:
        return ["no session record found"]
    wanted = (("model", run_meta.model, model), ("effort", run_meta.effort, effort),
              ("cli_version", run_meta.cli_version, cli_version))  # fmt: skip
    found = [f"{n} mismatch: record shows {seen!r}, asked for {want!r}"
             for n, seen, want in wanted if want is not None and seen != want]  # fmt: skip
    if None in (run_meta.model, run_meta.effort, run_meta.cli_version):
        found.append("session record incomplete")
    return found


def run_team(
    *,
    entry: RunnerEntry,
    team: Team,
    reviewers: Sequence[str],
    skills_dir: Path,
    run_dir: Path,
    start: Path,
    out_dir: Path,
    base: str,
    head: str,
    where: str,
    extras: Sequence[str],
    model: str,
    effort: str,
    models: Mapping[str, str],
    codex_home: Path,
    cli_version: str | None,
    timeout_sec: int,
    idle_sec: int | None,
    bin_dir: Path,
    reader: Reader,
    launch: Callable,
    on_event: Callable[[dict], None] | None = None,
    parallel: int | None = None,
    secrets: Mapping[str, str] | None = None,
) -> TeamOutcome:
    """Start each reviewer as its own agent, then the validator when a finding needs one.

    `reader` serves the code the findings are checked against, copied out before any agent
    started. `launch` starts one process and watches it. At most `parallel` reviewers run at
    once (all of them when None). A member's file counts only if its own record shows it ran
    as the model and effort asked for.
    """

    def tell(kind: str, name: str, **more) -> None:
        if on_event:
            on_event({"type": kind, "agent": name, **more})

    def one(name: str, skill: str, prompt: str) -> AgentRun:
        folder = run_dir / AGENTS_FOLDER / name
        home = folder / "home"
        home.mkdir(parents=True)
        wanted = models.get(name, model)
        ctx = {
            "workdir": str(start), "out_dir": str(out_dir), "model": wanted, "effort": effort,
            "last_message": str(folder / "last_message.txt"), "home": str(home),
            "codex_home": str(codex_home), "sandbox": entry.permissions.sandbox, "prompt": prompt,
        }  # fmt: skip
        # Its own skill and no other: the folder its host lists skills from holds one.
        shutil.copytree(skills_dir / skill, Path(entry.skills_copy_to.format_map(ctx)) / skill)
        folder.joinpath("prompt.txt").write_text(prompt, encoding="utf-8")
        env = agent_env(entry, ctx, secrets)
        env["PATH"] = os.pathsep.join(p for p in (str(bin_dir), env.get("PATH", "")) if p)
        argv = [a.format_map(ctx) for a in entry.argv]
        tell("agent.started", name, model=wanted)
        began = time.monotonic()
        events, code, stopped = launch(
            argv, env, start, folder, timeout_sec, None, idle_sec, entry.activity(env)
        )
        seconds = round(time.monotonic() - began, 1)
        meta = entry.parser(events, env)
        problems = tuple(_problems(meta, wanted, effort, cli_version))
        tell("agent.finished", name, exit_code=code, seconds=seconds, stopped=stopped)
        return AgentRun(name, wanted, effort, code, stopped, seconds, meta, problems)

    values = {"<base>": base, "<head>": head, "<out>": str(out_dir)}
    jobs = []
    for name in reviewers:
        mine = {**values, "<skill>": team.reviewers[name], "<reviewer>": name}
        jobs.append((name, team.reviewers[name], fill(team.reviewer_message, mine, extras, where)))
    with ThreadPoolExecutor(max_workers=max(1, parallel or len(jobs))) as pool:
        runs = tuple(pool.map(lambda job: one(*job), jobs))

    reasons = [f"{r.name}: {p}" for r in runs for p in r.problems]
    reasons += [f"{r.name}: stopped ({r.stopped})" for r in runs if r.stopped]
    ran = {r.name for r in runs if r.counted}
    merged = gate_and_merge(
        collect_findings(out_dir, list(reviewers), ran), reader, DEFAULT_FLOOR, MERGE_WINDOW
    )[0]
    to_check = validator_input(merged)
    validator = None
    if to_check["findings"]:
        if _write_plain(out_dir / VALIDATOR_INPUT, json.dumps(to_check, indent=2) + "\n"):
            message = fill(team.validator_message, values, extras, where)
            validator = one(VALIDATOR, team.validator_skill, message)
            reasons += [f"{VALIDATOR}: {p}" for p in validator.problems]
        else:
            reasons.append(f"{VALIDATOR}: not started, its input file could not be written")
    return TeamOutcome(runs, validator, tuple(reasons))


def team_meta(outcome: TeamOutcome) -> RunMeta | None:
    """One record for the whole team, in the shape a one-agent run's record has.

    Model, effort and version are joined when members differ, so a mixed team reads as mixed.
    Tokens are per member; the allowance is the lowest first reading and the highest last.
    """
    every = [r for r in (*outcome.runs, outcome.validator) if r is not None and r.meta]
    if not every:
        return None

    def joined(values) -> str | None:
        return ",".join(sorted({v for v in values if v})) or None

    sessions: dict[str, dict[str, int]] = {}
    allowances = []
    for run in every:
        usage = run.meta.usage or {}
        rows = list((usage.get("sessions") or {}).values())
        if rows:
            sessions[run.name] = {f: sum(row[f] for row in rows) for f in TOKEN_FIELDS}
        if usage.get("allowance"):
            allowances.append(usage["allowance"])
    usage = None
    if sessions:
        usage = {
            "sessions": sessions,
            "total": {f: sum(s[f] for s in sessions.values()) for f in TOKEN_FIELDS},
            "allowance": None,
        }
        if allowances:
            usage["allowance"] = {
                "window_minutes": allowances[-1].get("window_minutes"),
                "used_percent_first": min(a["used_percent_first"] for a in allowances),
                "used_percent_last": max(a["used_percent_last"] for a in allowances),
                "plan_type": allowances[-1].get("plan_type"),
            }
    return RunMeta(
        model=joined(r.meta.model for r in every),
        effort=joined(r.meta.effort for r in every),
        cli_version=joined(r.meta.cli_version for r in every),
        sandbox=joined(r.meta.sandbox for r in every),
        subagents=tuple(sorted(outcome.ran)),
        usage=usage,
    )


def team_record(outcome: TeamOutcome) -> dict:
    """What each member was and did, for the run folder: the record of a separate run."""
    rows = [
        {
            "agent": r.name, "model": r.model, "effort": r.effort, "exit_code": r.exit_code,
            "stopped": r.stopped, "seconds": r.seconds, "counted": r.counted,
            "problems": list(r.problems),
        }
        for r in (*outcome.runs, outcome.validator) if r is not None
    ]  # fmt: skip
    return {"team": "separate", "agents": rows}
