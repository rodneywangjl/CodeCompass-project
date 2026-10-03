"""T6.2 embedding batches and lazy-model tests (tests-first)."""

import dataclasses

import pytest

from codecompass.offline import orchestrator
from codecompass.offline.chunking.ids import text_hash
from codecompass.offline.config import load_config
from codecompass.offline.stores.vector import VectorStore
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


class SpyEmbedder(StubEmbedder):
    def __init__(self):
        super().__init__()
        self.batches = []

    def embed(self, texts):
        self.batches.append(list(texts))
        return super().embed(texts)


def _run(repo, base, cfg, **kw):
    return orchestrator.run(repo, config=cfg, index_dir=base, **kw)


def test_batches_bounded_sorted_and_mapped(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    cfg = dataclasses.replace(cfg, embedder=dataclasses.replace(
        cfg.embedder, batch_size=2))
    spy = SpyEmbedder()
    _run(fx.path, tmp_path / "idx", cfg, embedder=spy)
    assert spy.batches, "expected embedding work on a fresh build"
    for batch in spy.batches:
        assert len(batch) <= 2
    seen = [t for batch in spy.batches for t in batch]
    assert seen == sorted(seen, key=len)  # length-sorted
    idx = orchestrator.index_path_for(fx.path, tmp_path / "idx")
    stored = VectorStore(idx / "vector").vectors_for_paths(
        [c for c in ["src/main.py", "src/app.js"]])
    for h, vec in stored.items():
        expect = spy.embed([[t for t in seen if text_hash(t) == h][0]])[0]
        assert list(vec) == pytest.approx(expect, abs=1e-6)  # float32 store


def test_factory_never_called_when_nothing_to_embed(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    _run(fx.path, tmp_path / "idx", cfg, embedder=StubEmbedder())
    calls = []
    _run(fx.path, tmp_path / "idx", cfg,
         embedder_factory=lambda: calls.append(1) or StubEmbedder())
    assert calls == []
