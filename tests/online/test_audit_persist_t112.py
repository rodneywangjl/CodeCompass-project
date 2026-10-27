"""T11.2 audit log persistence tests (tests-first).

Contract under test (Spec AC-7.2, AC-7.3; Plan §7 [logging]):
  - every ask() writes its audit log as JSON under logging.query_log_dir; the
    file name starts with a UTC timestamp; the path is in audit_log["log_file"]
  - a stale-index warning is recorded in the log
"""

import json
import re
from pathlib import Path

import codecompass.online as online
from codecompass.offline import EnsureResult
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo


def test_log_is_written_as_timestamped_json(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "Why retry?", config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs())
    path = Path(result.audit_log["log_file"])
    assert path.parent == tmp_path / "queries"
    assert re.fullmatch(r"\d{8}T\d{6}\d*Z-[0-9a-f]{8}\.json", path.name)
    on_disk = json.loads(path.read_text())
    assert on_disk == {k: v for k, v in result.audit_log.items() if k != "log_file"}


def test_stale_warning_is_recorded(monkeypatch, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg, idx = config(tmp_path), tmp_path / "idx"
    online.ask(repo.path, "Why retry?", config=cfg, index_dir=idx, **stubs())
    monkeypatch.setattr(online, "ensure_current", lambda *a, **k: EnsureResult(
        ok=False, status="failed", message="boom"))
    log = online.ask(repo.path, "Why retry?", config=cfg, index_dir=idx, **stubs()).audit_log
    assert log["index"]["stale"] is True
    assert log["index"]["stale_message"] == "boom"
    assert log["index"]["ensure_status"] == "failed"
