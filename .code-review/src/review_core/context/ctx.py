"""The `ctx` command: `ctx search "<text>"` and `ctx related <path>` over one context store.

The provider comes from the store's manifest and must be a row of the packaged registry; nothing
in the store names code to run. Every call, success or not, appends one line to a JSON log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from review_core.context.providers import (
    CTX_NOTICE,
    Registry,
    StoreError,
    clean_field,
    load_registry,
    read_bounded,
    resolve,
)

CHARS_PER_TOKEN = 3
MAX_MANIFEST_BYTES = 1_000_000
MAX_ARGUMENT = 2000
MAX_ITEMS = 100
MAX_LOGGED_IDS = 50
DEFAULT_LOG = Path(".review") / "ctx-log.jsonl"
ITEM_KEYS = {"id": str, "title": str, "path": str, "start": int, "end": int, "text": str}


# Set by the launcher's wrapper. A pinned call takes its store and log from here and refuses
# the matching flags: the caller is the reviewer, and an arm must only see its own store.
PIN_STORE, PIN_LOG, PIN_ENV_FILE = "CTX_STORE", "CTX_LOG", "CTX_ENV_FILE"
KEY_LINE = re.compile(r"\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*?)\s*\Z")


def key_from_env_file(path: Path | str) -> None:
    """Set OPENAI_API_KEY from an env file when it is not already set; read no other variable.

    The file is parsed line by line and never sourced, so nothing else in it reaches this
    process. A missing or unreadable file is left alone: the search then degrades and says so.
    """
    if os.environ.get("OPENAI_API_KEY"):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if found := KEY_LINE.match(line.rstrip("\n")):
                    value = found.group(1)
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    if value:
                        os.environ["OPENAI_API_KEY"] = value
                    return
    except OSError:
        return


class CallError(Exception):
    """The provider failed or answered badly; the exit code is 1."""


def estimate_tokens(text: str) -> int:
    """Estimated tokens of `text` for every provider: its length over three, rounded up."""
    return -(-len(text) // CHARS_PER_TOKEN)


def _one_line(text: Any) -> str:
    """Collapse whitespace so a message stays on one line."""
    return " ".join(str(text).split())


def _header(n: int, item: dict[str, Any]) -> str:
    """The one-line header: path and lines for code, `note <id>` for an item with no lines."""
    title = clean_field(item["title"])
    if item["start"] == 0 and item["end"] == 0:
        head = f"[{n}] note {clean_field(item['id'])}"
    else:
        head = f"[{n}] {clean_field(item['path'])}:{item['start']}-{item['end']}"
    return f"{head}  {title}" if title else head


def fit_items(items: list[dict[str, Any]], budget: int | None) -> list[str]:
    """The text of each item that fits, in order, so the estimate of the texts is within budget.

    With no budget (None) every item is returned whole. Only item text counts. The first item
    is always kept; alone over budget, it is cut after
    its last whole line that fits. Nothing is added to fill the budget.
    """
    if budget is None:
        return [item["text"].rstrip() for item in items]
    texts: list[str] = []
    for item in items:
        text = item["text"].rstrip()
        if estimate_tokens("\n".join([*texts, text])) <= budget:
            texts.append(text)
            continue
        if not texts:
            kept: list[str] = []
            for line in text.splitlines():
                if estimate_tokens("\n".join([*kept, line])) > budget:
                    break
                kept.append(line)
            texts.append("\n".join(kept))
        break
    return texts


def render_items(items: list[dict[str, Any]], texts: list[str], avoid: tuple[str, ...] = ()) -> str:
    """Headers, then each text between marker lines carrying a boundary token fresh per call.

    The token occurs in no header, text or `avoid` line (the summary line).
    """
    headers = [_header(n, item) for n, item in enumerate(items[: len(texts)], 1)]
    while True:
        token = secrets.token_hex(6)
        if not any(token in part for part in (*headers, *texts, *avoid)):
            break
    blocks = []
    for n, (header, text) in enumerate(zip(headers, texts, strict=True), 1):
        lines = [header, f"<<<item {n} boundary={token}"]
        lines += [text] if text else []
        lines.append(f">>>end {n} boundary={token}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _status(shown: int, total: int, tokens: int, result: dict[str, Any], cut: bool) -> str:
    """The first output line: how many items, the estimate, and anything the reader must know."""
    noun = "item" if shown == 1 else "items"
    parts = [f"{shown} {noun}, ~{tokens} tokens"]
    reason = clean_field(result["reason"]) if result["reason"] else ""
    if result["degraded"]:
        parts.append(f"keyword-only: {reason or 'unspecified'}")
    elif reason:
        parts.append(reason)
    if cut:
        left = total - shown
        parts.append("cut to fit the budget" + (f" ({left} more not shown)" if left else ""))
    return "; ".join(parts)


def _check_result(result: Any) -> dict[str, Any]:
    """Refuse a provider answer that is not the shared shape."""
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise CallError("the provider answered in an unknown shape")
    for item in result["items"]:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), kind) or isinstance(item.get(key), bool)
            for key, kind in ITEM_KEYS.items()
        ):
            raise CallError("the provider returned an item without the shared fields")
    reason = result.get("reason")
    return {
        "items": result["items"][:MAX_ITEMS],
        "degraded": bool(result.get("degraded")),
        "reason": reason if isinstance(reason, str) else None,
    }


def _read_manifest(store: Path) -> dict[str, Any]:
    """The store's manifest as a dict; the store and the manifest must not be links."""
    if store.is_symlink() or not store.is_dir():
        raise StoreError(f"there is no plain store folder at {clean_field(store)!r}")
    try:
        manifest = json.loads(read_bounded(store / "manifest.json", MAX_MANIFEST_BYTES))
    except ValueError:
        raise StoreError("the store manifest is not valid JSON") from None
    if not isinstance(manifest, dict):
        raise StoreError("the store manifest is not a JSON object")
    return manifest


