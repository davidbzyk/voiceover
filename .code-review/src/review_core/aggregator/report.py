"""The final report of a review run, as Markdown: a summary, the counts and every finding.

Everything an agent wrote reaches this module as untrusted text: finding titles, descriptions
and quotes come from agents that read the code under review, and the summary comes from the main
agent. None of it may change the shape of the report, so each piece is cleaned of control
characters, cut to a fixed length with a visible mark, and written in a form that cannot open a
heading, a table row, a list, a block quote, an HTML tag or a code fence of its own.

`render_report` is pure: it takes the run document and the summary and returns text.
"""

from __future__ import annotations

import re
import unicodedata

from review_core.contracts.models import (
    DROP_REASONS,
    REVIEWERS,
    SEVERITIES,
    SUCCESS_OUTCOMES,
    Finding,
    load_run_envelope,
)

NO_SUMMARY = "No summary of the change was written."

DROP_WORDS = {
    "quote_gate": "quote not found at the stated place",
    "confidence_floor": "confidence below the floor",
    "duplicate": "merged into another finding",
    "validator_declined": "declined by the validator",
    "out_of_snapshot": "file not in the change",
    "malformed": "not a valid finding",
}
_LINE_BREAKS = {"\r\n": "\n", "\r": "\n", " ": "\n", " ": "\n", "\x85": "\n"}
_INLINE = re.compile(r"([\\`*_\[\]<>|#!&~])")
_NUMBERED = re.compile(r"^(\d+)([.)])")
_FENCE = re.compile(r"`{3,}|~{3,}")
_FENCE_LINE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_MARK = re.compile(r"^\s{0,3}#{1,6}(\s+|$)")
_RULE = re.compile(r"^\s*[-=_*]{3,}\s*$")


def _clean(text: str, keep: str = "\n") -> str:
    """Drop control and format characters, keeping only the whitespace named in `keep`."""
    for old, new in _LINE_BREAKS.items():
        text = text.replace(old, new)
    kept = []
    for char in text:
        if char in keep:
            kept.append(char)
        elif char in "\t\n":
            kept.append(" ")
        elif unicodedata.category(char) not in ("Cc", "Cf", "Cs"):
            kept.append(char)
    return "".join(kept)


def _escape(text: str) -> str:
    """Backslash-escape every character that could start Markdown or HTML inside a line."""
    return _INLINE.sub(r"\\\1", text)


def _protect_start(text: str) -> str:
    """Escape what could turn the first characters of a line into a list or a rule."""
    if text[:1] in ("-", "+", "="):
        return "\\" + text
    return _NUMBERED.sub(r"\1\\\2", text)


def _paragraphs(text: str) -> list[str]:
    """Blank-line separated blocks, each collapsed to one escaped line that opens no block."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        flat = " ".join(block.split())
        if flat:
            out.append(_protect_start(_escape(flat)))
    return out


def _code_span(text: str) -> str:
    """The text as inline code, with delimiters longer than any backtick run inside it."""
    longest = max((len(run) for run in re.findall("`+", text)), default=0)
    tick = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{tick}{pad}{text}{pad}{tick}"


def _title(text: str) -> str:
    """A finding title as one escaped line."""
    return _escape(" ".join(_clean(text, "").split())) or "(no title)"


def _description(text: str) -> list[str]:
    """A finding description as escaped paragraphs."""
    return _paragraphs(_clean(text))


def _summary(text: str | None) -> list[str]:
    """The summary as escaped paragraphs; heading, rule and fence markup is removed first."""
    if text is None:
        return []
    kept = []
    for raw in _clean(text).split("\n"):
        if _FENCE_LINE.match(raw):
            continue  # the marker and its language word are markup, not sentences
        plain = _FENCE.sub("", _HEADING_MARK.sub("", raw))
        if _RULE.match(plain):
            continue
        # A heading's words stay, as a paragraph of their own.
        kept += ["", plain, ""] if plain != raw and _HEADING_MARK.match(raw) else [plain]
    return _paragraphs("\n".join(kept).strip())


def _quote_block(quote: str) -> list[str]:
    """The quoted code in a fence longer than any backtick run it holds."""
    text = _clean(quote, "\n\t").strip("\n")
    longest = max((len(run) for run in re.findall("`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence, *text.split("\n"), fence]


def _plural(count: int, word: str) -> str:
    """`1 finding`, `2 findings`."""
    return f"{count} {word}" + ("" if count == 1 else "s")


def _order(finding: Finding) -> tuple:
    """Severity first, then place, then a few fields so equal places stay in a fixed order."""
    return (
        SEVERITIES.index(finding.severity), finding.file, finding.line_start, finding.line_end,
        finding.side, finding.title, finding.reviewer,
    )  # fmt: skip


def _raised_by(finding: Finding) -> str:
    """The finding's reviewer, then the others with a finding on its lines, in roster order."""
    others = [r for r in REVIEWERS if r in finding.also_raised_by and r != finding.reviewer]
    return finding.reviewer + (f" (also on these lines: {', '.join(others)})" if others else "")


