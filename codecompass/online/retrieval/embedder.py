"""Query embedding through the index handles (Article II.2, II.4; Plan D1)."""

from __future__ import annotations


def embed_question(handles, question: str) -> list[float]:
    """Embed *question* with the embedder open_index checked against the index."""
    return handles.embed_query(question)
