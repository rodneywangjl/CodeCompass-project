"""T2.5 (Spec 004) background warm-up: tests first.

Contract under test (Spec 004 AC-3.2, AC-3.3, AC-3.4):
  online.warm_up(repo_path, *, config, index_dir=None, embedder=None, reranker=None)
  - brings the index current and loads the embedder and re-ranker; prints nothing
  - the models it loads are the ones ask() then reuses (T0.1)
  codecompass (main):
  - on a terminal, starts warm_up once in a background thread after a good start-up
  - a question asked while it is still running waits for it and shows
    "Preparing index and models…"; one asked after shows nothing extra
  - a warm-up error is never shown by itself: the question runs and reports its own
  - piped input and failed start-ups start nothing; /exit does not wait for it
No model, no network: warm_up is a fake with events, the T1.2 `world` fixture
supplies the rest, and the stub models stand in for the real ones.
"""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.offline import status
from codecompass.online.tui import main
from tests.online.ask_support import config, stubs
from tests.online.test_model_reuse_tui_t01 import (  # noqa: F401 (fixture and helpers)
    ask_default_models, built, unique_config)
from tests.online.test_tui_main_t12 import In, Out, world  # noqa: F401 (fixture)
from tests.support.fixture_repo import build_history_repo


@pytest.fixture
def warm(monkeypatch):
    """A fake online.warm_up that records calls and can block or fail on demand."""
    w = SimpleNamespace(calls=[], started=threading.Event(), release=threading.Event(),
                        done=threading.Event(), block=False, error=None)

    def fake(repo_path, *, config, index_dir=None, **kw):
        w.calls.append(SimpleNamespace(repo=Path(repo_path), config=config,
                                       index_dir=index_dir))
        w.started.set()
        if w.block:
            w.release.wait(10)
        w.done.set()
        if w.error:
            raise w.error

    monkeypatch.setattr(online, "warm_up", fake)
    yield w
    w.release.set()


class WaitingIn(In):
    """A terminal whose first line only arrives once `gate` is set."""

    def __init__(self, gate, *lines):
        super().__init__(*lines, tty=True)
        self._gate = gate

    def readline(self):
        self._gate.wait(5)
        time.sleep(0.15)  # let the warm-up thread finish exiting
        return super().readline()


def run_main_in_thread(args, stdin):
    stdout, stderr, result = Out(), Out(tty=True), {}
    thread = threading.Thread(
        target=lambda: result.update(code=main(args, stdin=stdin, stdout=stdout,
                                               stderr=stderr)), daemon=True)
    thread.start()
    return thread, result, stdout, stderr


# --- the warm-up in the terminal -------------------------------------------------------


def test_a_terminal_session_starts_one_warm_up_for_the_repo_root(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path / "src")
    code, _, _ = world.run(["--index-dir", str(world.tmp / "idx")], "a?\n", "b?\n", tty=True)
    assert code == 0 and len(warm.calls) == 1
    assert warm.calls[0].repo == world.repo.path.resolve()
    assert str(warm.calls[0].index_dir) == str(world.tmp / "idx")
    assert warm.calls[0].config is world.asks[0].config  # the session's merged config


def test_a_question_asked_during_the_warm_up_waits_for_it(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    warm.block = True
    thread, result, stdout, stderr = run_main_in_thread([], In("q?\n", tty=True))
    assert warm.started.wait(5)
    time.sleep(0.3)
    assert world.asks == []  # the question is waiting, not running
    assert "Preparing index and models…" in stderr.getvalue()
    warm.release.set()
    thread.join(5)
    assert not thread.is_alive() and result["code"] == 0
    assert [a.question for a in world.asks] == ["q?"]
    assert stdout.getvalue() == "answer to q?\n"


def test_a_question_asked_after_the_warm_up_shows_nothing_extra(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    thread, result, stdout, stderr = run_main_in_thread([], WaitingIn(warm.done, "q?\n"))
    thread.join(5)
    assert result["code"] == 0 and stdout.getvalue() == "answer to q?\n"
    assert "Preparing" not in stderr.getvalue()


def test_a_warm_up_error_is_not_shown_by_itself(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    warm.error = RuntimeError("no index is available")
    thread, result, stdout, stderr = run_main_in_thread([], WaitingIn(warm.done, "q?\n"))
    thread.join(5)
    assert result["code"] == 0
    assert "no index is available" not in stderr.getvalue()
    assert [a.question for a in world.asks] == ["q?"]  # the question ran and reports its own
    assert stdout.getvalue() == "answer to q?\n"


def test_piped_input_starts_no_warm_up(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    world.run([], "q?\n", tty=False)
    assert warm.calls == [] and not warm.started.is_set()


@pytest.mark.parametrize("args", [["--profile", "nope"], ["/no/such/path"]])
def test_a_failed_start_up_starts_no_warm_up(world, warm, monkeypatch, args):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    code, _, _ = world.run(args, tty=True)
    assert code == 1 and warm.calls == []


def test_exit_does_not_wait_for_a_warm_up_that_is_still_running(world, warm, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    warm.block = True
    t0 = time.monotonic()
    code = main([], stdin=In("/exit\n", tty=True), stdout=Out(), stderr=Out(tty=True))
    assert code == 0 and time.monotonic() - t0 < 2
    assert warm.started.wait(5) and not warm.done.is_set()  # it was still running


# --- online.warm_up itself ---------------------------------------------------------------


def test_warm_up_brings_the_index_current_loads_the_models_and_prints_nothing(
        tmp_path, capsys):
    repo = build_history_repo(tmp_path / "repo")
    cfg, kit = config(tmp_path), stubs()
    assert status(repo.path, config=cfg.offline, index_dir=tmp_path / "idx").state != "current"
    online.warm_up(repo.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=kit["embedder"], reranker=kit["reranker"])
    assert status(repo.path, config=cfg.offline, index_dir=tmp_path / "idx").state == "current"
    assert len(kit["reranker"].calls) == 1  # the re-ranker was exercised once
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_the_models_warm_up_loads_are_the_ones_ask_reuses(tmp_path, built):  # noqa: F811
    repo = build_history_repo(tmp_path / "repo")
    cfg = unique_config(tmp_path)
    online.warm_up(repo.path, config=cfg, index_dir=tmp_path / "idx")
    ask_default_models(repo, cfg, tmp_path / "idx")
    ask_default_models(repo, cfg, tmp_path / "idx")
    assert len(built["embedder"]) == 1 and len(built["reranker"]) == 1


def test_warm_up_on_a_repository_that_cannot_be_indexed_raises_for_the_caller(tmp_path):
    kit = stubs()
    with pytest.raises(Exception) as failure:
        online.warm_up(tmp_path / "not-a-repo", config=config(tmp_path),
                       index_dir=tmp_path / "idx", embedder=kit["embedder"],
                       reranker=kit["reranker"])
    assert not isinstance(failure.value, NotImplementedError)  # a real failure, not the stub
