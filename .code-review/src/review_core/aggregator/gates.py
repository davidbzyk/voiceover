"""The path gate and the quote gate.

A finding must name a path inside the snapshot and quote lines that exist in the file on its
side: the head commit for `new`, the base commit for `old`. Files are read from git objects,
never from the working tree.

A finding's line range is then taken from where its quote is, not from what the reviewer
claimed. Everything after this point acts on lines (merging, verdicts, where a comment is
posted), so the lines must be the ones the gate checked. A claimed range is only a hint that
picks between two places the same quote occurs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

from review_core.contracts.models import locate_quote, quote_lines, safe_relpath


def quote_in_text(quote: str, text: str) -> bool:
    """True when the quote occurs in the text, by the shared rule in `locate_quote`."""
    return bool(locate_quote(text, quote))


# Variables that point git at a repository other than the one named with -C.
REPO_REDIRECTS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX",
)  # fmt: skip


COMMIT_ID = re.compile(r"[0-9a-f]{40}")


def _git_env() -> dict[str, str]:
    """The environment for a git read: nothing that redirects it, and no replacement objects.

    A caller such as a git hook exports GIT_DIR, which would send the read to its repository.
    `git replace` lets anyone who can write the repository serve other content for an object
    id, so replacement is switched off: an id then means its own content.
    """
    env = {k: v for k, v in os.environ.items() if k not in REPO_REDIRECTS}
    return {**env, "GIT_NO_REPLACE_OBJECTS": "1"}


def _git(repo: Path | str, *args: str) -> subprocess.CompletedProcess:
    """Run git with an argument list in the repository; never through a shell."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False, env=_git_env()
    )


def resolve_commit(repo: Path | str, ref: str) -> str | None:
    """The commit id a ref names, or None; a ref that looks like an option is refused.

    A caller that does not trust later changes to the repository resolves its refs once, before
    anything untrusted runs, and reads by commit id from then on.
    """
    if not ref or ref.startswith("-"):
        return None
    done = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return done.stdout.decode().strip() if done.returncode == 0 else None


def ref_exists(repo: Path | str, ref: str) -> bool:
    """True when ref names a commit."""
    return resolve_commit(repo, ref) is not None


def _list_tree(repo: Path | str, commit: str) -> list[tuple[str, str, str, str]]:
    """Every entry of a commit's tree as (mode, kind, object id, path), read from git."""
    if not COMMIT_ID.fullmatch(commit):
        raise ValueError("expected a full 40-character commit id")
    listing = _git(repo, "ls-tree", "-r", "-z", commit)
    if listing.returncode != 0:
        raise ValueError(f"cannot list commit {commit[:12]} in {repo}")
    entries = []
    for record in listing.stdout.split(b"\0"):
        if record:
            meta, _, raw = record.partition(b"\t")
            mode, kind, sha = meta.decode().split()
            entries.append((mode, kind, sha, raw.decode("utf-8", errors="surrogateescape")))
    return entries


def _write_objects(repo: Path | str, wanted: list[tuple[str, Path, int]], scratch: Path) -> None:
    """Write each (object id, target, file mode) from the repository, one object at a time.

    The ids go to git through a file and each object is streamed to its target, so nothing
    larger than one read is held in memory.
    """
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("".join(f"{sha}\n" for sha, _, _ in wanted))
    try:
        with scratch.open("rb") as ids:
            proc = subprocess.Popen(
                ["git", "-C", str(repo), "cat-file", "--batch"],
                stdin=ids, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_git_env(),
            )  # fmt: skip
            assert proc.stdout is not None
            for sha, target, mode in wanted:
                header = proc.stdout.readline().split()
                if len(header) != 3 or header[0].decode() != sha or header[1] != b"blob":
                    proc.kill()
                    raise ValueError(f"object {sha[:12]} is missing from {repo}")
                target.parent.mkdir(parents=True, exist_ok=True)
                remaining = int(header[2])
                with target.open("wb") as out:
                    while remaining:
                        chunk = proc.stdout.read(min(remaining, 1 << 20))
                        if not chunk:
                            proc.kill()
                            raise ValueError(f"object {sha[:12]} ended early")
                        out.write(chunk)
                        remaining -= len(chunk)
                proc.stdout.read(1)  # the newline git writes after each object
                target.chmod(mode)
            proc.stdout.close()
            proc.wait()
    finally:
        scratch.unlink(missing_ok=True)


