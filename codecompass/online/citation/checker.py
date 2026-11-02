"""Deterministic citation checker: F (cited) or G (flagged) (Article VI)."""

from __future__ import annotations

import dataclasses
import re

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


def _copy_commit_metadata(answer: str, body: str, sources, commits):
    """Replace the model's commit subject/author/date with the tool record (Plan D10)."""
    lines = answer.splitlines()
    body_len = len(body.splitlines())
    out = []
    for s in sources:
        if s.kind == "commit" and s.verified:
            rec = next(r for r in commits if r.sha.startswith(s.commit))
            s = dataclasses.replace(s, subject=rec.subject, author=rec.author,
                                    date=rec.date)
            entry = re.compile(rf"\s*\[{s.marker}\]\s*Commit ")
            for i in range(body_len, len(lines)):
                if entry.match(lines[i]):
                    lines[i] = (f'[{s.marker}] Commit {s.commit}, "{s.subject}", '
                                f"{s.author}, {s.date}")
        out.append(s)
    text = "\n".join(lines) + ("\n" if answer.endswith("\n") else "")
    return text, out


def check(answer: str, chunks, commits) -> CitationResult:
    """Match each Sources entry against the evidence placed in context (Plan D9)."""
    parsed = parse_answer(answer)
    markers = body_markers(parsed.body)
    counts: dict[int, int] = {}
    for s in parsed.sources:
        counts[s.marker] = counts.get(s.marker, 0) + 1
    # An entry is verified only if its evidence is in context, its marker is
    # used in the body, and no other entry claims the same marker.
    sources, unreferenced = [], set()
    for s in parsed.sources:
        matches = counts[s.marker] == 1 and _verified(s, chunks, commits)
        if matches and s.marker not in markers:
            unreferenced.add(s.marker)  # real evidence, but tied to no statement (AC-4.10)
        sources.append(dataclasses.replace(s, verified=matches and s.marker in markers))
    unverified = sorted({s.marker for s in sources if not s.verified}
                        | (markers - counts.keys()))
    flagged = bool(unverified) or not parsed.has_sources
    answer, sources = _copy_commit_metadata(answer, parsed.body, sources, commits)
    return CitationResult(outcome="G" if flagged else "F", sources=sources,
                          unverified=unverified, unreferenced=sorted(unreferenced),
                          answer_text=answer)
