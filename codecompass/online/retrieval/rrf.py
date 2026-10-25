"""Reciprocal Rank Fusion merge (Article IV.2, Plan D2)."""

from __future__ import annotations


def rrf_merge(
    vector_hits: list[str], keyword_hits: list[str], *, k: int, constant: int
) -> list[tuple[str, float]]:
    """Merge two ranked id lists by rank only: score = sum(1 / (constant + rank)).

    Ranks count from 0 (Plan D2). A chunk in both lists is counted once with
    its contributions summed. Ties are broken by chunk id so output is stable.
    """
    scores: dict[str, float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, cid in enumerate(hits):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (constant + rank)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:k]
