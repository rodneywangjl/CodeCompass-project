"""T2.4 hybrid retrieval integration tests (tests-first).

Contract under test (Spec AC-2.1, AC-2.3, AC-2.4; Plan §1, D1, D2):
  - retrieval.hybrid.retrieve(handles, question, *, config) -> list[(chunk_id, rrf_score)]
  - embeds the question, runs vector and keyword search with their own k, and
    merges them with RRF; the result has at most rerank_k unique ids
"""

import dataclasses

import pytest

import codecompass.offline as offline
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.config import RetrievalConfig
from codecompass.online.retrieval import hybrid
from codecompass.online.retrieval.keyword import keyword_search
from codecompass.online.retrieval.rrf import rrf_merge
from codecompass.online.retrieval.vector import vector_search
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder


@pytest.fixture
def handles(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg = dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    offline.ensure_current(repo.path, config=cfg, index_dir=tmp_path / "idx",
                           embedder=StubEmbedder())
    h = offline.open_index(repo.path, config=cfg, index_dir=tmp_path / "idx",
                           embedder=StubEmbedder())
    yield h
    h.close()


QUESTION = "Why is MAX_RETRIES used in authenticate?"


def test_result_is_the_rrf_merge_of_both_searches(handles):
    cfg = RetrievalConfig()
    vec = vector_search(handles.vector, handles.embed_query(QUESTION), cfg.vector_k)
    kw = keyword_search(handles.keyword, QUESTION, cfg.keyword_k)
    assert vec and kw
    got = hybrid.retrieve(handles, QUESTION, config=cfg)
    assert got == rrf_merge(vec, kw, k=cfg.rerank_k, constant=cfg.rrf_constant)
    assert {cid for cid, _ in got} == set(vec) | set(kw)


def test_chunk_found_by_both_appears_once(handles):
    ids = [cid for cid, _ in hybrid.retrieve(handles, QUESTION, config=RetrievalConfig())]
    assert len(ids) == len(set(ids))


def test_output_is_capped_at_rerank_k(handles):
    cfg = RetrievalConfig(rerank_k=1)
    assert len(hybrid.retrieve(handles, QUESTION, config=cfg)) == 1


def test_each_search_uses_its_own_k(handles):
    cfg = RetrievalConfig(vector_k=1, keyword_k=1)
    vec = vector_search(handles.vector, handles.embed_query(QUESTION), 1)
    kw = keyword_search(handles.keyword, QUESTION, 1)
    got = hybrid.retrieve(handles, QUESTION, config=cfg)
    assert {cid for cid, _ in got} == set(vec) | set(kw)
