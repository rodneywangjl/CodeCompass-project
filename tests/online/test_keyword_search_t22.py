"""T2.2 keyword search wrapper tests (tests-first).

Contract under test (Spec AC-2.1 keyword side; Plan §3 retrieval/keyword.py):
  - codecompass.online.retrieval.keyword.keyword_search(index, query, k) -> list[chunk_id]
  - index is the read-only keyword handle from codecompass.offline.open_index
  - returns at most k ids, best BM25 match first
  - exact identifier lookup works
  - an empty index or a blank query returns []
"""

import dataclasses
import subprocess

import pytest

import codecompass.offline as offline
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.retrieval import keyword
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
    return offline.open_index(repo_path, config=cfg, index_dir=idx)


@pytest.fixture
def handles(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    h = _open(repo.path, tmp_path / "idx")
    yield h
    h.close()


def _paths(handles, ids):
    found = handles.keyword.paths_for_ids(ids)
    return [found[i] for i in ids]


def test_exact_identifier_lookup(handles):
    ids = keyword.keyword_search(handles.keyword, "MAX_RETRIES", k=5)
    assert ids
    assert _paths(handles, ids)[0] == "src/auth.py"


def test_best_match_first(handles):
    ids = keyword.keyword_search(handles.keyword, "noop", k=5)
    assert _paths(handles, ids)[0] == "src/util.py"


def test_k_limits_results(handles):
    all_ids = keyword.keyword_search(handles.keyword, "def return", k=50)
    assert len(all_ids) >= 2
    assert len(keyword.keyword_search(handles.keyword, "def return", k=1)) == 1


def test_blank_query_returns_empty(handles):
    assert keyword.keyword_search(handles.keyword, "   ", k=5) == []


def test_question_punctuation_does_not_crash(handles):
    ids = keyword.keyword_search(
        handles.keyword, 'Why does authenticate() retry "3" times?', k=5)
    assert ids


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
        assert keyword.keyword_search(h.keyword, "anything", k=5) == []
    finally:
        h.close()
