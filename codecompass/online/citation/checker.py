"""Deterministic citation checker: F (cited) or G (flagged) (Article VI)."""

from __future__ import annotations

import dataclasses

from codecompass.online.citation.parser import body_markers, parse_answer
from codecompass.online.models import CitationResult, SourceEntry


def _covered(entry: SourceEntry, chunks) -> bool:
    """Every cited line lies inside retrieved chunks of that path and commit."""
    spans = sorted((c.start_line, c.end_line) for c in chunks
                   if c.path == entry.path and c.commit_sha.startswith(entry.commit))
    need = entry.start_line
    for start, end in spans:
        if start > need:
            break
        need = max(need, end + 1)
        if need > entry.end_line:
            return True
    return False


def _verified(entry: SourceEntry, chunks, commits) -> bool:
    if entry.kind == "code":
        return entry.start_line <= entry.end_line and _covered(entry, chunks)
    if entry.kind == "commit":
        return any(r.sha.startswith(entry.commit) for r in commits)
    return False


def check(answer: str, chunks, commits) -> CitationResult:
    """Match each Sources entry against the evidence placed in context (Plan D9)."""
    parsed = parse_answer(answer)
    markers = body_markers(parsed.body)
    counts: dict[int, int] = {}
    for s in parsed.sources:
        counts[s.marker] = counts.get(s.marker, 0) + 1
    # An entry is verified only if its evidence is in context, its marker is
    # used in the body, and no other entry claims the same marker.
    sources = [dataclasses.replace(
        s, verified=(s.marker in markers and counts[s.marker] == 1
                     and _verified(s, chunks, commits)))
        for s in parsed.sources]
    unverified = sorted({s.marker for s in sources if not s.verified}
                        | (markers - counts.keys()))
    flagged = bool(unverified) or not parsed.has_sources
    return CitationResult(outcome="G" if flagged else "F", sources=sources,
                          unverified=unverified, answer_text=answer)
