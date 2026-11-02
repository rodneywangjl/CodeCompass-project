"""T4.1 live tool lines and --plain tests (tests-first).

Contract under test (Spec 004 AC-6.1, 6.2, 6.6; Plan 004 section 9; Article V.4):
  - run_agent / ask take an optional on_tool(entry): called once per executed tool call, in
    order, with a deep copy of its audit record; never for malformed, refused or ignored
    requests; with None everything is unchanged
  - tool_lines gives the "●" line and the "⎿" line of one call, cleaned and cut, painted by role
  - in live mode (a real terminal, not --plain, TERM not dumb) the lines appear on stderr as each
    call finishes; everywhere else the output is what it was
"""

import io
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.online import tui
from codecompass.online import tui_live as live
from codecompass.online import tui_view as view
from codecompass.online.agent.harness import run_agent
from codecompass.online.tui import main, run_session
from codecompass.offline.models import EmbedderIdentity
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import (
    MALFORMED_TOOL_CALL, TOOL_CALL_BLAME, TOOL_CALL_LOG, StubGenerator)
from tests.support.stub_reranker import StubReranker

TTY_FD = 7
QUESTION = "Why does authenticate retry?"
S = view.Style("truecolor", "dark")
P = S.paint

GIT_LOG = {"round": 0, "tool": "git_log", "args": {"path": "src/auth.py", "n": 5},
           "cache_hit": False, "error": False, "result_summary": 'f00dbab 2024-03-14 Alice "fix"'}
OPEN = {"round": 1, "tool": "open_file", "args": {"path": "src/auth.py", "lines": "1-20"},
        "cache_hit": True, "error": False,
        "result_summary": "--- src/auth.py, lines 1-20 | python ---"}
FAILED = {"round": 2, "tool": "open_file", "args": {"path": "../x"}, "cache_hit": False,
          "error": True, "result_summary": "error: path outside the repository"}


@pytest.fixture(autouse=True)
def tty_is_fd_7(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: fd == TTY_FD)


# --- on_tool in the harness (AC-6.2) ----------------------------------------------------


def agent(responses, *, max_rounds=3, tools_enabled=True, on_tool=None):
    return run_agent(StubGenerator(responses), QUESTION, CHUNKS, run_tool=FakeTools(),
                     max_rounds=max_rounds, tools_enabled=tools_enabled, on_tool=on_tool)


def test_on_tool_is_called_once_per_executed_call_in_order():
    seen = []
    run = agent([TOOL_CALL_LOG, TOOL_CALL_BLAME, ANSWER], on_tool=seen.append)
    assert [entry["tool"] for entry in seen] == ["git_log", "git_blame"]
    assert seen == run.rounds  # the same records the audit log gets


def test_on_tool_is_not_called_for_a_malformed_request():
    seen = []
    run = agent([MALFORMED_TOOL_CALL, ANSWER], on_tool=seen.append)
    assert any(entry.get("malformed") for entry in run.rounds)
    assert seen == []


def test_on_tool_is_not_called_for_a_request_refused_after_the_round_limit():
    seen = []
    run = agent([TOOL_CALL_LOG, ANSWER], max_rounds=0, on_tool=seen.append)
    assert any(entry.get("final_call") for entry in run.rounds)
    assert seen == []


def test_on_tool_is_not_called_when_tools_are_off():
    seen = []
    run = agent([TOOL_CALL_LOG, ANSWER], tools_enabled=False, on_tool=seen.append)
    assert any(entry.get("reason") == "tools disabled" for entry in run.rounds)
    assert seen == []


def test_a_callback_only_observes():
    plain = agent([TOOL_CALL_LOG, ANSWER])
    observed = agent([TOOL_CALL_LOG, ANSWER], on_tool=lambda entry: None)
    assert (plain.answer, plain.rounds, plain.generator_calls) == (
        observed.answer, observed.rounds, observed.generator_calls)


def test_the_callback_gets_a_copy_it_cannot_use_to_change_the_audit_record():
    def vandal(entry):
        entry["tool"] = "evil"
        entry["args"]["path"] = "/etc/passwd"

    run = agent([TOOL_CALL_LOG, ANSWER], on_tool=vandal)
    assert run.rounds[0]["tool"] == "git_log"
    assert run.rounds[0]["args"]["path"] == "src/auth.py"


# --- on_tool through ask() (AC-6.2) -----------------------------------------------------

TOOL_REQUEST = '<tool>git_log(path="src/auth.py", n=5)</tool>'


def asked(tmp_path, name, on_tool):
    repo = build_history_repo(tmp_path / name / "repo")
    return online.ask(repo.path, QUESTION, config=config(tmp_path / name),
                      index_dir=tmp_path / name / "idx", on_tool=on_tool,
                      **stubs(CitingGenerator(before=[TOOL_REQUEST])))


