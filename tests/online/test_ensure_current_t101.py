"""T10.1 ensure_current integration tests (tests-first).

Contract under test (Spec AC-6.1, AC-6.2, AC-6.3; Plan D12; Article III.2):
  - ask() calls ensure_current before opening the index
  - ok: no stale flag; failed or locked with an existing index: stale flag
    set and the answer still comes from that index
  - failed and no index yet: an answer saying so (with the reason); no
    retrieval or generation; nothing raised
"""

import pytest

import codecompass.online as online
from codecompass.offline import EnsureResult
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo

QUESTION = "Why does authenticate retry?"


@pytest.fixture
def indexed(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg = config(tmp_path)
    online.ask(repo.path, QUESTION, config=cfg, index_dir=tmp_path / "idx", **stubs())
    return repo.path, cfg, tmp_path / "idx"


def fail_with(monkeypatch, status, message):
    monkeypatch.setattr(online, "ensure_current",
                        lambda *a, **k: EnsureResult(ok=False, status=status, message=message))


def test_ensure_current_runs_before_the_index_is_opened(monkeypatch, indexed):
    repo, cfg, idx = indexed
    order = []
    real_ensure, real_open = online.ensure_current, online.open_index
    monkeypatch.setattr(online, "ensure_current",
                        lambda *a, **k: order.append("ensure") or real_ensure(*a, **k))
    monkeypatch.setattr(online, "open_index",
                        lambda *a, **k: order.append("open") or real_open(*a, **k))
    online.ask(repo, QUESTION, config=cfg, index_dir=idx, **stubs())
    assert order == ["ensure", "open"]


def test_current_index_is_not_stale(indexed):
    repo, cfg, idx = indexed
    result = online.ask(repo, QUESTION, config=cfg, index_dir=idx, **stubs())
    assert result.stale_index is False and result.citation_outcome == "F"


@pytest.mark.parametrize("status", ["failed", "locked"])
def test_failure_with_an_existing_index_answers_flagged_stale(monkeypatch, indexed, status):
    repo, cfg, idx = indexed
    fail_with(monkeypatch, status, f"reindex {status}")
    gen = CitingGenerator()
    result = online.ask(repo, QUESTION, config=cfg, index_dir=idx, **stubs(gen))
    assert result.stale_index is True
    assert gen.calls, "the answer must still come from the existing index"
    assert result.citation_outcome == "F"


def test_failure_with_no_index_says_so_without_generating(monkeypatch, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    fail_with(monkeypatch, "failed", "disk full")
    gen = CitingGenerator()
    result = online.ask(repo.path, QUESTION, config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs(gen))
    assert online.NO_INDEX in result.answer and "disk full" in result.answer
    assert gen.calls == []
