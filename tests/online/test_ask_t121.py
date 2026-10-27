"""T12.1 ask() tests (tests-first); also T2.3's checks that need ask().

Contract under test (Spec AC-9.1, AC-9.2, AC-2.2; Plan §1, D1, O2):
  - ask(repo, question, *, config, profile=None, index_dir=None,
        generator=None, reranker=None, embedder=None) -> QueryResult
    with answer, sources, citation_outcome, stale_index, stale_message and
    audit_log; it prints nothing
  - the embedder given to ask() reaches both ensure_current and open_index
    (the same instance, O2)
  - an index built with a different embedder is refused, not silently used
"""

import dataclasses

import pytest

import codecompass.online as online
from codecompass.offline.config import EmbedderConfig
from codecompass.online.models import QueryResult
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo


def test_ask_returns_a_complete_result_and_prints_nothing(tmp_path, capsys):
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                        profile="dev", index_dir=tmp_path / "idx", **stubs())
    assert isinstance(result, QueryResult)
    assert "Login retries on timeout [1]." in result.answer
    assert result.citation_outcome == "F"
    assert [s.verified for s in result.sources] == [True]
    assert result.stale_index is False and result.stale_message == ""
    assert result.audit_log["question"] == "Why does authenticate retry?"
    assert capsys.readouterr().out == ""


def test_the_same_embedder_reaches_ensure_current_and_open_index(monkeypatch, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    seen = []
    for name in ("ensure_current", "open_index"):
        real = getattr(online, name)
        monkeypatch.setattr(online, name, lambda *a, _r=real, **k: seen.append(
            k["embedder"]) or _r(*a, **k))
    kit = stubs()
    online.ask(repo.path, "Why retry?", config=config(tmp_path), index_dir=tmp_path / "idx", **kit)
    assert seen == [kit["embedder"], kit["embedder"]]


def test_mismatched_embedder_is_refused(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg = config(tmp_path)
    online.ask(repo.path, "Why retry?", config=cfg, index_dir=tmp_path / "idx", **stubs())
    other = dataclasses.replace(cfg, offline=dataclasses.replace(
        cfg.offline, embedder=EmbedderConfig(model="other", revision="r", dimension=8)))
    with pytest.raises(Exception, match="embedder mismatch"):
        kit = stubs()
        kit["embedder"].identity = dataclasses.replace(kit["embedder"].identity, model="other",
                                                       revision="r")
        online.ask(repo.path, "Why retry?", config=other, index_dir=tmp_path / "idx", **kit)
