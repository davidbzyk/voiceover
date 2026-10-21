"""Run one review: start the agent through its registry entry, watch it, read back its files."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from review_core.aggregator.cli import MAX_SUMMARY_BYTES
from review_core.aggregator.gates import BlobReader, export_blobs, resolve_commit
from review_core.aggregator.pipeline import rebuild
from review_core.aggregator.report import render_report
from review_core.aggregator.validate import VALIDATOR
from review_core.context.providers import load_registry as load_providers
from review_core.contracts.models import Finding, load_manifest, load_run_envelope
from review_core.hashing import tree_sha256
from review_core.launcher.render import (
    AGGREGATE_COMMAND,
    CTX_COMMAND,
    CTX_LOG_NAME,
    CTX_SCRATCH_NAME,
    MAX_CTX_LOG_BYTES,  # noqa: F401 -- re-exported for callers that read it from here
    aggregate_wrapper_text,
    copy_reviewer_files,
    ctx_wrapper_text,
    prompt_extras,
    read_regular_file,
    render_prompt,
    repository_location,
    summarise_ctx_log,
)
from review_core.launcher.render import (
    context_command as _context_command,
)
from review_core.launcher.runners import (
    RegistryError,
    RunnerEntry,
    agent_env,
    load_registry,
    read_secrets,
)
from review_core.launcher.team import (
    TEAMS,
    read_team,
    run_team,
    team_meta,
    team_record,
)
from review_core.pipeline_digest import pipeline_digest

DEFAULT_RUNS = Path(__file__).resolve().parents[3] / "runs"
# Codex's workspace-write sandbox also lets commands write /tmp and $TMPDIR unless a row opts out.
CODEX_TMP_OPT_OUTS = {
    "/tmp": "sandbox_workspace_write.exclude_slash_tmp=true",
    "TMPDIR": "sandbox_workspace_write.exclude_tmpdir_env_var=true",
}
# The folder that holds this package, for the search command's import path.
SRC = Path(__file__).resolve().parents[2]
# Arms a store can declare, and every arm a run can be of.
STORE_ARMS = ("vector", "okf")
ARMS = ("plain", *STORE_ARMS)
# Where a repository under review keeps its knowledge notes, for the okf kind.
NOTES_FOLDER = "okf"
# The change as a diff, which a case folder keeps beside the project folder.
DIFF_NAME = "change.diff"
# The main agent's summary of the change, written after the result is final.
SUMMARY_NAME = "pr-summary.md"
STORE_CHECK_TIMEOUT_SEC = 120
# The one line `ctx check` prints when the store answered in full.
CHECK_OK = re.compile(r"ctx check: ok \([^\n]*\)")
PLACEHOLDER = "unset"


@dataclass(frozen=True)
class ReviewResult:
    """What one review run produced. A failed run carries no findings."""

    run_id: str
    run_dir: Path
    out_dir: Path
    status: str
    document: dict
    findings: tuple[Finding, ...]
    exit_code: int
    timed_out: bool
    reasons: tuple[str, ...]
    subagents: tuple[str, ...]

    @property
    def review_path(self) -> Path:
        """Path of the review.json this run wrote."""
        return self.run_dir / "review.json"


def _now() -> str:
    """Current UTC time as an ISO string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pump(stream, path: Path, events: list[dict], on_event: Callable[[dict], None] | None) -> None:
    """Copy the agent's stdout to events.jsonl and hand each parsed event on."""
    with path.open("w") as out:
        for line in stream:
            out.write(line)
            out.flush()
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
                if on_event:
                    on_event(event)


