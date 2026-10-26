"""T0.4 stub re-ranker tests (tests-first).

Contract under test (Tasks 002 T0.4, Plan §4 Reranker protocol):
  - tests.support.stub_reranker.StubReranker().rerank(query, texts) -> list[float]
  - one float score per text, in input order
  - score = number of distinct lowercase query words found in the text, so a
    text sharing more words with the query scores higher
  - deterministic: same input, same output
  - every call's (query, texts) is recorded in .calls (to prove the
    re-ranker only ever sees the shortlist, Article IV.3)
"""

from tests.support import stub_reranker as sr


def test_one_float_score_per_text_in_order():
    scores = sr.StubReranker().rerank("retry login", ["a", "b", "c"])
    assert len(scores) == 3
    assert all(isinstance(s, float) for s in scores)


def test_more_shared_query_words_scores_higher():
    texts = ["def helper(): pass", "def login(): retry()", "login only"]
    scores = sr.StubReranker().rerank("retry login", texts)
    assert scores[1] > scores[2] > scores[0]


def test_matching_is_case_insensitive_and_counts_distinct_words():
    scores = sr.StubReranker().rerank("Login login", ["LOGIN login login"])
    assert scores == [1.0]


def test_deterministic():
    texts = ["x y", "y z", "z x"]
    r = sr.StubReranker()
    assert r.rerank("x z", texts) == r.rerank("x z", texts)


def test_empty_texts_gives_empty_scores():
    assert sr.StubReranker().rerank("q", []) == []


def test_records_calls():
    r = sr.StubReranker()
    r.rerank("q", ["a", "b"])
    assert r.calls == [("q", ["a", "b"])]
