"""One digest over every file of the review pipeline, so any change makes old results stale.

The files are named by `pipeline.toml` beside this module (decision 87). Standard library only.
"""

from __future__ import annotations

import hashlib
import tomllib
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("pipeline.toml")


def load_config(path: Path | None = None) -> dict:
    """The include and exclude lists of a pipeline config."""
    raw = tomllib.loads((path or CONFIG).read_text(encoding="utf-8"))
    return {
        "include": list(raw.get("include", [])),
        "exclude_names": set(raw.get("exclude_names", [])),
        "exclude_suffixes": tuple(raw.get("exclude_suffixes", [])),
        "exclude_paths": set(raw.get("exclude_paths", [])),
    }


def pipeline_files(root: Path | None = None, config: Path | None = None) -> list[str]:
    """Repository-relative POSIX paths of the pipeline's files, sorted."""
    root = (root or ROOT).resolve()
    c = load_config(config)
    found: set[str] = set()
    for pattern in c["include"]:
        base = pattern[:-3] if pattern.endswith("/**") else pattern
        target = root / base
        candidates = target.rglob("*") if pattern.endswith("/**") else root.glob(pattern)
        for path in candidates:
            rel = path.relative_to(root).as_posix()
            if (
                not path.is_file()
                or path.is_symlink()
                or rel in c["exclude_paths"]
                or rel.endswith(c["exclude_suffixes"])
                or any(part in c["exclude_names"] for part in Path(rel).parts)
                or not (fnmatch(rel, pattern) or pattern.endswith("/**"))
            ):
                continue
            found.add(rel)
    return sorted(found)


def pipeline_digest(root: Path | None = None, config: Path | None = None) -> str:
    """Hex sha256 over `path NUL size LF bytes` of every pipeline file."""
    root = (root or ROOT).resolve()
    digest = hashlib.sha256()
    for rel in pipeline_files(root, config):
        data = (root / rel).read_bytes()
        digest.update(f"{rel}\0{len(data)}\n".encode())
        digest.update(data)
    return digest.hexdigest()
