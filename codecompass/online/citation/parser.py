"""Parse the Sources section of an answer (Article VI.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from codecompass.online.models import SourceEntry

_HEADING = re.compile(r"\s*(?:#+\s*)?\**\s*sources\s*\**\s*:?\s*\**\s*", re.IGNORECASE)
_ENTRY = re.compile(r"\s*\[(\d+)\]\s*(.*?)\s*")
_CODE = re.compile(r"(.+?), lines (\d+)-(\d+) \(indexed at ([0-9a-f]{7})\)")
_COMMIT = re.compile(r'Commit ([0-9a-f]{7}), "(.*)", ([^,]+), (\d{4}-\d{2}-\d{2})')
_MARKER = re.compile(r"(?<![\w\]])\[(\d+)\]")


@dataclass(frozen=True)
class ParsedAnswer:
    body: str
    sources: list[SourceEntry] = field(default_factory=list)
    has_sources: bool = False


def _entry(marker: int, rest: str) -> SourceEntry:
    if m := _CODE.fullmatch(rest):
        return SourceEntry(kind="code", marker=marker, path=m.group(1),
                           start_line=int(m.group(2)), end_line=int(m.group(3)),
                           commit=m.group(4))
    if m := _COMMIT.fullmatch(rest):
        return SourceEntry(kind="commit", marker=marker, commit=m.group(1),
                           subject=m.group(2), author=m.group(3), date=m.group(4))
    return SourceEntry(kind="invalid", marker=marker)


def parse_answer(text: str) -> ParsedAnswer:
    """Split the answer at its last Sources heading and parse the entries."""
    lines = text.splitlines()
    heading = max((i for i, line in enumerate(lines) if _HEADING.fullmatch(line)),
                  default=None)
    if heading is None:
        return ParsedAnswer(body=text)
    sources = [_entry(int(m.group(1)), m.group(2))
               for line in lines[heading + 1:] if (m := _ENTRY.fullmatch(line))]
    return ParsedAnswer(body="\n".join(lines[:heading]).rstrip(),
                        sources=sources, has_sources=True)


def body_markers(body: str) -> set[int]:
    """Inline [N] citation markers, ignoring indexing such as arr[0]."""
    return {int(n) for n in _MARKER.findall(body)}