def _provider_name(manifest: dict[str, Any], registry: Registry) -> str:
    """The provider the manifest names; it must be a plain row name with a command."""
    name = manifest.get("provider")
    row = registry.providers.get(name) if isinstance(name, str) else None
    if row is None or not row.command:
        raise StoreError(f"the manifest names a provider with no command: {_one_line(name)!r}")
    return row.name


def _answer(
    store: Path, verb: str, argument: str, budget: int, registry: Registry, record: dict[str, Any]
) -> str:
    """Run one call; fills `record` as it learns things and returns the text to print."""
    if len(argument) > MAX_ARGUMENT:
        raise StoreError(f"the argument is longer than {MAX_ARGUMENT} characters")
    manifest = _read_manifest(store)
    record["store_sha256"] = manifest.get("store_sha256")
    record["provider"] = name = _provider_name(manifest, registry)
    row = registry.providers[name]
    try:
        func = resolve(row.search if verb == "search" else row.related)
        result = _check_result(func(store, argument, row.settings))
    except (CallError, StoreError):
        raise
    except BaseException as exc:  # a provider may exit() too; neither takes ctx down unlogged
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise CallError(
            f"the {name} provider failed: {clean_field(exc) or type(exc).__name__}"
        ) from None
    texts = fit_items(result["items"], budget)
    tokens = estimate_tokens("\n".join(texts))
    shown = len(texts)
    first = result["items"][0] if result["items"] else None
    cut = shown < len(result["items"]) or (first is not None and texts[0] != first["text"].rstrip())
    status = _status(shown, len(result["items"]), tokens, result, cut)
    record.update(
        item_ids=[clean_field(i["id"]) for i in result["items"][: min(shown, MAX_LOGGED_IDS)]],
        item_count=shown,
        tokens=tokens,
        degraded=result["degraded"],
        reason=clean_field(result["reason"]) if result["reason"] else None,
        cut=cut,
    )
    body = render_items(result["items"], texts, (status,))
    return f"{CTX_NOTICE}\n{status}" + ("\n" + body if body else "") + "\n"