def export_commit(repo: Path | str, commit: str, dest: Path | str, skip=None) -> list[str]:
    """Write every regular file of a commit as a directory tree; return the entries left out.

    Left out and returned, sorted: symbolic links and submodule entries. Left out and not
    returned: paths for which `skip(path)` is true. Files are read as objects, so nothing the
    tree says about exporting (an `export-ignore` attribute) can remove a file. Two paths that
    would land on one name on a case-insensitive disk are refused: a tree on disk cannot hold
    both, and writing one over the other would hide a file without a word.
    """
    dest = Path(dest)
    wanted: list[tuple[str, Path, int]] = []
    left_out: list[str] = []
    taken: dict[str, str] = {}
    for mode, kind, sha, path in _list_tree(repo, commit):
        rel = safe_relpath(path)
        if rel is None or any(part.lower() == ".git" for part in rel.split("/")):
            raise ValueError(f"unsafe path or git metadata in commit: {path!r}")
        if skip is not None and skip(rel):
            continue
        if kind != "blob" or mode == "120000":
            left_out.append(rel)
            continue
        folded = unicodedata.normalize("NFC", rel).casefold()
        if folded in taken:
            raise ValueError(
                f"paths collide on a case-insensitive disk: {taken[folded]!r}, {rel!r}"
            )
        taken[folded] = rel
        wanted.append((sha, dest / rel, 0o755 if mode == "100755" else 0o644))
    dest.mkdir(parents=True, exist_ok=True)
    _write_objects(repo, wanted, dest.parent / f".{dest.name}.objects")
    return sorted(left_out)


def export_blobs(repo: Path | str, commit: str, dest: Path | str) -> None:
    """Copy a commit's files out as objects plus an index of exact path to object id.

    Unlike a directory tree this cannot lose or confuse a file: names on disk are object ids,
    and a path is looked up as the exact string git recorded, so letter case, Unicode forms and
    odd characters in a path mean what they mean in the commit and nothing else.
    """
    dest = Path(dest)
    index = _blob_index(_list_tree(repo, commit))
    objects = dest / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    wanted = [(sha, objects / sha, 0o644) for sha in sorted(set(index.values()))]
    _write_objects(repo, wanted, dest / "wanted.txt")
    (dest / "index.json").write_text(json.dumps(index, sort_keys=True), encoding="utf-8")


class _IndexedReader:
    """A reader that knows every path of two commits and finds a cited path among them.

    A path is found by its exact spelling. Failing that, it is found by its Unicode form when
    exactly one path in the commit has that form: a file name stored with a combining accent
    is usually cited with the composed letter, and the difference cannot be seen. Letter case is
    never forgiven, because git itself tells such paths apart.
    """

    def __init__(self) -> None:
        """Start with no index loaded."""
        self._index: dict[str, dict[str, str]] = {}
        self._forms: dict[str, dict[str, list[str]]] = {}

    def _load(self, side: str) -> dict[str, str]:
        """Return path to object id for a side. Subclasses supply it."""
        raise NotImplementedError

    def _text(self, side: str, sha: str) -> str | None:
        """Return an object's text. Subclasses supply it."""
        raise NotImplementedError

    def _paths(self, side: str) -> dict[str, str]:
        """The side's index, loaded once, with its paths grouped by Unicode form."""
        if side not in self._index:
            index = self._load(side)
            forms: dict[str, list[str]] = {}
            for path in index:
                forms.setdefault(unicodedata.normalize("NFC", path), []).append(path)
            self._index[side], self._forms[side] = index, forms
        return self._index[side]

    def find(self, side: str, file: str) -> str | None:
        """Return the path as the commit spells it, or None when it has no such file."""
        if file in self._paths(side):
            return file
        same_form = self._forms[side].get(unicodedata.normalize("NFC", file), [])
        return same_form[0] if len(same_form) == 1 else None

    def read(self, side: str, file: str) -> str | None:
        """Return the file's text on that side, or None when the commit has no such path."""
        found = self.find(side, file)
        return self._text(side, self._index[side][found]) if found is not None else None


