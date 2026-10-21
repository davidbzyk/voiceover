"""What a review run is told and given: the prompt, the `ctx` wrapper text and the search record.

Nothing here starts a process, reads a rollout or knows a runner. The launcher and the Harbor
task generator both use it, so a task's instruction and wrapper cannot drift from a launcher run's.
"""

from __future__ import annotations

import json
import os
import shlex
import stat
from collections.abc import Sequence
from pathlib import Path
from string import Template

from review_core.context.providers import CTX_HELP
from review_core.contracts.models import REVIEWERS, safe_relpath
from review_core.envelope import MAX_REVIEWER_FILE_BYTES

# The search command's call log, written beside the findings.
CTX_LOG_NAME = "ctx-log.jsonl"
# Scratch space for the search command's database, inside the folder the agent may write.
# The launcher only names it; it creates and deletes nothing there.
CTX_SCRATCH_NAME = "ctx-scratch"
# The call log is written where the agent can write, so it is read with a size limit.
MAX_CTX_LOG_BYTES = 20_000_000
# Where the repository is when the agent starts in it.
WHERE_HERE = "in the current directory"
PROMPT = Path(__file__).with_name("prompt.md")
VERDICTS_NAME = "validation.json"


def prompt_extras(
    slice_paths: Sequence[str] | None,
    task_text: str | None,
    context_command: str | None,
    method: str | None = None,
    prior_review: str | None = None,
) -> list[str]:
    """The optional prompt lines the orchestrator passes on to reviewers; `method` is the arm's
    way of gathering context, `prior_review` the file of this pull request's earlier findings."""
    lines = []
    if slice_paths is not None:
        paths = [safe_relpath(p) for p in slice_paths]
        if not paths or any(p is None or "\n" in p for p in paths):
            raise ValueError("a slice needs at least one path, each inside the repository")
        lines.append("Your slice is only these files: " + ", ".join(paths))
    if task_text and task_text.strip():
        lines.append("What the change is meant to do: " + " ".join(task_text.split()))
    if method and method.strip():
        lines.append("How to gather context: " + " ".join(method.split()))
    if context_command and context_command.strip():
        lines.append("Context search command: " + " ".join(context_command.split()))
    if prior_review:
        if "\n" in prior_review:
            raise ValueError("the earlier review's path must be one line")
        lines.append(
            f"Earlier review of this pull request: read {prior_review} to its last line after"
            " your skill file (if output is truncated, read the missing lines by line range)."
            " A finding it marks resolved or answered is settled, and a reply there explains"
            " why: report it again only if the lines it names changed since, and say what"
            " changed. An outdated one sat on lines that have since changed: report it only if"
            " the problem is still there. Do not report an open one again in other words."
            " Report any new problem as usual."
        )
    return lines


# The two commands an agent types are names on its PATH, never paths. A model retyping a long
# path gets it wrong often enough to lose the last step of a run.
AGGREGATE_COMMAND = "review-aggregate"
CTX_COMMAND = "ctx"  # the name the usage text in the prompt already uses


def context_command(wrapper: Path | str = CTX_COMMAND) -> str:
    """The search command line the prompt names: the command, a dot, then the usage text."""
    return f"{wrapper} . {CTX_HELP}"


def repository_location(repo: Path | str, start: Path | str) -> str:
    """Where the repository is, as the prompt says it, from the folder the agent starts in."""
    rel = Path(os.path.relpath(repo, start)).as_posix()
    return WHERE_HERE if rel == "." else f"in the folder `{rel}`"


def render_prompt(
    base: str,
    head: str,
    out_dir: Path | str,
    skills: Path | str,
    extras: list[str],
    aggregate: str = AGGREGATE_COMMAND,
    where: str = WHERE_HERE,
) -> str:
    """The full prompt: the template filled in, then one line per extra, newline-terminated.

    `where` says where the repository is from the agent's start folder.
    """
    prompt = Template(PROMPT.read_text()).substitute(
        base=base, head=head, out_dir=out_dir, aggregate=aggregate, skills=skills, where=where
    )
    return prompt.rstrip("\n") + "".join(f"\n{line}" for line in extras) + "\n"


def aggregate_wrapper_text(python: str, script: Path | str) -> str:
    """The text of the `review-aggregate` command: the interpreter and the skill's script."""
    return f'#!/bin/sh\nexec {shlex.quote(python)} {shlex.quote(str(script))} "$@"\n'


