"""Typed loaders for the four contract documents. Standard library only.

The matcher and the aggregator ship inside containers as plain scripts, so nothing here may
import a third-party package. The JSON Schemas next to this file describe the same shapes;
the tests prove the two agree. Rules a schema cannot state are enforced here.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = 1
REVIEWERS = (
    "security",
    "tests",
    "correctness",
    "architecture",
    "code_quality",
    "compliance",
    "language",
)
SIDES = ("new", "old")
SEVERITIES = ("P0", "P1", "P2", "P3")
CONFIDENCES = (0, 25, 50, 75, 100)
SCOPES = ("in_diff", "pre_existing", "out_of_slice")
STATUSES = ("complete", "partial", "failed")
OUTCOMES = (
    "ok",
    "empty",
    "timeout",
    "malformed",
    "rate_limited",
    "auth",
    "spawn_declined",
    "not_run",
)
SUCCESS_OUTCOMES = ("ok", "empty")
DROP_REASONS = (
    "quote_gate",
    "confidence_floor",
    "duplicate",
    "validator_declined",
    "out_of_snapshot",
    "malformed",
)
# A finding that claims more lines than this points at no particular place: it is not matched
# against the key and it is never grouped with a neighbour.
MAX_SPAN = 30
TIERS = (1, 2, 3)
TAGS = ("visible_in_diff", "needs_other_files")
ARMS = ("plain", "vector", "okf", "control")


class ContractError(ValueError):
    """A document breaks its contract; the message names the field and the reason."""


# --- field checks -------------------------------------------------------------------------


def _fields(doc, names: tuple[str, ...], where: str, optional: tuple[str, ...] = ()) -> dict:
    """Require a JSON object with exactly the given keys, plus any of the optional ones."""
    if not isinstance(doc, dict):
        raise ContractError(f"{where}: expected an object")
    missing = [n for n in names if n not in doc]
    extra = [n for n in doc if n not in names and n not in optional]
    if missing:
        raise ContractError(f"{where}: missing field {', '.join(missing)}")
    if extra:
        raise ContractError(f"{where}: unexpected field {', '.join(extra)}")
    return doc


def _str(
    doc: dict, name: str, where: str, *, nullable: bool = False, nonblank: bool = False
) -> str | None:
    """Read a string field, or None when nullable and null."""
    value = doc[name]
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ContractError(f"{where}.{name}: expected a string")
    if nonblank and not value.strip():
        raise ContractError(f"{where}.{name}: must not be blank")
    return value


def _int(doc: dict, name: str, where: str, *, minimum: int = 0) -> int:
    """Read an integer field no smaller than minimum."""
    value = doc[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{where}.{name}: expected an integer")
    if value < minimum:
        raise ContractError(f"{where}.{name}: must be at least {minimum}")
    return value


def _enum(doc: dict, name: str, where: str, allowed: tuple):
    """Read a field that must be one of the allowed values."""
    value = doc[name]
    # Compare by exact type too: 75.0 == 75 and True == 1 must not pass as the integer.
    if type(value) not in {type(a) for a in allowed} or value not in allowed:
        raise ContractError(f"{where}.{name}: {value!r} is not one of {list(allowed)}")
    return value


def _list(doc: dict, name: str, where: str) -> list:
    """Read an array field."""
    value = doc[name]
    if not isinstance(value, list):
        raise ContractError(f"{where}.{name}: expected an array")
    return value


def _version(doc: dict) -> None:
    """Check the schema_version field."""
    value = doc["schema_version"]
    if type(value) is not int or value != SCHEMA_VERSION:
        raise ContractError(f"schema_version: expected {SCHEMA_VERSION}")


# --- findings -----------------------------------------------------------------------------

FINDING_FIELDS = (
    "file", "line_start", "line_end", "side", "quote", "title", "description", "severity",
    "confidence", "category", "reviewer", "scope", "fingerprint",
)  # fmt: skip


@dataclass(frozen=True)
class Finding:
    """One reported problem, anchored to a quote of the offending lines."""

    file: str
    line_start: int
    line_end: int
    side: str
    quote: str
    title: str
    description: str
    severity: str
    confidence: int
    category: str
    reviewer: str
    scope: str
    fingerprint: str | None
    also_raised_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class FindingsDoc:
    """One reviewer's output file."""

    reviewer: str
    findings: tuple[Finding, ...]