def _append_log(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON line with a single write call, safe for several callers at once.

    The log sits in the project under review, which may ship a link where the folder or the
    file should be. Neither is followed: OSError is raised and nothing is written.
    """
    line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    folder = path.parent
    if folder.is_symlink():
        raise OSError(f"{folder} is a symbolic link")
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{path} is not a regular file")
        os.write(fd, line)
    finally:
        os.close(fd)


# Any words do: the check is that the store answers in full, not what it answers.
CHECK_TEXT = "where the program starts"


def _check(
    store: Path, path: str, budget: int, registry: Registry, refused: str, out: TextIO, err: TextIO
) -> int:
    """Answer `ctx check`: one search, and one related lookup when a path is given.

    Run before an agent is started against the store. It passes only when every call answers
    and none in a reduced way; it is not written to the log, which records the reviewers' calls.
    """
    done: list[str] = []
    code, message = 0, ""
    try:
        if refused:
            raise StoreError(refused)
        for verb, argument in [("search", CHECK_TEXT)] + ([("related", path)] if path else []):
            record: dict[str, Any] = {}
            _answer(store, verb, argument, budget, registry, record)
            if record.get("degraded"):
                why = record.get("reason") or "no reason given"
                raise CallError(f"{verb} answered in a reduced way ({why})")
            done.append(f"{verb} {record.get('item_count', 0)} items")
    except StoreError as exc:
        code, message = 2, str(exc)
    except CallError as exc:
        code, message = 1, str(exc)
    if message:
        print(f"ctx: check failed: {clean_field(message, 400)}", file=err)
    else:
        out.write(f"ctx check: ok ({', '.join(done)})\n")
    return code


def main(
    argv: list[str] | None = None,
    *,
    registry: Registry | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one ctx call; returns the exit code (0 ok, 1 provider failed, 2 store unusable)."""
    out, err = stdout or sys.stdout, stderr or sys.stderr
    registry = registry or load_registry()
    # The flags are read first, wherever they stand; what is left is the verb and its argument.
    flags = argparse.ArgumentParser(prog="ctx", allow_abbrev=False)
    flags.add_argument("--store", type=Path)
    flags.add_argument("--budget", type=int)
    flags.add_argument("--log", type=Path)
    parser = flags
    args, rest = flags.parse_known_args(argv)
    verbs = argparse.ArgumentParser(prog="ctx")
    sub = verbs.add_subparsers(dest="verb", required=True)
    sub.add_parser("search").add_argument("argument", metavar="text")
    sub.add_parser("related").add_argument("argument", metavar="path")
    sub.add_parser("check").add_argument("argument", metavar="path", nargs="?", default="")
    args = argparse.Namespace(**vars(args), **vars(verbs.parse_args(rest)))
    pinned = os.environ.get(PIN_STORE)
    refused = ""
    if pinned:
        if args.store is not None or args.log is not None:
            refused = "the store and the log are pinned for this run; --store and --log are refused"
        args.store = Path(pinned)
        args.log = Path(os.environ[PIN_LOG]) if os.environ.get(PIN_LOG) else None
        if os.environ.get(PIN_ENV_FILE):
            key_from_env_file(os.environ[PIN_ENV_FILE])
    if args.store is None:
        parser.error("--store is required")
    if args.budget is not None and args.budget < 0:
        parser.error("--budget must not be negative")
    requested = args.budget
    # No cap unless the registry sets one; then a caller may lower it, never raise it.
    cap = registry.budget_tokens
    budget = requested if cap is None else (cap if requested is None else min(requested, cap))
    args.budget = budget
    if args.verb == "check":
        return _check(args.store, args.argument, budget, registry, refused, out, err)
    started = time.monotonic()
    record: dict[str, Any] = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "verb": args.verb,
        "argument": args.argument[:MAX_ARGUMENT],
        "provider": None,
        "store_sha256": None,
        "item_ids": [],
        "tokens": 0,
        "degraded": False,
        "reason": None,
        "budget": budget,
        "budget_requested": requested,
        "cut": False,
    }
    code, text, message = 0, "", ""
    try:
        if refused:
            raise StoreError(refused)
        text = _answer(args.store, args.verb, args.argument, args.budget, registry, record)
    except StoreError as exc:
        code, message = 2, str(exc)
    except CallError as exc:
        code, message = 1, str(exc)
    record.update(exit_code=code, duration_ms=round((time.monotonic() - started) * 1000))
    if message:
        record["reason"] = clean_field(message)
    try:
        _append_log(args.log or Path.cwd() / DEFAULT_LOG, record)
    except OSError as exc:
        print(f"ctx: could not write the log ({_one_line(exc)})", file=err)
    if message:
        print(f"ctx: {clean_field(message, 400)}", file=err)
    else:
        out.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
