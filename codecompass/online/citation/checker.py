"""Deterministic citation checker: F (cited) or G (flagged) (Article VI)."""

from __future__ import annotations

import dataclasses

from codecompass.online.citation.parser import parse_answer
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
    sources = [dataclasses.replace(s, verified=_verified(s, chunks, commits))
               for s in parsed.sources]
    unverified = [s.marker for s in sources if not s.verified]
    return CitationResult(outcome="G" if unverified else "F", sources=sources,
                          unverified=unverified, answer_text=answer)