def _finding_block(finding: Finding) -> list[str]:
    """One finding: heading, five fixed detail lines, description and quote."""
    path = " ".join(_clean(finding.file, "").split())
    place = _code_span(f"{path}:{finding.line_start}-{finding.line_end}")
    lines = [
        f"#### {_title(finding.title)}",
        "",
        f"- Severity: {finding.severity}",
        f"- Confidence: {finding.confidence}",
        f"- Location: {place} ({finding.side} side)",
        f"- Scope: {finding.scope}",
        f"- Raised by: {_raised_by(finding)}",
        "",
    ]
    for para in _description(finding.description):
        lines += [para, ""]
    return [*lines, *_quote_block(finding.quote), ""]


def _counts_table(findings: tuple) -> list[str]:
    """Categories as rows in roster order, severities as columns, with totals."""
    cell = {(c, s): 0 for c in REVIEWERS for s in SEVERITIES}
    for finding in findings:
        cell[(finding.category, finding.severity)] += 1
    rows = ["| Category | " + " | ".join(SEVERITIES) + " | Total |"]
    rows.append("| --- | " + " | ".join("---:" for _ in SEVERITIES) + " | ---: |")
    for category in REVIEWERS:
        counts = [cell[(category, s)] for s in SEVERITIES]
        rows.append(f"| {category} | " + " | ".join(map(str, counts)) + f" | {sum(counts)} |")
    totals = [sum(cell[(c, s)] for c in REVIEWERS) for s in SEVERITIES]
    rows.append("| Total | " + " | ".join(map(str, totals)) + f" | {sum(totals)} |")
    return rows


def _dropped_line(dropped: dict) -> str:
    """One line with how many findings were removed before the report, and why."""
    parts = [f"{DROP_WORDS[r]}: {dropped[r]}" for r in DROP_REASONS if dropped[r]]
    if not parts:
        return "No findings were filtered out."
    total = sum(dropped[r] for r in DROP_REASONS)
    return f"Filtered out before this report: {_plural(total, 'finding')} ({'; '.join(parts)})."


def render_report(doc: dict, summary: str | None) -> str:
    """Render the Markdown report for a run document and an optional summary of the change.

    `doc` is the content of findings.json and must satisfy the run contract (ContractError
    otherwise). The result depends on the two arguments only and ends with one newline.
    """
    run = load_run_envelope(doc)
    env = run.envelope
    done = [r.reviewer for r in env.reviewers if r.outcome in SUCCESS_OUTCOMES]
    lines = ["# Code review report", "", "## What this change does", ""]
    for para in _summary(summary) or [NO_SUMMARY]:
        lines += [para, ""]
    lines += ["## Result", ""]
    lines.append(
        f"{len(done)} of {len(env.reviewers_planned)} reviewers finished. "
        f"The run is {env.status}. {_plural(len(run.findings), 'finding')} kept."
    )
    missed = [f"{r.reviewer} ({r.outcome})" for r in env.reviewers if r.reviewer not in done]
    if missed:
        lines += ["", "Did not finish: " + ", ".join(missed) + "."]
    lines += ["", *_counts_table(run.findings), "", "## Findings", ""]
    if not run.findings:
        lines += ["No findings were kept.", ""]
    for category in REVIEWERS:
        group = sorted((x for x in run.findings if x.category == category), key=_order)
        if group:
            lines += [f"### {category}", ""]
            for finding in group:
                lines += _finding_block(finding)
    lines.append(_dropped_line(env.dropped))
    return "\n".join(lines) + "\n"
