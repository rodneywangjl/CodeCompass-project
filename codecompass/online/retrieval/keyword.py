"""BM25 keyword search over the read-only keyword index (Article IV.1)."""

from __future__ import annotations


def keyword_search(index, query: str, k: int) -> list[str]:
    """Top-k chunk ids by BM25, best first. A blank query matches nothing."""
    if not query.strip():
        return []
    return index.search(query, k)
