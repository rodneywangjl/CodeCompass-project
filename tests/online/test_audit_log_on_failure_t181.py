"""T18.1 audit log on failure tests (tests-first); 2 Nov development test, problem 7.

Contract under test (Spec AC-7.6; Article V.4):
  - when a question fails after work has started (indexing, retrieval,
    re-ranking, generation), ask() still writes the audit log, with
    error.type, error.message and the timings collected so far, and then
    re-raises the same exception, unchanged
  - Ctrl-C (KeyboardInterrupt) is logged and re-raised the same way
  - if writing the log fails while handling an error, the caller gets the
    original error, not the logging error
  - the log of a question that succeeds has no "error" key (unchanged)
  - errors before any work starts (a bad setting) write no log
  - the CLI still prints one "error:" line and exits 1, and the log exists
"""

import functools
import json

import pytest

import codecompass.online as online
from codecompass.online import cli
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator


class FailingGenerator(StubGenerator):
    """Raises *error* on every generate call, as a timed-out llama-server would."""

    def __init__(self, error: BaseException) -> None:
        super().__init__(["unused"])
        self.error = error

    def generate(self, messages, *, on_text=None):
        super().generate(messages)
        raise self.error


def logs(tmp_path):
    folder = tmp_path / "queries"
    return sorted(folder.glob("*.json")) if folder.exists() else []


def only_log(tmp_path):
    files = logs(tmp_path)
    assert len(files) == 1, f"expected one audit log, found {len(files)}"
    return json.loads(files[0].read_text(encoding="utf-8"))


def ask_failing(tmp_path, error):
    repo = build_history_repo(tmp_path / "repo")
    return online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                      index_dir=tmp_path / "idx", **stubs(FailingGenerator(error)))


def test_the_same_error_reaches_the_caller(tmp_path):
    error = TimeoutError("llama-server timed out after 120s")
    with pytest.raises(TimeoutError) as raised:
        ask_failing(tmp_path, error)
    assert raised.value is error


def test_a_failed_question_still_writes_its_log(tmp_path):
    with pytest.raises(TimeoutError):
        ask_failing(tmp_path, TimeoutError("llama-server timed out after 120s"))
    log = only_log(tmp_path)
    assert log["question"] == "Why does authenticate retry?"
    assert log["error"] == {"type": "TimeoutError",
                            "message": "llama-server timed out after 120s"}


def test_the_log_shows_how_far_it_got(tmp_path):
    with pytest.raises(TimeoutError):
        ask_failing(tmp_path, TimeoutError("timed out"))
    log = only_log(tmp_path)
    assert log["retrieved"], "retrieval finished before the generator failed"
    assert log["timings"]["generation"] > 0, "it stopped during generation"
    assert log["timings"]["total"] >= log["timings"]["generation"]


def test_a_failure_while_indexing_is_logged(monkeypatch, tmp_path):
    def broken(*args, **kwargs):
        raise RuntimeError("index lock timed out")
    monkeypatch.setattr(online, "ensure_current", broken)
    with pytest.raises(RuntimeError, match="index lock timed out"):
        online.ask(tmp_path / "repo", "Why retry?", config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs())
    assert only_log(tmp_path)["error"]["type"] == "RuntimeError"


def test_ctrl_c_is_logged_and_still_stops_the_question(tmp_path):
    with pytest.raises(KeyboardInterrupt):
        ask_failing(tmp_path, KeyboardInterrupt())
    assert only_log(tmp_path)["error"]["type"] == "KeyboardInterrupt"


def test_if_the_log_cannot_be_written_the_original_error_wins(monkeypatch, tmp_path):
    def disk_full(*args, **kwargs):
        raise OSError("No space left on device")
    monkeypatch.setattr(online, "write_log", disk_full)
    with pytest.raises(TimeoutError, match="timed out"):
        ask_failing(tmp_path, TimeoutError("timed out"))


def test_a_successful_answer_has_no_error_in_its_log(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs())
    assert "error" not in result.audit_log
    assert "error" not in only_log(tmp_path)


def test_a_bad_setting_before_any_work_writes_no_log(tmp_path):
    with pytest.raises(ValueError, match="pipeline.mode"):
        online.ask(tmp_path / "repo", "Why retry?", config=config(tmp_path, mode="bogus"),
                   index_dir=tmp_path / "idx", **stubs())
    assert logs(tmp_path) == []


def test_the_cli_reports_the_error_and_the_log_exists(monkeypatch, capsys, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    failing = FailingGenerator(TimeoutError("llama-server timed out after 120s"))
    monkeypatch.setattr(cli, "ask", functools.partial(online.ask, **stubs(failing)))
    monkeypatch.setattr(cli, "load_online_config", lambda path: config(tmp_path))
    code = cli.main(["ask", str(repo.path), "Why does authenticate retry?",
                     "--index-dir", str(tmp_path / "idx")])
    err = capsys.readouterr().err
    assert code == 1
    assert "error: llama-server timed out after 120s" in err
    assert only_log(tmp_path)["error"]["type"] == "TimeoutError"
