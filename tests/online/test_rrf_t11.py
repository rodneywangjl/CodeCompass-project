"""T1.1 RRF scoring and merge tests (tests-first).

Contract under test (Spec AC-2.3, AC-2.4; Plan D2):
  - codecompass.online.retrieval.rrf.rrf_merge(vector_hits, keyword_hits, *, k, constant)
    -> list[tuple[chunk_id, score]]
  - ranks count from 0 as in plan D2: score = sum(1 / (constant + rank))
  - a chunk in both lists appears once with both contributions summed
  - sorted by score descending, ties broken by chunk id ascending
  - truncated to k items
"""

import pytest

from codecompass.online.retrieval import rrf


def merge(v, kw, k=50, constant=60):
    return rrf.rrf_merge(v, kw, k=k, constant=constant)


def test_no_overlap_scores_by_rank():
    out = dict(merge(["a", "b"], ["c", "d"]))
    assert out["a"] == pytest.approx(1 / 60)
    assert out["b"] == pytest.approx(1 / 61)
    assert out["c"] == pytest.approx(1 / 60)
    assert out["d"] == pytest.approx(1 / 61)


def test_full_overlap_sums_contributions():
    out = dict(merge(["a", "b"], ["b", "a"]))
    assert out["a"] == pytest.approx(1 / 60 + 1 / 61)
    assert out["b"] == pytest.approx(1 / 61 + 1 / 60)


def test_chunk_in_both_lists_appears_once():
    out = merge(["a", "b", "c"], ["c", "x"])
    ids = [cid for cid, _ in out]
    assert ids.count("c") == 1
    assert len(ids) == len(set(ids)) == 4


def test_sorted_descending_and_found_by_both_ranks_first():
    out = merge(["a", "b", "c"], ["c", "x"])
    scores = [s for _, s in out]
    assert scores == sorted(scores, reverse=True)
    assert out[0][0] == "c"


def test_ties_broken_by_chunk_id():
    out = merge(["b", "z"], ["a", "y"])
    assert [cid for cid, _ in out] == ["a", "b", "y", "z"]


def test_truncated_to_k():
    out = merge([f"v{i}" for i in range(10)], [f"k{i}" for i in range(10)], k=5)
    assert len(out) == 5
