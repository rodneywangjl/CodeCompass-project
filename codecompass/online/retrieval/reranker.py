"""Cross-encoder re-ranking of the merged shortlist (Article IV.3)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score each text against the query. Higher is more relevant."""
        ...


def rerank_chunks(reranker: Reranker, question: str, chunks: list, final_k: int) -> list:
    """Re-order the shortlist by score, best first; ties keep shortlist order."""
    if not chunks:
        return []
    scores = reranker.rerank(question, [c.text for c in chunks])
    order = sorted(range(len(chunks)), key=lambda i: -scores[i])
    return [(chunks[i], scores[i]) for i in order[:final_k]]
