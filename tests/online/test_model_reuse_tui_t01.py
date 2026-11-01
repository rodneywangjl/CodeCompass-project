"""T0.1 (Spec 004) model reuse across questions: tests first.

Contract under test (Spec 004 AC-1.4; Plan 002 O1, O2; Article II.4):
  - the default re-ranker and the default embedder are created once per
    process for a given configuration and reused by every later ask()
  - ensure_current and open_index share that one embedder (O2)
  - a different configuration builds a new instance
  - objects passed to ask() are used as given and never enter the cache
  - the cache never bypasses the embedder identity check (Article II.4)

Each test uses its own embedder and re-ranker revision strings, so a cached
instance from another test can never be reused here.
"""

import dataclasses

import pytest

import codecompass.online as online
from codecompass.offline.config import EmbedderConfig
from codecompass.offline.models import EmbedderIdentity
from codecompass.online.config import RerankerConfig
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_reranker import StubReranker

QUESTION = "Why does authenticate retry?"


@pytest.fixture
def built(monkeypatch):
    """Replace the real model classes with counting stubs; return what was built."""
    made = {"embedder": [], "reranker": []}

    class CountedEmbedder(StubEmbedder):
        def __init__(self, embedder_config):
            super().__init__(embedder_config.dimension)
            self.identity = EmbedderIdentity(model=embedder_config.model,
                                             revision=embedder_config.revision,
                                             dimension=embedder_config.dimension)
            made["embedder"].append(self)

    class CountedReranker(StubReranker):
        def __init__(self, reranker_config):
            super().__init__()
            made["reranker"].append(self)

    monkeypatch.setattr("codecompass.offline.embedding.CodeEmbedder", CountedEmbedder)
    monkeypatch.setattr("codecompass.online.retrieval.reranker.BgeReranker", CountedReranker)
    return made


def unique_config(tmp_path, tag=""):
    """The stub-based test config, with embedder and re-ranker keys no other test uses."""
    cfg = config(tmp_path)
    key = f"{tmp_path.name}{tag}"
    return dataclasses.replace(
        cfg,
        offline=dataclasses.replace(
            cfg.offline, embedder=EmbedderConfig(model="stub", revision=f"stub-{key}",
                                                 dimension=8)),
        reranker=RerankerConfig(revision=f"rerank-{key}"))


def ask_default_models(repo, cfg, index_dir):
    """ask() with only the generator injected: re-ranker and embedder are the defaults."""
    return online.ask(repo.path, QUESTION, config=cfg, index_dir=index_dir,
                      generator=CitingGenerator())


def test_default_reranker_is_built_once_across_questions(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    for _ in range(3):
        ask_default_models(repo, cfg, tmp_path / "idx")
    assert len(built["reranker"]) == 1
    assert len(built["reranker"][0].calls) == 3  # every question used that one instance


def test_default_embedder_is_built_once_across_questions(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    for _ in range(3):  # the first question also indexes, so ensure_current needs it too
        ask_default_models(repo, cfg, tmp_path / "idx")
    assert len(built["embedder"]) == 1


def test_a_different_reranker_config_builds_a_new_instance(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    other = dataclasses.replace(cfg, reranker=RerankerConfig(
        revision=f"rerank-other-{tmp_path.name}"))
    ask_default_models(repo, cfg, tmp_path / "idx")
    ask_default_models(repo, other, tmp_path / "idx")
    ask_default_models(repo, cfg, tmp_path / "idx")  # back to the first: reused, not rebuilt
    assert len(built["reranker"]) == 2
    assert built["reranker"][0] is not built["reranker"][1]


def test_a_different_embedder_config_builds_a_new_instance(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    other = unique_config(tmp_path, tag="-other")
    ask_default_models(repo, cfg, tmp_path / "idx-a")
    ask_default_models(repo, other, tmp_path / "idx-b")  # its own index, so no mismatch
    ask_default_models(repo, cfg, tmp_path / "idx-a")  # back to the first: reused, not rebuilt
    assert len(built["embedder"]) == 2
    assert built["embedder"][0] is not built["embedder"][1]


def test_objects_passed_to_ask_are_used_and_never_cached(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    kit = stubs()
    kit["embedder"].identity = EmbedderIdentity(  # the stub claims the configured identity
        model="stub", revision=cfg.offline.embedder.revision, dimension=8)
    online.ask(repo.path, QUESTION, config=cfg, index_dir=tmp_path / "idx", **kit)
    assert built == {"embedder": [], "reranker": []}  # nothing default was built
    assert len(kit["reranker"].calls) == 1  # the injected re-ranker did the work
    # ...and the injected objects were not remembered for the next default call:
    ask_default_models(repo, cfg, tmp_path / "idx")
    assert len(built["reranker"]) == 1
    assert len(built["embedder"]) == 1


def test_the_cache_does_not_bypass_the_embedder_identity_check(tmp_path, built):
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    ask_default_models(repo, cfg, tmp_path / "idx")  # caches this config's embedder
    other = dataclasses.replace(cfg, offline=dataclasses.replace(
        cfg.offline, embedder=EmbedderConfig(model="stub", revision="stub-other",
                                             dimension=8)))
    with pytest.raises(Exception, match="embedder mismatch"):
        ask_default_models(repo, other, tmp_path / "idx")  # same index, different embedder
