"""The runner registry: one TOML entry per agent CLI. Standard library only.

An entry names a command template, environment, how the skills folder is exposed, a
permissions block and the parser that reads run metadata. The launcher knows nothing about a
CLI beyond its entry.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from review_core.launcher.rollout import RolloutActivity, RunMeta, parse_codex_rollout

REGISTRY_PATH = Path(__file__).with_name("runners.toml")
METADATA_PARSERS: dict[str, Callable[[list[dict], dict[str, str]], RunMeta | None]] = {
    "codex_rollout": parse_codex_rollout,
}
# How to tell that a run of this kind is still doing something, keyed like the parsers.
ACTIVITY_READERS: dict[str, Callable[[dict[str, str]], RolloutActivity]] = {
    "codex_rollout": RolloutActivity,
}


# Variables an agent process may inherit from the caller when its entry names no others.
DEFAULT_PASS_ENV = (
    "PATH", "LANG", "LC_ALL", "TERM", "TZ", "SSL_CERT_FILE", "HTTPS_PROXY", "HTTP_PROXY",
    "NO_PROXY",
)  # fmt: skip


class RegistryError(ValueError):
    """A runner entry is missing, incomplete or unusable."""


@dataclass(frozen=True)
class Permissions:
    """What a run may do: sandbox mode, writable folders and whether it has network."""

    sandbox: str
    writable_roots: list[str]
    network: bool


@dataclass(frozen=True)
class RunnerEntry:
    """One agent CLI: command template, environment, skills exposure, permissions, metadata."""

    name: str
    argv: list[str]
    env: dict[str, str]
    pass_env: tuple[str, ...]
    skills_copy_to: str
    permissions: Permissions
    stdin: str
    metadata: str
    # Variables the agent is given a secret under, each mapped to the name the secret is
    # looked up by: in the caller's environment first, then in the run's env file.
    secrets: dict[str, str]
    # Folders the launcher creates before the agent starts, for an agent that will not
    # create them itself (Codex refuses a CODEX_HOME that does not exist).
    make_dirs: tuple[str, ...]

    @property
    def activity(self) -> Callable[[dict[str, str]], RolloutActivity]:
        """Builds this entry's activity reader for one run's environment."""
        return ACTIVITY_READERS[self.metadata]

    @property
    def parser(self) -> Callable[[list[dict], dict[str, str]], RunMeta | None]:
        """The metadata parser this entry names."""
        return METADATA_PARSERS[self.metadata]


def _entry(name: str, raw: dict) -> RunnerEntry:
    """Validate one raw TOML table into a RunnerEntry."""
    perms = raw.get("permissions")
    if not isinstance(perms, dict) or not {"sandbox", "writable_roots", "network"} <= perms.keys():
        raise RegistryError(
            f"runner {name!r}: needs a [permissions] table with sandbox, writable_roots and network"
        )
    argv = raw.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise RegistryError(f"runner {name!r}: argv must be a non-empty list of strings")
    if raw.get("stdin") != "closed":
        raise RegistryError(f'runner {name!r}: stdin must be "closed"')
    metadata = raw.get("metadata")
    if metadata not in METADATA_PARSERS:
        raise RegistryError(f"runner {name!r}: unknown metadata parser {metadata!r}")
    skills = raw.get("skills") or {}
    if "copy_to" not in skills:
        raise RegistryError(f"runner {name!r}: needs [skills] copy_to")
    secrets = raw.get("secrets") or {}
    if not isinstance(secrets, dict) or not all(isinstance(v, str) and v for v in secrets.values()):
        raise RegistryError(f"runner {name!r}: [secrets] maps a variable to the name of its source")
    return RunnerEntry(
        name=name,
        argv=argv,
        env=dict(raw.get("env") or {}),
        pass_env=tuple(raw.get("pass_env") or DEFAULT_PASS_ENV),
        skills_copy_to=skills["copy_to"],
        permissions=Permissions(
            perms["sandbox"], list(perms["writable_roots"]), bool(perms["network"])
        ),
        stdin="closed",
        metadata=metadata,
        secrets=dict(secrets),
        make_dirs=tuple(raw.get("make_dirs") or ()),
    )


def load_registry(path: Path | str | None = None) -> dict[str, RunnerEntry]:
    """Load and validate every entry of a runners.toml; the packaged one when no path is given."""
    with Path(path or REGISTRY_PATH).open("rb") as fh:
        raw = tomllib.load(fh)
    return {name: _entry(name, table) for name, table in raw.items()}


def _from_env_file(path: Path | str | None, name: str) -> str | None:
    """One variable's value from an env file, read line by line and never sourced."""
    if path is None:
        return None
    line_of = re.compile(rf"\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.*?)\s*\Z")
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if found := line_of.match(line):
            value = found.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


def read_secrets(entry: RunnerEntry, env_file: Path | str | None = None) -> dict[str, str]:
    """The secrets an entry's agent needs, by the variable each is given under.

    Looked up before any agent starts, so a run without its key starts none. The values go into
    the agent's environment only: never into a command line, a prompt or a file of the run.
    """
    found: dict[str, str] = {}
    for variable, source in entry.secrets.items():
        value = os.environ.get(source) or _from_env_file(env_file, source)
        if not value:
            where = f"the environment or {env_file}" if env_file else "the environment"
            raise RegistryError(f"runner {entry.name!r} needs {source}, which is not in {where}")
        found[variable] = value
    return found


def agent_env(
    entry: RunnerEntry, ctx: Mapping[str, str], secrets: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The environment one agent process gets: a named few variables, the entry's own, its secrets.

    The folders the entry asks for are made here, so they exist before the agent starts.

    The agent reads untrusted code, so it inherits only what the entry lists, never the
    caller's whole environment.
    """
    for folder in entry.make_dirs:
        Path(folder.format_map(ctx)).mkdir(parents=True, exist_ok=True)
    inherited = {k: os.environ[k] for k in entry.pass_env if k in os.environ}
    return {**inherited, **{k: v.format_map(ctx) for k, v in entry.env.items()}, **(secrets or {})}
