"""Deterministic stub re-ranker for the required (model-free) test suite."""

from __future__ import annotations

import re

_WORD = re.compile(r"\w+")


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


class StubReranker:
    """Scores each text by how many distinct query words it contains."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        self.calls.append((query, list(texts)))
        q = _words(query)
        return [float(len(q & _words(t))) for t in texts]
