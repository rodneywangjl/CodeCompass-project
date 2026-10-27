"""T10.2 stale-index fallback tests (tests-first).

Contract under test (Spec AC-6.3, FR-14; Plan D12; Article III.2, X.3):
  - when ensure_current fails, the answer starts with online.STALE_WARNING and
    the failure reason, then the normal answer; stale_index is True and
    stale_message holds the reason; nothing is raised
"""

import codecompass.online as online
from codecompass.offline import EnsureResult
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo


def test_stale_answer_is_warned_and_still_produced(monkeypatch, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg, idx = config(tmp_path), tmp_path / "idx"
    online.ask(repo.path, "Why retry?", config=cfg, index_dir=idx, **stubs())
    monkeypatch.setattr(online, "ensure_current", lambda *a, **k: EnsureResult(
        ok=False, status="locked", message="index is locked (waited 120s)"))
    result = online.ask(repo.path, "Why retry?", config=cfg, index_dir=idx, **stubs())
    assert online.STALE_WARNING.startswith("⚠ WARNING: The index may be out of date")
    assert result.answer.startswith(online.STALE_WARNING)
    assert "index is locked (waited 120s)" in result.answer
    assert "Login retries on timeout [1]." in result.answer
    assert result.stale_index is True
    assert result.stale_message == "index is locked (waited 120s)"