def _finding(doc, where: str, *, need_fingerprint: bool) -> Finding:
    """Validate one finding object."""
    final = need_fingerprint  # only the final document's findings name reviewers at their place
    d = _fields(doc, (*FINDING_FIELDS, "also_raised_by") if final else FINDING_FIELDS, where)
    merged = _list(d, "also_raised_by", where) if final else []
    if any(not isinstance(name, str) or name not in REVIEWERS for name in merged):
        raise ContractError(f"{where}.also_raised_by: {merged!r} holds a name that is no reviewer")
    line_start = _int(d, "line_start", where, minimum=1)
    line_end = _int(d, "line_end", where, minimum=1)
    if line_end < line_start:
        raise ContractError(f"{where}.line_end: {line_end} is before line_start {line_start}")
    quote = _str(d, "quote", where)
    if not quote.strip():
        raise ContractError(f"{where}.quote: must not be blank")
    fingerprint = _str(d, "fingerprint", where, nullable=not need_fingerprint)
    return Finding(
        file=_str(d, "file", where, nonblank=True),
        line_start=line_start,
        line_end=line_end,
        side=_enum(d, "side", where, SIDES),
        quote=quote,
        title=_str(d, "title", where),
        description=_str(d, "description", where),
        severity=_enum(d, "severity", where, SEVERITIES),
        confidence=_enum(d, "confidence", where, CONFIDENCES),
        category=_enum(d, "category", where, REVIEWERS),
        reviewer=_enum(d, "reviewer", where, REVIEWERS),
        scope=_enum(d, "scope", where, SCOPES),
        fingerprint=fingerprint,
        also_raised_by=tuple(merged),
    )


def load_findings(doc) -> FindingsDoc:
    """Validate one reviewer's findings document."""
    d = _fields(doc, ("schema_version", "reviewer", "findings"), "findings")
    _version(d)
    items = _list(d, "findings", "findings")
    return FindingsDoc(
        reviewer=_enum(d, "reviewer", "findings", REVIEWERS),
        findings=tuple(
            _finding(item, f"findings[{i}]", need_fingerprint=False) for i, item in enumerate(items)
        ),
    )


