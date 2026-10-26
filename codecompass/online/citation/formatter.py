"""Render checked answers; flagged ones never look verified (Article VI.3)."""

from __future__ import annotations

import re

from codecompass.online.citation.parser import parse_answer
from codecompass.online.models import CitationResult

BANNER = ("⚠ WARNING: Some citations in this answer could not be verified against "
          "the retrieved evidence. Verify the marked sources manually.")
MARK = "[UNVERIFIED] "
_ENTRY = re.compile(r"\s*\[(\d+)\]")


def render(result: CitationResult) -> str:
    """F: the answer as is. G: banner plus a mark on each unverified source (Plan D11)."""
    text = result.answer_text
    if result.outcome == "F":
        return text
    unverified = set(result.unverified)
    lines = text.splitlines()
    body_len = len(parse_answer(text).body.splitlines())
    for i in range(body_len, len(lines)):
        m = _ENTRY.match(lines[i])
        if m and int(m.group(1)) in unverified:
            lines[i] = MARK + lines[i]
    listed = {s.marker for s in result.sources}
    lines += [f"{MARK}[{n}] (no matching Sources entry)"
              for n in sorted(unverified - listed)]
    return BANNER + "\n\n" + "\n".join(lines)