def test_ask_reports_each_tool_call_and_changes_nothing_else(tmp_path):
    seen = []
    with_callback = asked(tmp_path, "a", seen.append)
    without = asked(tmp_path, "b", None)
    assert len(seen) == 1
    assert seen[0]["tool"] == "git_log" and seen[0]["args"] == {"path": "src/auth.py", "n": 5}
    assert seen[0] == with_callback.audit_log["tool_calls"][0]
    for key in ("tool_calls", "generator_calls", "citation"):
        assert with_callback.audit_log[key] == without.audit_log[key]
    assert with_callback.answer == without.answer


# --- tool_lines (AC-6.2) ----------------------------------------------------------------


def test_the_two_lines_of_a_call():
    assert live.tool_lines(GIT_LOG) == ["● git_log(path=src/auth.py, n=5)",
                                        '  ⎿ f00dbab 2024-03-14 Alice "fix"']


def test_a_failed_call_says_so():
    assert live.tool_lines(FAILED) == ["● open_file(path=../x)",
                                       "  ⎿ failed · error: path outside the repository"]


def test_a_call_with_no_output_or_no_arguments():
    quiet = dict(GIT_LOG, args={}, result_summary="")
    assert live.tool_lines(quiet) == ["● git_log()", "  ⎿ (no output)"]
    assert live.tool_lines({"tool": "git_log"}) == ["● git_log()", "  ⎿ (no output)"]


def test_text_from_the_model_is_cleaned_and_cut():
    nasty = dict(GIT_LOG, args={"path": "a\x1b[31mb\rc\x07d", "query": "x" * 300},
                 result_summary="ok\x1b]0;title\x07" + "y" * 300)
    text = "\n".join(live.tool_lines(nasty))
    assert "\x1b" not in text and "\r" not in text and "\x07" not in text
    assert "x" * 101 not in text and "y" * 101 not in text
    assert "…" in text


def test_the_lines_are_painted_by_role_and_strip_back_to_the_plain_lines():
    first, second = live.tool_lines(GIT_LOG, S)
    assert first == P("●", "accent") + " git_log(path=src/auth.py, n=5)"
    assert second == "  " + P("⎿", "muted") + ' f00dbab 2024-03-14 Alice "fix"'
    _, failed = live.tool_lines(FAILED, S)
    assert failed == ("  " + P("⎿", "muted") + " " + P("failed", "danger")
                      + " · error: path outside the repository")
    for entry in (GIT_LOG, OPEN, FAILED):
        painted = [view.strip_escapes(line) for line in live.tool_lines(entry, S)]
        assert painted == live.tool_lines(entry)


# --- is_terminal (AC-6.1) ---------------------------------------------------------------


class TtyOut(io.StringIO):
    """Stands in for a terminal: it has a file descriptor that os.isatty accepts."""

    def fileno(self):
        return TTY_FD

    def isatty(self):
        return True


class FakeTty(io.StringIO):
    """isatty() is true but there is no file descriptor, like the streams of earlier tests."""

    def isatty(self):
        return True


class Pipe(io.StringIO):
    def fileno(self):
        return 3


def test_a_real_terminal_is_a_terminal():
    assert live.is_terminal(TtyOut(), {}) is True
    assert live.is_terminal(TtyOut(), {"TERM": "xterm-256color"}) is True


@pytest.mark.parametrize("stream, env", [
    (TtyOut(), {"TERM": "dumb"}), (io.StringIO(), {}), (FakeTty(), {}), (Pipe(), {}),
])
def test_everything_else_is_not(stream, env):
    assert live.is_terminal(stream, env) is False


# --- run_session (AC-6.2, AC-6.6) -------------------------------------------------------


class In:
    def __init__(self, *lines, tty=True):
        self._lines, self._tty = list(lines), tty

    def isatty(self):
        return self._tty

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class Out(io.StringIO):
    def __init__(self, tty=False):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


def live_session(*, live_tools, tty=True, chrome=None, fail=False, entries=(GIT_LOG, OPEN)):
    def answer(question, on_draft=None, on_tool=None):
        if on_tool:
            for entry in entries:
                on_tool(entry)
        if fail:
            raise RuntimeError("boom")
        return "the answer"

    stdout, stderr = Out(), Out(tty=tty)
    run_session(answer, stdin=In("q\n", tty=tty), stdout=stdout, stderr=stderr,
                live_tools=live_tools, chrome=chrome)
    return stdout.getvalue(), stderr.getvalue()


def test_each_call_clears_the_status_line_writes_its_lines_and_shows_the_status_again():
    out, err = live_session(live_tools=True)
    first = "\n".join(live.tool_lines(GIT_LOG)) + "\n"
    second = "\n".join(live.tool_lines(OPEN)) + "\n"
    assert f"{tui.CLEAR_LINE}{first}{tui.STATUS}" in err
    assert f"{tui.CLEAR_LINE}{second}{tui.STATUS}" in err
    assert err.index(first) < err.index(second)
    assert out == "the answer\n"  # stdout is the answer and nothing else


