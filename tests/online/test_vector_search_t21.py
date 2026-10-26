"""T2.1 vector search wrapper tests (tests-first).

Contract under test (Spec AC-2.1 vector side; Plan §3 retrieval/vector.py):
  - codecompass.online.retrieval.vector.vector_search(index, query_vector, k) -> list[chunk_id]
  - index is the read-only vector handle from codecompass.offline.open_index
  - returns at most k ids, most cosine-similar first
  - an empty index returns []
"""

import dataclasses
import math
import subprocess

import pytest

import codecompass.offline as offline
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.retrieval import vector
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder


def _config():
    return dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))


def _open(repo_path, idx):
    cfg = _config()
    offline.ensure_current(repo_path, config=cfg, index_dir=idx,
                           embedder=StubEmbedder())
    return offline.open_index(repo_path, config=cfg, index_dir=idx,
                              embedder=StubEmbedder())


@pytest.fixture
def handles(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    h = _open(repo.path, tmp_path / "idx")
    yield h
    h.close()


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _stored(handles):
    ids = sorted(handles.vector.ids())
    return {cid: rec["vector"]
            for cid, rec in handles.vector.records_for_ids(ids).items()}


def test_a_chunks_own_vector_finds_that_chunk_first(handles):
    stored = _stored(handles)
    target = sorted(stored)[0]
    assert vector.vector_search(handles.vector, stored[target], k=3)[0] == target


def test_results_are_ordered_by_cosine_similarity(handles):
    stored = _stored(handles)
    query = StubEmbedder().embed(["Why does authenticate retry?"])[0]
    expected = sorted(stored, key=lambda cid: _cosine(query, stored[cid]),
                      reverse=True)
    got = vector.vector_search(handles.vector, query, k=len(stored))
    assert got == expected


def test_k_limits_results(handles):
    total = len(handles.vector.ids())
    assert total >= 2
    query = StubEmbedder().embed(["retry"])[0]
    assert len(vector.vector_search(handles.vector, query, k=1)) == 1
    assert len(vector.vector_search(handles.vector, query, k=total + 50)) == total


def test_returns_unique_chunk_ids_from_the_index(handles):
    query = StubEmbedder().embed(["token"])[0]
    ids = vector.vector_search(handles.vector, query, k=50)
    assert len(ids) == len(set(ids))
    assert set(ids) <= handles.vector.ids()


def test_empty_index_returns_empty(tmp_path):
    repo = tmp_path / "docs-only"
    repo.mkdir()
    (repo / "README.md").write_text("# only docs\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t",
                  "commit", "-q", "-m", "docs"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    h = _open(repo, tmp_path / "idx")
    try:
        query = StubEmbedder().embed(["anything"])[0]
        assert vector.vector_search(h.vector, query, k=5) == []
    finally:
        h.close()
