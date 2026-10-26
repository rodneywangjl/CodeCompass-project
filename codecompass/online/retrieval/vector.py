"""Vector ANN search over the read-only vector index (Article IV.1)."""

from __future__ import annotations


def vector_search(index, query_vector, k: int) -> list[str]:
    """Top-k chunk ids by cosine similarity to *query_vector*, best first."""
    return index.search(query_vector, k)