def _lower_to_allowed(value):
    """An off-scale confidence from 0 to 100 becomes the allowed value below it, never above."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100:
        return max(c for c in CONFIDENCES if c <= value)
    return value


def salvage_findings(doc, reviewer: str) -> tuple[FindingsDoc, int]:
    """Read a reviewer's file as a model really writes it; return its sound findings and the
    number dropped.

    `load_findings` states the contract. This reader forgives the near misses seen in real
    runs, each in a way that cannot add or strengthen a finding: a missing `schema_version` or
    `reviewer` header (the file's name already says whose it is), and a confidence between two
    allowed values, which is lowered. A finding that still breaks the contract, or is credited
    to another reviewer, is dropped on its own and counted. Raises ContractError when the
    document is not a findings object, or its header contradicts the reviewer or the version.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        raise ContractError("findings: expected an object with a findings list")
    if unknown := set(doc) - {"schema_version", "reviewer", "findings"}:
        raise ContractError(f"findings: unknown field {sorted(unknown)}")
    if "schema_version" in doc:
        _version(doc)
    if doc.get("reviewer", reviewer) != reviewer:
        raise ContractError(f"findings.reviewer: {doc['reviewer']!r} is not {reviewer!r}")
    sound, bad = [], 0
    for i, item in enumerate(doc["findings"]):
        try:
            if isinstance(item, dict) and "confidence" in item:
                item = {**item, "confidence": _lower_to_allowed(item["confidence"])}
            finding = _finding(item, f"findings[{i}]", need_fingerprint=False)
            if finding.reviewer != reviewer:
                raise ContractError(f"findings[{i}].reviewer: not {reviewer!r}")
            sound.append(finding)
        except ContractError:
            bad += 1
    return FindingsDoc(reviewer=reviewer, findings=tuple(sound)), bad


# --- run envelope -------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewerRun:
    """What happened to one planned reviewer."""

    reviewer: str
    outcome: str
    retries: int
    findings_count: int


@dataclass(frozen=True)
class Envelope:
    """Run-level facts: status, per-reviewer outcomes and the agent that produced them."""

    status: str
    reviewers_planned: tuple[str, ...]
    reviewers: tuple[ReviewerRun, ...]
    runner: str
    model: str
    effort: str
    cli_version: str
    sandbox_mode: str
    dropped: dict[str, int]


@dataclass(frozen=True)
class RunEnvelope:
    """The final findings.json of one review run."""

    envelope: Envelope
    findings: tuple[Finding, ...]


def _reviewer_run(doc, where: str) -> ReviewerRun:
    """Validate one per-reviewer outcome row."""
    d = _fields(doc, ("reviewer", "outcome", "retries", "findings_count"), where)
    return ReviewerRun(
        reviewer=_enum(d, "reviewer", where, REVIEWERS),
        outcome=_enum(d, "outcome", where, OUTCOMES),
        retries=_int(d, "retries", where),
        findings_count=_int(d, "findings_count", where),
    )


def _envelope(doc) -> Envelope:
    """Validate the envelope object and its cross-field rules."""
    names = (
        "status", "reviewers_planned", "reviewers", "runner", "model", "effort", "cli_version",
        "sandbox_mode", "dropped",
    )  # fmt: skip
    d = _fields(doc, names, "envelope")
    planned = _list(d, "reviewers_planned", "envelope")
    for name in planned:
        if not isinstance(name, str) or name not in REVIEWERS:
            raise ContractError(f"envelope.reviewers_planned: {name!r} is not a reviewer")
    if not planned or len(set(planned)) != len(planned):
        raise ContractError("envelope.reviewers_planned: needs at least one reviewer, each once")
    runs = tuple(
        _reviewer_run(r, f"envelope.reviewers[{i}]")
        for i, r in enumerate(_list(d, "reviewers", "envelope"))
    )
    # One row per planned reviewer, so a reviewer that never ran cannot simply be absent.
    seen = [r.reviewer for r in runs]
    if unplanned := [name for name in seen if name not in planned]:
        raise ContractError(f"envelope.reviewers: {unplanned} not planned")
    if len(set(seen)) != len(seen):
        raise ContractError("envelope.reviewers: more than one row for a reviewer")
    if missing := [name for name in planned if name not in seen]:
        raise ContractError(f"envelope.reviewers: no row for planned reviewer {missing}")
    dropped = _fields(d["dropped"], DROP_REASONS, "envelope.dropped")
    status = _enum(d, "status", "envelope", STATUSES)
    bad = [f"{r.reviewer}={r.outcome}" for r in runs if r.outcome not in SUCCESS_OUTCOMES]
    if status == "complete" and bad:
        raise ContractError(f"envelope: status complete is inconsistent with outcomes {bad}")
    counts = {k: _int(dropped, k, "envelope.dropped") for k in DROP_REASONS}
    # A finding thrown away for its form is a reviewer's work lost, so the run is not whole.
    if status == "complete" and counts["malformed"]:
        raise ContractError("envelope: status complete is inconsistent with malformed drops")
    return Envelope(
        status=status,
        reviewers_planned=tuple(planned),
        reviewers=runs,
        runner=_str(d, "runner", "envelope"),
        model=_str(d, "model", "envelope"),
        effort=_str(d, "effort", "envelope"),
        cli_version=_str(d, "cli_version", "envelope"),
        sandbox_mode=_str(d, "sandbox_mode", "envelope"),
        dropped=counts,
    )


def load_final_findings(items) -> tuple[Finding, ...]:
    """Validate a list of fingerprinted findings, as candidates and final files carry them."""
    if not isinstance(items, list):
        raise ContractError("findings: expected a list")
    return tuple(
        _finding(item, f"findings[{i}]", need_fingerprint=True) for i, item in enumerate(items)
    )


def load_run_envelope(doc) -> RunEnvelope:
    """Validate a final run file: envelope plus fingerprinted findings."""
    d = _fields(doc, ("schema_version", "envelope", "findings"), "run")
    _version(d)
    envelope = _envelope(d["envelope"])
    findings = tuple(
        _finding(item, f"findings[{i}]", need_fingerprint=True)
        for i, item in enumerate(_list(d, "findings", "run"))
    )
    if envelope.status == "failed" and findings:
        raise ContractError("run: status failed must carry no findings")
    return RunEnvelope(envelope=envelope, findings=findings)


# --- answer key ---------------------------------------------------------------------------

SITE_FIELDS = ("file", "side", "line_start", "line_end", "anchor")
ENTRY_FIELDS = ("id", "case", "tier", "tag", "description", "sites", "fixed_sites")


@dataclass(frozen=True)
class Site:
    """Lines in one file, pinned by an anchor text. Any site satisfies its entry."""

    file: str
    side: str
    line_start: int
    line_end: int
    anchor: str


@dataclass(frozen=True)
class KeyEntry:
    """One known bug."""

    id: str
    case: str
    tier: int
    tag: str
    description: str
    sites: tuple[Site, ...]
    fixed_sites: tuple[Site, ...]


@dataclass(frozen=True)
class Key:
    """A versioned answer key."""

    version: str
    entries: tuple[KeyEntry, ...]


def _site(doc, where: str) -> Site:
    """Validate one site."""
    d = _fields(doc, SITE_FIELDS, where)
    line_start = _int(d, "line_start", where, minimum=1)
    line_end = _int(d, "line_end", where, minimum=1)
    if line_end < line_start:
        raise ContractError(f"{where}.line_end: {line_end} is before line_start {line_start}")
    return Site(
        file=_str(d, "file", where, nonblank=True),
        side=_enum(d, "side", where, SIDES),
        line_start=line_start,
        line_end=line_end,
        anchor=_str(d, "anchor", where),
    )


def _entry(doc, where: str) -> KeyEntry:
    """Validate one key entry."""
    d = _fields(doc, ENTRY_FIELDS, where)
    sites = tuple(_site(s, f"{where}.sites[{i}]") for i, s in enumerate(_list(d, "sites", where)))
    if not sites:
        raise ContractError(f"{where}.sites: an entry needs at least one site")
    fixed = tuple(
        _site(s, f"{where}.fixed_sites[{i}]") for i, s in enumerate(_list(d, "fixed_sites", where))
    )
    return KeyEntry(
        id=_str(d, "id", where, nonblank=True),
        case=_str(d, "case", where, nonblank=True),
        tier=_enum(d, "tier", where, TIERS),
        tag=_enum(d, "tag", where, TAGS),
        description=_str(d, "description", where),
        sites=sites,
        fixed_sites=fixed,
    )


def load_key(doc) -> Key:
    """Validate an answer key."""
    d = _fields(doc, ("version", "entries"), "key")
    entries = tuple(_entry(e, f"entries[{i}]") for i, e in enumerate(_list(d, "entries", "key")))
    ids = [e.id for e in entries]
    if len(set(ids)) != len(ids):
        raise ContractError("key.entries: duplicate entry id")
    return Key(version=_str(d, "version", "key"), entries=entries)


def key_to_dict(key: Key) -> dict:
    """Turn a Key back into the JSON document it was loaded from."""
    return json.loads(
        json.dumps({"version": key.version, "entries": [asdict(e) for e in key.entries]})
    )


def key_hash(key: Key) -> str:
    """Return a sha256 of the key that ignores entry order, site order and JSON key order."""

    def site_order(s: dict):
        return (s["file"], s["side"], s["line_start"], s["line_end"], s["anchor"])

    entries = []
    for e in sorted(key_to_dict(key)["entries"], key=lambda e: e["id"]):
        e["sites"] = sorted(e["sites"], key=site_order)
        e["fixed_sites"] = sorted(e["fixed_sites"], key=site_order)
        entries.append(e)
    canonical = json.dumps(
        {"version": key.version, "entries": entries},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- manifest -----------------------------------------------------------------------------

MANIFEST_FIELDS = (
    "run_id", "case", "arm", "repeat", "runner", "model", "effort", "cli_version", "key_version",
    "store_hash", "skills_hash", "snapshot_hash", "started_at", "finished_at", "status",
)  # fmt: skip


@dataclass(frozen=True)
class Manifest:
    """Identity and settings of one stored run."""

    run_id: str
    case: str
    arm: str
    repeat: int
    runner: str
    model: str
    effort: str
    cli_version: str
    key_version: str
    store_hash: str | None
    skills_hash: str
    snapshot_hash: str
    started_at: str
    finished_at: str
    status: str
    pipeline_digest: str | None = None


def load_manifest(doc) -> Manifest:
    """Validate a run manifest; `pipeline_digest` is optional, absent on older runs."""
    d = _fields(doc, MANIFEST_FIELDS, "manifest", optional=("pipeline_digest",))
    strings = {
        n: _str(d, n, "manifest", nullable=n == "store_hash")
        for n in MANIFEST_FIELDS
        if n not in ("arm", "repeat", "status")
    }
    return Manifest(
        **strings,
        arm=_enum(d, "arm", "manifest", ARMS),
        repeat=_int(d, "repeat", "manifest"),
        status=_enum(d, "status", "manifest", STATUSES),
        pipeline_digest=_str(d, "pipeline_digest", "manifest") if "pipeline_digest" in d else None,
    )


def _reject_constant(name: str):
    """Refuse NaN and Infinity, which Python's parser accepts and JSON does not allow."""
    raise ValueError(f"{name} is not a JSON number")


def read_json(path: Path | str):
    """Parse a JSON file; any unreadable document becomes a ContractError naming the file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        # ValueError covers bad JSON, bad UTF-8 and the constants refused above.
        raise ContractError(f"{path}: not valid JSON ({type(exc).__name__}: {exc})") from exc


class TreeReader:
    """Reads file text from two directory trees: the head tree for side new, the base for old.

    For a caller that exported both trees before anything untrusted ran, so that no git command
    runs afterwards. A path that leaves its tree, through `..` or a link, reads as missing.
    """

    def __init__(self, head_root: Path | str, base_root: Path | str) -> None:
        """Remember the two roots."""
        self.roots = {"new": Path(head_root).resolve(), "old": Path(base_root).resolve()}

    def read(self, side: str, file: str) -> str | None:
        """Return the file's text on that side, or None when it is not a readable file there."""
        root = self.roots[side]
        path = (root / file).resolve()
        if not path.is_relative_to(root):
            return None
        try:
            return path.read_text(errors="replace")
        except OSError:
            return None


def quote_lines(quote: str) -> list[str]:
    """Split quoted code into stripped lines, dropping blank lines at either end."""
    lines = [line.strip() for line in quote.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def locate_quote(text: str, quote: str) -> list[int]:
    """Return the 1-based first line of every place the quote occurs in the text.

    The one rule for finding quoted code: indentation is ignored and the lines must be
    contiguous. The quote gate, the matcher and the answer-key pins all use it, so a finding
    and a key entry that quote the same code land on the same lines.
    """
    wanted = quote_lines(quote)
    if not wanted:
        return []
    lines = [line.strip() for line in text.splitlines()]
    n = len(wanted)
    return [i + 1 for i in range(len(lines) - n + 1) if lines[i : i + n] == wanted]


def safe_relpath(path: str) -> str | None:
    """Normalise a repo-relative POSIX path, or return None if it is absolute or escapes."""
    if not path or path.startswith("/") or "\\" in path or "\0" in path:
        return None
    normal = posixpath.normpath(path)
    if normal == "." or normal == ".." or normal.startswith("../"):
        return None
    return normal