def test_the_lines_and_the_status_are_painted_with_a_chrome_style():
    _, err = live_session(live_tools=True, chrome=S)
    first = "\n".join(live.tool_lines(GIT_LOG, S)) + "\n"
    assert f"{tui.CLEAR_LINE}{first}{P(tui.STATUS, 'info')}" in err


def test_without_live_tools_the_answer_is_called_the_old_way():
    def strict(question, on_draft=None):  # no on_tool parameter: passing one would fail
        return "the answer"

    out, err = Out(), Out(tty=True)
    run_session(strict, stdin=In("q\n"), stdout=out, stderr=err)
    assert out.getvalue() == "the answer\n"
    assert "●" not in err.getvalue()


def test_when_stderr_is_not_a_terminal_nothing_is_passed_or_shown():
    def strict(question, on_draft=None):
        return "the answer"

    out, err = Out(), Out(tty=False)
    run_session(strict, stdin=In("q\n", tty=False), stdout=out, stderr=err, live_tools=True)
    assert out.getvalue() == "the answer\n"
    assert err.getvalue() == ""


def test_a_question_that_fails_after_a_tool_call_still_reports_the_error():
    _, err = live_session(live_tools=True, fail=True)
    assert "● git_log(path=src/auth.py, n=5)" in err
    assert "error: boom\n" in err


# --- main (AC-6.1, AC-6.2, AC-6.6) -------------------------------------------------------


@pytest.fixture
def world(tmp_path, monkeypatch):
    tmp = tmp_path.resolve()
    monkeypatch.setenv("HOME", str(tmp / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp / "home"))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "xdg"))
    for name in ("GENERATOR_PROFILE", "NO_COLOR", "COLORTERM", "TERM", "WT_SESSION",
                 "COLORFGBG", "CODECOMPASS_THEME"):
        monkeypatch.delenv(name, raising=False)
    repo = build_history_repo(tmp / "repo")

    class Generator(CitingGenerator):
        def __init__(self, profile, *, server_url, timeout_seconds):
            super().__init__(before=[TOOL_REQUEST])
            self.profile = profile

        def health_check(self):
            return True

    class Embedder(StubEmbedder):
        def __init__(self, embedder_config):
            super().__init__(embedder_config.dimension)
            self.identity = EmbedderIdentity(model=embedder_config.model,
                                             revision=embedder_config.revision,
                                             dimension=embedder_config.dimension)

    class Reranker(StubReranker):
        def __init__(self, reranker_config):
            super().__init__()

    monkeypatch.setattr("codecompass.online.generator.llama.LlamaServerGenerator", Generator)
    monkeypatch.setattr("codecompass.offline.embedding.CodeEmbedder", Embedder)
    monkeypatch.setattr("codecompass.online.retrieval.reranker.BgeReranker", Reranker)
    monkeypatch.setattr(tui, "_start_warm_up", lambda *a, **k: None)
    (repo.path / "codecompass.toml").write_text(
        f'[embedder]\nmodel = "stub"\nrevision = "stub-{tmp.name}"\ndimension = 8\n'
        f'[reranker]\nrevision = "rerank-{tmp.name}"\n')
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(tmp=tmp)


def run_main(world, argv=(), stdout=None, stderr=None, stdin_tty=True):
    stdout, stderr = stdout or TtyOut(), stderr or TtyOut()
    code = main(["--no-draft", "--index-dir", str(world.tmp / "idx"), *argv],
                stdin=In(QUESTION + "\n", "/tools\n", tty=stdin_tty),
                stdout=stdout, stderr=stderr)
    return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue())


def test_on_a_live_terminal_the_real_tool_call_is_shown_as_it_runs(world):
    r = run_main(world)
    assert r.code == 0, r.err
    assert "● git_log(path=src/auth.py, n=5)" in r.err
    assert "  ⎿ " in r.err
    assert "▸ 1 tool called" in r.err  # the count line and /tools are unchanged
    assert "round 0  git_log" in r.err
    assert "●" not in r.out  # stdout is still only the answer


def test_plain_turns_the_live_lines_off(world):
    r = run_main(world, ["--plain"])
    assert "●" not in r.err and "▸ 1 tool called" in r.err


def test_a_stand_in_terminal_without_a_descriptor_gets_the_old_output(world):
    r = run_main(world, stderr=FakeTty())
    assert "●" not in r.err


def test_piped_output_gets_the_old_output(world):
    r = run_main(world, stdout=Out(), stderr=Out(), stdin_tty=False)
    assert "●" not in r.err and "●" not in r.out


def test_a_dumb_terminal_gets_the_old_output(world, monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    assert "●" not in run_main(world).err


def test_help_mentions_plain(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "--plain" in capsys.readouterr().out