def ctx_wrapper_text(
    python: str,
    src: Path | str,
    store: Path | str,
    log: Path | str,
    scratch: Path | str,
    env_file: Path | str | None,
    key_from: str | None = None,
) -> str:
    """The text of the run's `ctx` command: one executable that needs no flag from the reviewer.

    It pins the store, the interpreter and the import path through the environment, which the
    command line cannot override. Every variable the command reads is set or cleared here: the
    reviewer starts the wrapper, so one left to the caller's environment would be the
    reviewer's to choose. `key_from` names a variable whose value becomes the embedder key
    inside the wrapper only, so the agent's own process never carries a variable of that name.
    """
    lines = [
        "#!/bin/sh",
        f"export PYTHONPATH={shlex.quote(str(src))}",
        f"export CTX_STORE={shlex.quote(str(store))}",
        f"export CTX_LOG={shlex.quote(str(log))}",
        f"export CONTEXT_ENGINE_SCRATCH={shlex.quote(str(scratch))}",
    ]
    if env_file is None:
        lines.append("unset CTX_ENV_FILE")
    else:
        lines.append(f"export CTX_ENV_FILE={shlex.quote(str(Path(env_file).resolve()))}")
    if key_from:
        lines.append(f'export OPENAI_API_KEY="${key_from}"')
    # -P: the command runs in the project under review, whose files must never load as modules.
    lines.append(f'exec {shlex.quote(python)} -P -m review_core.context.ctx "$@"')
    return "\n".join(lines) + "\n"


def summarise_ctx_log(log: Path) -> dict[str, int | str]:
    """Count the search calls of a run: all, failed, degraded, and answered with nothing.

    A run whose store never answered is not a run of that arm, and only this record shows it.
    `log` is "read", "missing" (no call was made) or "unreadable"; a line that is not a call
    record counts as a failed call. Never raises: the log's content is not ours.
    """
    # The log is written by the search command inside the agent's sandbox, so the agent can
    # edit it. This record is what the run reported about itself, not evidence against a run
    # that set out to hide failed calls; nothing outside the sandbox sees a call being made.
    counts: dict[str, int | str] = {
        "log": "read",
        "calls": 0,
        "failed": 0,
        "degraded": 0,
        "empty": 0,
    }
    # One open, without following a link; the type and size checks and the read all use that
    # descriptor, so the file cannot be swapped or grown between the check and the read.
    try:
        fd = os.open(log, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {**counts, "log": "missing"}
    except OSError:
        return {**counts, "log": "unreadable"}
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return {**counts, "log": "unreadable"}
        with os.fdopen(os.dup(fd), "rb") as handle:
            data = handle.read(MAX_CTX_LOG_BYTES + 1)
    except OSError:
        return {**counts, "log": "unreadable"}
    finally:
        os.close(fd)
    if len(data) > MAX_CTX_LOG_BYTES:
        return {**counts, "log": "unreadable"}
    lines = data.decode("utf-8", errors="replace").splitlines()
    for line in lines:
        counts["calls"] += 1
        try:
            row = json.loads(line)
            ok = row["exit_code"] == 0 and isinstance(row["exit_code"], int)
            degraded, empty = bool(row["degraded"]), not row["item_ids"]
        except (ValueError, KeyError, TypeError, RecursionError):
            ok, degraded, empty = False, False, False
        counts["failed"] += not ok
        counts["degraded"] += ok and degraded
        counts["empty"] += ok and empty
    return counts


def reviewer_file_names() -> tuple[str, ...]:
    """The raw files a run keeps: seven findings files, the validator's verdicts, the search log."""
    return (*(f"findings.{r}.json" for r in REVIEWERS), VERDICTS_NAME, CTX_LOG_NAME)


def read_regular_file(path: Path, limit: int) -> bytes | None:
    """The bytes of a regular file of at most `limit` bytes, read without following a link.

    One open serves the type check, the size check and the read, so the file cannot be swapped
    between them. None when the file is missing, is anything but a plain file, or is too big.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with os.fdopen(os.dup(fd), "rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    return data if len(data) <= limit else None


def copy_reviewer_files(out_dir: Path | str, dest: Path | str) -> tuple[str, ...]:
    """Copy the reviewers' raw files from a review's output folder into `dest`; return the names.

    The output folder is where the agent can write, so a link, a folder, a pipe or a file over
    its size limit in place of a named file is skipped, and nothing else in the folder is read.
    The copy is what lets a stored run be scored again once its workspace is gone.
    """
    out = Path(out_dir)
    if out.is_symlink() or not out.is_dir():
        return ()
    kept: list[str] = []
    dest = Path(dest)
    for name in reviewer_file_names():
        limit = MAX_CTX_LOG_BYTES if name == CTX_LOG_NAME else MAX_REVIEWER_FILE_BYTES
        data = read_regular_file(out / name, limit)
        if data is None:
            continue
        dest.mkdir(parents=True, exist_ok=True)
        (dest / name).write_bytes(data)
        kept.append(name)
    return tuple(kept)
