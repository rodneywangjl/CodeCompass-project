"""Render checked answers; flagged ones never look verified (Article VI.3)."""

from __future__ import annotations

import re

from codecompass.online.citation.parser import _HEADING, body_markers, parse_answer
from codecompass.online.models import CitationResult

BANNER = ("⚠ WARNING: Some citations in this answer could not be verified against "
          "the retrieved evidence. Verify the marked sources manually.")
MARK = "[UNVERIFIED] "
UNREFERENCED_BANNER = ("⚠ WARNING: Sources are listed, but the answer does not say which "
                       "statement each one supports. Check them yourself before relying on "
                       "the answer.")
UNREF_MARK = "[NOT REFERENCED IN ANSWER] "
UNCITED_NOTE = ("Note: This answer is not supported by any citation from the "
                "repository. Verify it against the source code before relying on it.")
PARTIAL_NOTE = ("Note: Some statements in this answer are not supported by a citation. "
                "They are marked (not cited). Verify them against the source code "
                "before relying on them.")
TAG = " (not cited)"
DOCS_LABEL = " (documentation)"
DOCS_BANNER = ("ℹ Note: Part of this answer is based on documentation, which may be out of date. "
               "Code is the source of truth.")
_DOC_ENTRY = re.compile(r"^\s*(?:\[UNVERIFIED\]\s+|\[NOT REFERENCED IN ANSWER\]\s+)?\[(\d+)\]")

_ENTRY = re.compile(r"\s*\[(\d+)\]")
_LIST_ITEM = re.compile(r"\s*(?:[-*]|\d+[.)])\s")


def _parts(lines: list[str]) -> list[list[int]]:
    """Line indices of each paragraph or list item; headings and code skipped."""
    parts: list[list[int]] = []
    current: list[int] = []
    in_code = False
    for i, line in enumerate(lines):
        fence = line.strip().startswith("```")
        if fence or in_code or not line.strip() or line.lstrip().startswith("#"):
            if current:
                parts.append(current)
            current = []
            in_code ^= fence
            continue
        if _LIST_ITEM.match(line) and current:
            parts.append(current)
            current = []
        current.append(i)
    if current:
        parts.append(current)
    return parts


def _tag_uncited(lines: list[str], body_len: int) -> bool:
    """Append TAG to each body part with no [N] marker (Plan D11). True if any."""
    tagged = False
    for part in _parts(lines[:body_len]):
        last = part[-1]
        if lines[last].rstrip().endswith(":"):
            continue  # a lead-in such as "Here is the call:" makes no claim
        if body_markers("\n".join(lines[i] for i in part)):
            continue
        lines[last] = lines[last].rstrip() + TAG
        tagged = True
    return tagged


def render(result: CitationResult) -> str:
    """F: the answer, uncited parts tagged. G: banner plus marks (Plan D11).

    An answer that cites nothing gets UNCITED_NOTE instead of the banner: it
    fabricated nothing, it has no evidence (AC-4.8).
    """
    text = result.answer_text
    parsed = parse_answer(text)
    if not body_markers(parsed.body) and not parsed.sources:
        return UNCITED_NOTE + "\n\n" + text
    lines = text.splitlines()
    body_len = len(parsed.body.splitlines())
    note = PARTIAL_NOTE + "\n\n" if _tag_uncited(lines, body_len) else ""
    if result.outcome == "F":
        return note + "\n".join(lines) if note else text
    unverified, unreferenced = set(result.unverified), set(result.unreferenced)
    for i in range(body_len, len(lines)):
        m = _ENTRY.match(lines[i])
        if m and int(m.group(1)) in unverified:
            lines[i] = (UNREF_MARK if int(m.group(1)) in unreferenced else MARK) + lines[i]
    listed = {s.marker for s in result.sources}
    lines += [f"{MARK}[{n}] (no matching Sources entry)"
              for n in sorted(unverified - listed)]
    # Real sources that no statement uses get their own wording; any failed or
    # missing citation keeps the main banner (AC-4.4, AC-4.10).
    banner = UNREFERENCED_BANNER if unverified and unverified <= unreferenced else BANNER
    return banner + "\n\n" + note + "\n".join(lines)


def mark_documentation(rendered: str, result: CitationResult,
                       doc_paths: set[str]) -> tuple[str, list[int]]:
    """Label doc sources in Sources and prepend DOCS_BANNER if any (T22.2)."""
    target = {s.marker for s in result.sources
              if s.kind == "code" and s.path is not None and s.path in doc_paths}
    if not target:
        return rendered, []
    lines = rendered.splitlines()
    heading = max((i for i, line in enumerate(lines) if _HEADING.fullmatch(line)),
                  default=None)
    if heading is None:
        return rendered, []
    labelled: set[int] = set()
    for i in range(heading + 1, len(lines)):
        m = _DOC_ENTRY.match(lines[i])
        if m and int(m.group(1)) in target:
            marker = int(m.group(1))
            if not lines[i].endswith(DOCS_LABEL):
                lines[i] += DOCS_LABEL
            labelled.add(marker)
    if not labelled:
        return rendered, []
    return DOCS_BANNER + "\n\n" + "\n".join(lines), sorted(labelled)
