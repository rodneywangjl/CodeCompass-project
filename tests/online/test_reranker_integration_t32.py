"""T3.2 re-ranker integration tests (tests-first).

Contract under test (Spec AC-2.7, AC-2.4; Plan §1):
  - reranker.rerank_chunks(reranker, question, chunks, final_k) -> list[(chunk, score)]
  - the re-ranker sees only the given shortlist, is not called for an empty
    shortlist, and the result is ordered by score (ties keep shortlist order)
    and truncated to final_k
"""

from codecompass.online.context import RetrievedChunk
from codecompass.online.retrieval import reranker
from tests.support.stub_reranker import StubReranker


def _chunk(cid, text):
    return RetrievedChunk(cid, text, f"src/{cid}.py", 1, 2, "python", "a" * 40)


SHORTLIST = [_chunk("a", "noop helper"),
             _chunk("b", "retry login on timeout"),
             _chunk("c", "login retry timeout with MAX_RETRIES")]


def test_reranker_sees_only_the_shortlist():
    stub = StubReranker()
    reranker.rerank_chunks(stub, "login retry timeout", SHORTLIST[:2], final_k=8)
    assert stub.calls == [("login retry timeout", ["noop helper", "retry login on timeout"])]


def test_order_follows_scores_not_rrf_order():
    out = reranker.rerank_chunks(StubReranker(), "login retry timeout", SHORTLIST, final_k=8)
    assert [c.chunk_id for c, _ in out] == ["b", "c", "a"]
    assert [c.chunk_id for c, _ in out] != [c.chunk_id for c in SHORTLIST]
    assert [s for _, s in out] == [3.0, 3.0, 0.0]


def test_output_is_truncated_to_final_k():
    out = reranker.rerank_chunks(StubReranker(), "login retry timeout", SHORTLIST, final_k=1)
    assert [c.chunk_id for c, _ in out] == ["b"]


def test_empty_shortlist_does_not_call_the_reranker():
    stub = StubReranker()
    assert reranker.rerank_chunks(stub, "anything", [], final_k=8) == []
    assert stub.calls == []
