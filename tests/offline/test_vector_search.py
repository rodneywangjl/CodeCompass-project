"""Vector ANN search on the store and the read-only handle (tests-first).

Fix outside a numbered task: the online vector retriever (Spec 002 T2.1) needs
a ranked-id search through `open_index`, which Sprint 1 did not expose.
"""

import dataclasses

from codecompass.offline import ensure_current, open_index
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.offline.models import Chunk
from codecompass.offline.stores.vector import VectorStore
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def _chunk(cid, path, text):
    return Chunk(id=cid, text=text, path=path, start_line=1,
                 end_line=1, language="python", symbol=None, commit_sha="abc")


def _store(tmp_path):
    v = VectorStore(tmp_path / "vec")
    ch = [_chunk("c1", "a.py", "def alpha(): pass\n"),
          _chunk("c2", "b.py", "def beta(): pass\n"),
          _chunk("c3", "c.py", "def gamma(): pass\n")]
    v.add(ch, StubEmbedder().embed([c.text for c in ch]))
    return v


def test_search_ranks_nearest_first(tmp_path):
    v = _store(tmp_path)
    query = StubEmbedder().embed(["def beta(): pass\n"])[0]
    hits = v.search(query, 3)
    assert hits[0] == "c2"
    assert sorted(hits) == ["c1", "c2", "c3"]


def test_search_limit_truncates_and_clamps(tmp_path):
    v = _store(tmp_path)
    query = StubEmbedder().embed(["def alpha(): pass\n"])[0]
    assert v.search(query, 1) == ["c1"]
    assert len(v.search(query, 50)) == 3


def test_search_empty_store_returns_empty(tmp_path):
    v = VectorStore(tmp_path / "vec", dimension=8)
    assert v.search([0.1] * 8, 5) == []


def test_read_only_handle_exposes_search(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    ensure_current(fx.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=StubEmbedder())
    handles = open_index(fx.path, config=cfg, index_dir=tmp_path / "idx")
    try:
        query = StubEmbedder().embed(["hello"])[0]
        hits = handles.vector.search(query, 5)
        assert hits and set(hits) <= handles.vector.ids()
        assert len(hits) == len(set(hits))
    finally:
        handles.close()