def _blob_index(entries: list[tuple[str, str, str, str]]) -> dict[str, str]:
    """Path to object id for the regular files of a tree listing; links are not files."""
    return {path: sha for mode, kind, sha, path in entries if kind == "blob" and mode != "120000"}


class BlobReader(_IndexedReader):
    """Reads file text from two `export_blobs` folders: head for side new, base for side old.

    For a caller that copied both commits out before anything untrusted ran, so that no git
    command and no path on disk chosen by a reviewer is used afterwards.
    """

    def __init__(self, head_dir: Path | str, base_dir: Path | str) -> None:
        """Remember the two folders."""
        super().__init__()
        self.dirs = {"new": Path(head_dir), "old": Path(base_dir)}

    def _load(self, side: str) -> dict[str, str]:
        """Read the side's index file."""
        return json.loads((self.dirs[side] / "index.json").read_text(encoding="utf-8"))

    def _text(self, side: str, sha: str) -> str | None:
        """Read one copied object."""
        if not COMMIT_ID.fullmatch(sha):
            return None
        try:
            return (self.dirs[side] / "objects" / sha).read_text(errors="replace")
        except OSError:
            return None


class GitReader(_IndexedReader):
    """Reads file text from git objects at the head (side new) or base (side old) commit."""

    def __init__(self, repo: Path | str, base: str, head: str) -> None:
        """Remember the repository and the two refs."""
        super().__init__()
        self.repo = repo
        self.refs = {"new": head, "old": base}
        self._cache: dict[str, str | None] = {}

    def _load(self, side: str) -> dict[str, str]:
        """List the commit's files; a ref that names no commit has none."""
        commit = resolve_commit(self.repo, self.refs[side])
        return _blob_index(_list_tree(self.repo, commit)) if commit else {}

    def _text(self, side: str, sha: str) -> str | None:
        """Read one object by id."""
        if sha not in self._cache:
            done = _git(self.repo, "cat-file", "blob", sha)
            text = done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None
            self._cache[sha] = text
        return self._cache[sha]


# A reader of either kind. Both come from one base, which is the type callers name.
Reader = _IndexedReader


def apply_path_and_quote_gates(
    findings: list[dict], reader: Reader
) -> tuple[list[dict], list[dict]]:
    """Return (kept, dropped). A dropped item carries `reason`: out_of_snapshot or quote_gate.

    Kept findings use the path as the commit spells it and the line range of their quote: the
    place the quote occurs, or the occurrence nearest the claimed start when there are several.
    The fingerprint is left as the reviewer file gave it.
    """
    kept, dropped = [], []
    for finding in findings:
        path = safe_relpath(finding["file"])
        if path is None:
            dropped.append({**finding, "reason": "out_of_snapshot"})
            continue
        item = {**finding, "file": path}
        found = reader.find(item["side"], path)
        text = reader.read(item["side"], found) if found is not None else None
        hits = locate_quote(text, item["quote"]) if text is not None else []
        if not hits:
            dropped.append({**item, "reason": "quote_gate"})
            continue
        start = min(hits, key=lambda h: (abs(h - item["line_start"]), h))
        item["file"] = found
        item["line_start"] = start
        item["line_end"] = start + len(quote_lines(item["quote"])) - 1
        kept.append(item)
    return kept, dropped
