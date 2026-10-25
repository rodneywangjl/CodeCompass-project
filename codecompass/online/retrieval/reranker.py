"""Cross-encoder re-ranking of the merged shortlist (Article IV.3)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score each text against the query. Higher is more relevant."""
        ...
