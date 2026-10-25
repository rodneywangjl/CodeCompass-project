"""T3.1 re-ranker protocol tests (tests-first).

Contract under test (Spec AC-2.7; Plan §4 Reranker protocol):
  - codecompass.online.retrieval.reranker.Reranker: a runtime-checkable
    protocol with rerank(query: str, texts: list[str]) -> list[float]
  - StubReranker satisfies it; an object without rerank does not
  - re-ordering texts by the stub's scores gives a predictable order
"""

from codecompass.online.retrieval import reranker
from tests.support.stub_reranker import StubReranker


def test_stub_satisfies_protocol():
    assert isinstance(StubReranker(), reranker.Reranker)


def test_object_without_rerank_does_not():
    assert not isinstance(object(), reranker.Reranker)


def test_ordering_by_scores_is_predictable():
    texts = ["unrelated", "retry login", "login"]
    scores = StubReranker().rerank("retry login", texts)
    order = [t for _, t in sorted(zip(scores, texts), key=lambda p: -p[0])]
    assert order == ["retry login", "login", "unrelated"]
