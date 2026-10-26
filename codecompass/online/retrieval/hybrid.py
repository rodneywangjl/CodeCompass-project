"""Hybrid retrieval: vector + keyword search merged by RRF (Article IV.1, IV.2)."""

from __future__ import annotations

from codecompass.online.retrieval.embedder import embed_question
from codecompass.online.retrieval.keyword import keyword_search
from codecompass.online.retrieval.rrf import rrf_merge
from codecompass.online.retrieval.vector import vector_search


def retrieve(handles, question: str, *, config) -> list[tuple[str, float]]:
    """The re-rank shortlist: (chunk_id, rrf_score), best first, at most rerank_k."""
    vector_hits = vector_search(handles.vector, embed_question(handles, question),
                                config.vector_k)
    keyword_hits = keyword_search(handles.keyword, question, config.keyword_k)
    return rrf_merge(vector_hits, keyword_hits, k=config.rerank_k,
                     constant=config.rrf_constant)
