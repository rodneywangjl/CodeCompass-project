"""ensure_current builds the pinned embedder when none is given (tests-first).

Fix outside a numbered task, found while wiring ask() (Spec 002 T12.1):
with no embedder and no factory, a needed re-index failed with "no embedder
available", and the online pipeline may not build CodeEmbedder itself
(Article II.2). open_index already defaults to the configured embedder;
ensure_current now does the same, lazily, so the fast path loads nothing.
"""

import dataclasses

from codecompass.offline import embedding, ensure_current
from codecompass.offline.config import EmbedderConfig, load_config
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder

CFG = dataclasses.replace(
    load_config(None), embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))


class _Recording(StubEmbedder):
    built: list = []

    def __init__(self, embedder_config) -> None:
        super().__init__(embedder_config.dimension)
        _Recording.built.append(embedder_config)


def test_reindex_without_an_embedder_uses_the_configured_one(monkeypatch, tmp_path):
    _Recording.built = []
    monkeypatch.setattr(embedding, "CodeEmbedder", _Recording)
    fx = build_fixture_repo(tmp_path / "repo")
    result = ensure_current(fx.path, config=CFG, index_dir=tmp_path / "idx")
    assert result.ok, result.message
    assert _Recording.built == [CFG.embedder]


def test_fast_path_builds_no_embedder(monkeypatch, tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    ensure_current(fx.path, config=CFG, index_dir=tmp_path / "idx", embedder=StubEmbedder())
    _Recording.built = []
    monkeypatch.setattr(embedding, "CodeEmbedder", _Recording)
    assert ensure_current(fx.path, config=CFG, index_dir=tmp_path / "idx").ok
    assert _Recording.built == []
