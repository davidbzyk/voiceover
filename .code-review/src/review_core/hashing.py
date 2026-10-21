"""Content hashes of files and directory trees. Standard library only."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Hex sha256 of one file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_files(root: Path) -> dict[str, Path]:
    """Map repo-relative POSIX path to file path for every regular file under root.

    A symbolic link is not a file of the tree: its target may lie anywhere on disk.
    """
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def tree_sha256(root: Path) -> str:
    """Content hash of a tree: sha256 over sorted `path NUL size LF bytes` records."""
    digest = hashlib.sha256()
    for rel, path in tree_files(root).items():
        digest.update(f"{rel}\0{path.stat().st_size}\n".encode())
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()