def _kill_group(proc: subprocess.Popen) -> None:
    """Kill the agent's whole process group, whatever is left of it."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


# How often a running agent is checked for the wall-clock limit and for signs of life.
POLL_SEC = 1.0


def _launch(argv, env, workdir, run_dir, timeout_sec, on_event, idle_sec=None, activity=None):
    """Start the agent with stdin closed in its own process group.

    Returns the events, the exit code and why it was stopped: "timeout" at the wall-clock limit,
    "idle" when neither its output nor `activity.latest` moved for idle_sec seconds, else None.
    """
    events: list[dict] = []
    events_path = run_dir / "events.jsonl"
    with (run_dir / "stderr.txt").open("wb") as err:
        proc = subprocess.Popen(
            argv, cwd=workdir, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=err, text=True, encoding="utf-8", errors="replace", start_new_session=True,
        )  # fmt: skip
        reader = threading.Thread(target=_pump, args=(proc.stdout, events_path, events, on_event))
        reader.start()
        stopped = None
        started = last_seen = time.time()
        try:
            while proc.poll() is None:
                try:
                    proc.wait(timeout=POLL_SEC)
                    break
                except subprocess.TimeoutExpired:
                    pass
                now = time.time()
                if now - started >= timeout_sec:
                    stopped = "timeout"
                    break
                if idle_sec is None:
                    continue
                seen = [events_path.stat().st_mtime if events_path.exists() else started]
                if activity is not None:
                    seen.append(activity.latest(events) or started)
                last_seen = max(last_seen, *seen)
                if now - last_seen >= idle_sec:
                    stopped = "idle"
                    break
        finally:
            _kill_group(proc)
            proc.wait()
            reader.join(timeout=10)
    return events, proc.returncode, stopped


def _store_identity(store: Path) -> tuple[str, str]:
    """The arm and hash a built context store declares; ValueError when it declares neither."""
    try:
        manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
        arm, store_hash = manifest["provider"], manifest["store_sha256"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{store} is not a context store: {exc}") from None
    if arm not in STORE_ARMS or not isinstance(store_hash, str) or not store_hash:
        raise ValueError(f"{store} is not a context store of a known arm")
    return arm, store_hash


def _write_ctx_wrapper(
    run_dir: Path, store: Path, env_file: Path | str | None, out_dir: Path
) -> Path:
    """Write the run's search command in its bin folder, where the sandbox cannot write.

    The bin folder leads the agent's PATH, so the reviewers find the command by name.
    """
    wrapper = run_dir / "bin" / CTX_COMMAND
    wrapper.parent.mkdir(exist_ok=True)
    wrapper.write_text(
        ctx_wrapper_text(
            sys.executable, SRC, store, out_dir / CTX_LOG_NAME, out_dir / CTX_SCRATCH_NAME, env_file
        )
    )
    wrapper.chmod(0o755)
    return wrapper


def _has_notes(workdir: Path) -> bool:
    """Whether the project has its own folder of notes: a real folder, not a link to one."""
    notes = workdir / NOTES_FOLDER
    return notes.is_dir() and not notes.is_symlink()


class StoreCheckError(ValueError):
    """The context store did not pass its check, so no agent was started."""


MAX_CHANGED_PATHS = 60


def _changed_paths(
    workdir: Path, base_id: str, head_id: str, paths: Sequence[str] | None
) -> list[str]:
    """The files of the change, for the store check: the slice's, or the diff's.

    The names come from the project under review, so one that starts with a dash is never
    chosen: handed to a command it would be read as a flag.
    """
    if paths is None:
        done = subprocess.run(
            ["git", "-C", str(workdir), "diff", "--name-only", "-z", base_id, head_id],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        paths = done.stdout.split("\0") if done.returncode == 0 else []
    return [p for p in sorted(paths) if p and not p.startswith("-")][:MAX_CHANGED_PATHS]


def _changed_path(workdir: Path, base_id: str, head_id: str, paths: Sequence[str] | None) -> str:
    """One file of the change for the store check to look up, or "" when there is none."""
    return next(iter(_changed_paths(workdir, base_id, head_id, paths)), "")


def _check_store(wrapper: Path, workdir: Path, path: str) -> str:
    """Run the store's own check through the run's search command, before any agent starts.

    The store is built and proven by scripts; the agent only searches it. Returns the check's
    one line, or raises StoreCheckError with the reason.
    """
    try:
        done = subprocess.run(
            [str(wrapper), "check", *([path] if path else [])], cwd=workdir,
            capture_output=True, text=True, check=False, timeout=STORE_CHECK_TIMEOUT_SEC,
        )  # fmt: skip
        code, said, line = done.returncode, done.stderr.strip() or done.stdout.strip(), done.stdout
    except subprocess.TimeoutExpired:
        code, said, line = 1, f"no answer within {STORE_CHECK_TIMEOUT_SEC} seconds", ""
    # Exit 0 alone is not a pass: a command that printed its usage also exits 0.
    if code != 0 or not CHECK_OK.fullmatch(line.strip()):
        why = " ".join(said.split())[:400] or f"exit code {code}"
        raise StoreCheckError(
            f"the context store did not pass its check, so no agent was started: {why}"
        )
    return line.strip()


def _close_ctx(run_dir: Path, out_dir: Path, check: str = "") -> None:
    """Write the run's search record. The scratch folder is left alone.

    This runs outside the sandbox, and the scratch folder sits where the agent could have put
    a link. Each search call removes its own scratch files from inside the sandbox instead.
    """
    record = {**summarise_ctx_log(out_dir / CTX_LOG_NAME), "check": check}
    run_dir.joinpath("ctx.json").write_text(json.dumps(record, indent=2) + "\n")


def _agent_writable(entry: RunnerEntry, start: Path) -> list[Path]:
    """Every folder the agent's commands may write: its start folder, the row's writable roots
    and, for Codex in workspace-write, the temp folders it opens unless the row opts out."""
    roots = [start, *(Path(r.replace("{workdir}", str(start))).resolve()
                      for r in entry.permissions.writable_roots)]  # fmt: skip
    if Path(entry.argv[0]).name == "codex" and entry.permissions.sandbox == "workspace-write":
        tmpdir = os.environ.get("TMPDIR")
        if CODEX_TMP_OPT_OUTS["/tmp"] not in entry.argv:
            roots.append(Path("/tmp").resolve())
        if tmpdir and CODEX_TMP_OPT_OUTS["TMPDIR"] not in entry.argv:
            roots.append(Path(tmpdir).resolve())
    return roots


def run_review(
    *,
    workdir: Path | str,
    base: str,
    head: str,
    skills_dir: Path | str,
    runner: str = "codex",
    model: str = "gpt-6-luna",
    effort: str = "high",
    timeout_sec: int = 1800,
    out_dir: Path | str | None = None,
    runs_dir: Path | str | None = None,
    registry_path: Path | str | None = None,
    codex_home: Path | str | None = None,
    cli_version: str | None = None,
    on_event: Callable[[dict], None] | None = None,
    run_id: str | None = None,
    case: str = "adhoc",
    idle_sec: int | None = 600,
    slice_paths: Sequence[str] | None = None,
    task_text: str | None = None,
    prior_review: Path | str | None = None,
    context_command: str | None = None,
    store: Path | str | None = None,
    arm: str | None = None,
    start_in: Path | str | None = None,
    env_file: Path | str | None = None,
    key_version: str = PLACEHOLDER,
    skills_hash: str | None = None,
    snapshot_hash: str = PLACEHOLDER,
    team: str = "one",
    reviewers: Sequence[str] | None = None,
    models: Mapping[str, str] | None = None,
    parallel: int | None = None,
) -> ReviewResult:
    """Run one review of base..head in workdir and write review.json and manifest.json.

    on_event is called on a worker thread with each parsed event and must not raise.
    cli_version, when given, is the version the rollout must report. A run in which neither the
    main agent nor any sub-agent writes anything for idle_sec seconds is stopped. slice_paths
    limits every reviewer to those files; task_text says what the change is meant to do;
    prior_review names a file of this pull request's earlier findings and how each ended;
    context_command names the search command of a context store. Each is passed on as given.
    store is a built context store: the run then gets a `ctx` wrapper in its run folder as its
    search command and records the store's arm and hash; env_file is read by that wrapper for
    the embedder key when the environment does not already hold it, and by the launcher for a key
    the runner entry says its agent needs. A given store decides the
    kind of review; `arm` names it when there is none (plain, or okf, which needs no store: its
    notes are the repository's own `okf/` folder, and a run without one is refused).
    start_in is the folder the agent starts in: the repository itself (the default) or a folder
    that holds it. The prompt then says where the repository is, and `change.diff` there is named.
    team says how the reviewers are run: "one" starts a main agent that starts them as its
    sub-agents; "separate" starts each reviewer as an agent process of its own, holding only its
    own skill, and then the validator. A separate run may be of fewer reviewers (`reviewers`),
    may give a reviewer its own model (`models`, by reviewer name) and may limit how many run
    at once (`parallel`); it has no main agent, so it writes no summary of the change.
    """
    registry = load_registry(registry_path)
    if runner not in registry:
        raise RegistryError(f"no runner entry named {runner!r}")
    entry = registry[runner]
    keys = read_secrets(entry, env_file)  # a run without its key starts no agent
    if team not in TEAMS:
        raise ValueError(f"team must be one of {', '.join(TEAMS)}, not {team!r}")
    separate = team == "separate"
    if not separate and (reviewers is not None or models or parallel is not None):
        raise ValueError("reviewers, models and parallel belong to a separate team run")
    members = read_team(skills_dir) if separate else None
    planned = (
        tuple(reviewers) if reviewers is not None else tuple(members.reviewers if members else ())
    )
    unknown = [n for n in (*planned, *(models or {})) if members and n not in members.reviewers]
    if separate and (not planned or unknown or len(set(planned)) != len(planned)):
        raise ValueError(
            f"reviewers must be distinct names from {', '.join(members.reviewers)}; "
            f"got {', '.join(unknown) or 'none, or one twice'}"
        )
    workdir = Path(workdir).resolve()
    # Names can be moved by anything that can write the repository; commit ids cannot.
    base_id, head_id = resolve_commit(workdir, base), resolve_commit(workdir, head)
    if base_id is None or head_id is None:
        raise ValueError(f"base and head must each name a commit in {workdir}")
    start = Path(start_in).resolve() if start_in is not None else workdir
    if start != workdir and not (start.is_dir() and workdir.is_relative_to(start)):
        raise ValueError(f"start_in must be the repository or a folder that holds it: {start}")
    wanted, store_hash = arm, None
    if wanted is not None and wanted not in ARMS:
        raise ValueError(f"arm must be one of {', '.join(ARMS)}, not {wanted!r}")
    if store is not None:
        store = Path(store).resolve()
        arm, store_hash = _store_identity(store)
        if wanted is not None and wanted != arm:
            raise ValueError(f"arm {wanted!r} does not match the store, which is of arm {arm!r}")
    elif wanted in ("plain", "okf", None):
        arm = wanted or "plain"
    else:
        raise ValueError(f"arm {wanted!r} needs a store")
    # The notes are ordinary files of the project, read by the reviewers with their file tools.
    if arm == "okf" and not _has_notes(workdir):
        raise ValueError(
            f"an okf run needs a folder of notes named {NOTES_FOLDER}/ at the top of {workdir}"
        )
    out_dir = Path(out_dir or workdir / ".review")
    # The folder may sit in the project under review, which could ship a link in its place.
    if out_dir.is_symlink() or (out_dir.exists() and not out_dir.is_dir()):
        raise ValueError(f"{out_dir} must be a real folder, not a link or a file")
    out_dir = out_dir.resolve()
    if any(out_dir.glob("findings*.json")):
        raise FileExistsError(f"{out_dir} already holds findings files; use a fresh folder")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
    run_dir = Path(runs_dir or DEFAULT_RUNS).resolve() / run_id
    # The agent may write its start folder, which holds the repository; the trees it is judged on
    # and the wrappers live in the run folder, so that must sit outside (pass runs_dir).
    if writable := [r for r in _agent_writable(entry, start) if run_dir.is_relative_to(r)]:
        raise ValueError(
            f"the run folder {run_dir} is inside {writable[0]}, which the agent can write"
        )
    home = run_dir / "home"
    home.mkdir(parents=True)
    codex_home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    started = _now()
    # The arm's own way of gathering context: the plain arm's row is `none`. Its reviewers are
    # given the search command when the row says so and a store backs it.
    row = load_providers().providers.get("none" if arm == "plain" else arm)
    searches = store is not None and bool(row and row.agent_search)
    store_check = ""
    if searches:
        # The store is proven by the launcher before the agent starts: the command must answer
        # for the search and for a file of the change, or no agent is started.
        wrapper = _write_ctx_wrapper(run_dir, store, env_file, out_dir)
        paths = _changed_paths(workdir, base_id, head_id, slice_paths)
        store_check = _check_store(wrapper, workdir, paths[0] if paths else "")
        context_command = _context_command()
    elif store is not None:
        context_command = None
    prior = str(Path(prior_review).resolve()) if prior_review else None
    extras = prompt_extras(slice_paths, task_text, context_command, row.method if row else None,
                           prior_review=prior)  # fmt: skip

    ctx = {
        "workdir": str(start), "out_dir": str(out_dir), "model": model, "effort": effort,
        "last_message": str(run_dir / "last_message.txt"), "home": str(home),
        "codex_home": str(codex_home.resolve()), "sandbox": entry.permissions.sandbox,
    }  # fmt: skip
    skills_copy = Path(entry.skills_copy_to.format_map(ctx))
    where = repository_location(workdir, start)
    # The commands an agent types are found by name: the run's bin folder leads its PATH.
    bin_dir = run_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    if separate:
        # Each member gets its own home and its own skill there; nothing is shared but this.
        skills_hash = skills_hash or tree_sha256(Path(skills_dir))
    else:
        if start != workdir and (start / DIFF_NAME).is_file():
            extras.append(f"The change is also in the file `{DIFF_NAME}` in the current directory.")
        ctx["prompt"] = render_prompt(base, head, out_dir, skills_copy, extras, where=where)
        argv = [a.format_map(ctx) for a in entry.argv]
        env = agent_env(entry, ctx, keys)
        shutil.copytree(skills_dir, skills_copy, dirs_exist_ok=True)
        script = skills_copy / "review-orchestrator" / "scripts" / "aggregate.py"
        aggregate = bin_dir / AGGREGATE_COMMAND
        aggregate.write_text(aggregate_wrapper_text(sys.executable, script))
        aggregate.chmod(0o755)
        env["PATH"] = os.pathsep.join(p for p in (str(bin_dir), env.get("PATH", "")) if p)
        # Hashed from the copy, before the agent starts: what it was given, whatever it does next.
        skills_hash = skills_hash or tree_sha256(skills_copy)

    # The code the findings will be checked against is copied out now, into the run folder,
    # which the agent's sandbox cannot write. After the agent has run, the repository is not
    # read again: it can move names, plant replacement objects or delete the lot.
    trees = run_dir / "trees"
    export_blobs(workdir, base_id, trees / "base")
    export_blobs(workdir, head_id, trees / "head")

    integrity: list[str] = []
    notes: list[str] = []
    if separate:
        # A member whose own record is missing or shows another model is left out, and the run
        # goes on without it; only a run in which no member's record was found has failed.
        outcome = run_team(
            entry=entry, team=members, reviewers=planned, skills_dir=Path(skills_dir),
            run_dir=run_dir, start=start, out_dir=out_dir, base=base, head=head, where=where,
            extras=extras, model=model, effort=effort, models=models or {},
            codex_home=codex_home.resolve(), cli_version=cli_version, timeout_sec=timeout_sec,
            idle_sec=idle_sec, bin_dir=bin_dir, reader=BlobReader(trees / "head", trees / "base"),
            launch=_launch, on_event=on_event, parallel=parallel, secrets=keys,
        )  # fmt: skip
        run_dir.joinpath("team.json").write_text(json.dumps(team_record(outcome), indent=2) + "\n")
        meta, notes = team_meta(outcome), list(outcome.reasons)
        codes = [r.exit_code or 0 for r in outcome.runs]
        exit_code = next((c for c in codes if c), 0)
        stopped = "timeout" if any(r.stopped == "timeout" for r in outcome.runs) else None
        if meta is None:
            integrity.append("run metadata unavailable: no member's session record was found")
    else:
        events, exit_code, stopped = _launch(
            argv, env, start, run_dir, timeout_sec, on_event, idle_sec, entry.activity(env)
        )
        meta = entry.parser(events, env)
        if meta is None:
            integrity.append("run metadata unavailable: no rollout found")
        else:
            asked = (("model", meta.model, model), ("effort", meta.effort, effort),
                     ("cli_version", meta.cli_version, cli_version))  # fmt: skip
            integrity += [
                f"{name} mismatch: rollout reports {seen!r}, requested {wanted!r}"
                for name, seen, wanted in asked
                if wanted is not None and seen != wanted
            ]
            if meta.model is None or meta.effort is None or meta.cli_version is None:
                integrity.append("run metadata incomplete in rollout")
    timed_out = stopped == "timeout"
    observed = {
        "runner": entry.name,
        "model": (meta and meta.model) or "unknown",
        "effort": (meta and meta.effort) or "unknown",
        "cli_version": (meta and meta.cli_version) or "unknown",
        "sandbox_mode": entry.permissions.sandbox,
    }
    reasons = [*integrity, *notes, *([f"timed out after {timeout_sec}s"] if timed_out else [])]
    if stopped == "idle":
        reasons.append(f"no activity for {idle_sec}s; stopped, and the reviews written were kept")

    # The result is computed here, from the reviewer files, the verdict file and the commits
    # pinned before the agent started. Nothing the main agent aggregated is read: not its
    # candidates, not its final file, not its counts. A sub-agent that the rollouts do not show
    # contributes nothing, and verdicts count only when a validator sub-agent ran. That proves
    # the steps happened, not who typed each file: sub-agents share the main agent's sandbox.
    ran = set(meta.subagents) if meta else None
    doc, loose = rebuild(
        out_dir, BlobReader(trees / "head", trees / "base"), observed,
        ran=ran, validator_ran=ran is not None and VALIDATOR in ran,
        **({"planned": planned} if separate else {}),
    )  # fmt: skip
    shutil.rmtree(trees, ignore_errors=True)
    if integrity:
        doc["envelope"]["status"] = "failed"
        doc["findings"] = []
    elif loose:
        reasons.append(f"{loose} P0/P1 finding(s) have no upheld verdict from a validator")
    loaded = load_run_envelope(doc)
    status = loaded.envelope.status

    run_dir.joinpath("review.json").write_text(json.dumps(doc, indent=2) + "\n")
    # The report a person reads, rendered from the result rebuilt above. The agent's own
    # report.md is built from its own aggregate and is not used; its summary of the change is
    # the only prose taken from it, read as a plain file within a size limit.
    summary = read_regular_file(out_dir / SUMMARY_NAME, MAX_SUMMARY_BYTES)
    summary_text = summary.decode("utf-8", errors="replace") if summary else None
    run_dir.joinpath("report.md").write_text(render_report(doc, summary_text), encoding="utf-8")
    if meta and meta.usage:
        run_dir.joinpath("usage.json").write_text(json.dumps(meta.usage, indent=2) + "\n")
    # Kept so the run can be scored again with other settings once its workspace is gone; ran.json
    # says which sub-agents the rollouts showed, which decides whose files count.
    kept = run_dir / "reviewers"
    copy_reviewer_files(out_dir, kept)
    kept.mkdir(exist_ok=True)
    seen = sorted(ran) if ran is not None else None
    kept.joinpath("ran.json").write_text(json.dumps({"subagents": seen}) + "\n")
    if searches:
        _close_ctx(run_dir, out_dir, store_check)
    manifest = {
        "run_id": run_id, "case": case, "arm": arm, "repeat": 0, "runner": entry.name,
        "model": observed["model"], "effort": observed["effort"],
        "cli_version": observed["cli_version"], "key_version": key_version,
        "store_hash": store_hash, "skills_hash": skills_hash, "snapshot_hash": snapshot_hash,
        "started_at": started, "finished_at": _now(), "status": status,
        "pipeline_digest": pipeline_digest(),
    }  # fmt: skip
    load_manifest(manifest)
    run_dir.joinpath("manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return ReviewResult(
        run_id=run_id, run_dir=run_dir, out_dir=out_dir, status=status, document=doc,
        findings=loaded.findings, exit_code=exit_code, timed_out=timed_out,
        reasons=tuple(reasons), subagents=meta.subagents if meta else (),
    )  # fmt: skip
