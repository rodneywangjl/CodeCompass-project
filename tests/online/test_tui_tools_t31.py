"""T3.1 tool count and /tools tests (tests-first).

Contract under test (Spec 004 AC-4.1 to 4.5; Plan 004 section 8; Articles V.4, VI.3):
  - after an answer on a terminal, one stderr line gives the number of tool calls that ran
  - only executed calls count: not malformed requests, refused requests or ignored calls
  - the exact line `/tools` lists them from the audit log; it is never sent to the model
  - everything the model wrote in a call is shown without control characters, and cut
  - a failed or interrupted question leaves the previous list in place
  - stdout stays the answer and nothing else
"""

import io
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.offline.models import EmbedderIdentity
from codecompass.online import tui
from codecompass.online import tui_view as view
from codecompass.online.tui import main, run_session
from tests.online.ask_support import CitingGenerator
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_reranker import StubReranker

GIT_LOG = {"round": 0, "tool": "git_log", "args": {"path": "src/auth.py", "n": 5},
           "cache_hit": False, "error": False,
           "result_summary": 'f00dbab 2024-03-14 Alice "fix"'}
OPEN = {"round": 1, "tool": "open_file", "args": {"path": "src/auth.py", "lines": "1-20"},
        "cache_hit": True, "error": False,
        "result_summary": "--- src/auth.py, lines 1-20 | python ---"}
FAILED = {"round": 2, "tool": "open_file", "args": {"path": "../x"}, "cache_hit": False,
          "error": True, "result_summary": "error: path outside the repository"}
MALFORMED = {"round": 0, "tool": None, "args": {}, "malformed": True, "cache_hit": False,
             "error": True, "result_summary": "malformed tool call"}
REFUSED = {"round": 3, "final_call": True, "ignored_calls": 1}
DISABLED = {"round": 0, "ignored_calls": 1, "reason": "tools disabled"}

COUNT_1 = "▸ 1 tool called — type /tools to see them"
COUNT_3 = "▸ 3 tools called — type /tools to see them"
COUNT_0 = "▸ No tools called"


# --- tui_view: counting and the /tools text (AC-4.1, 4.2, 4.3) ---------------------


def test_summary_line_wording():
    assert view.summary_line([]) == COUNT_0
    assert view.summary_line([GIT_LOG]) == COUNT_1
    assert view.summary_line([GIT_LOG, OPEN, FAILED]) == COUNT_3  # a failed call still ran


def test_only_executed_calls_are_counted():
    rounds = [GIT_LOG, MALFORMED, REFUSED, DISABLED]
    assert view.tool_calls(rounds) == [GIT_LOG]
    assert view.summary_line(rounds) == COUNT_1


def test_tools_text_lists_each_call_in_order_with_cache_state_and_result():
    text = view.format_tools([GIT_LOG, OPEN])
    lines = text.splitlines()
    assert lines[0] == "Tools called for the last question:"
    assert lines[1] == "round 0  git_log  path=src/auth.py n=5"
    assert lines[2] == '         cache miss · f00dbab 2024-03-14 Alice "fix"'
    assert lines[3] == "round 1  open_file  path=src/auth.py lines=1-20"
    assert lines[4] == "         cache hit · --- src/auth.py, lines 1-20 | python ---"


def test_a_failed_call_says_so():
    text = view.format_tools([FAILED])
    assert "         cache miss · failed · error: path outside the repository" in text.splitlines()


def test_malformed_refused_and_ignored_requests_get_a_line_each():
    lines = view.format_tools([GIT_LOG, MALFORMED, REFUSED, DISABLED]).splitlines()
    assert "round 0  malformed request, no tool ran" in lines
    assert "round 3  request refused: the round limit was reached" in lines
    assert "round 0  request ignored: tools are off in this mode" in lines
    assert sum(1 for line in lines if line.startswith("round ")) == 4  # every round accounted for


def test_no_calls_says_so():
    assert view.format_tools([]) == "No tools were called for the last question."


def test_text_from_the_model_has_no_control_characters_and_is_cut():
    nasty = dict(GIT_LOG, args={"path": "a\x1b[31mb\rc\x07d", "query": "x" * 300},
                 result_summary="ok\x1b]0;title\x07" + "y" * 300)
    text = view.format_tools([nasty])
    assert "\x1b" not in text and "\r" not in text and "\x07" not in text
    assert "x" * 101 not in text and "y" * 101 not in text
    assert "…" in text


def test_an_entry_without_optional_fields_does_not_break_the_text():
    bare = {"round": 0, "tool": "git_log", "args": {}}
    text = view.format_tools([bare])
    assert "round 0  git_log" in text


# --- run_session (AC-4.1, 4.2, 4.4, 4.5) -------------------------------------------


class In:
    def __init__(self, *lines, tty=False):
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


def session(lines, *, tty, rounds_by_question=None, boom=(), interrupt=()):
    """Run a session; the fake answer 'does tool calls' as rounds_by_question says."""
    rounds_by_question = rounds_by_question or {}
    state = {"rounds": None}
    asked, provider_calls = [], []

    def answer(question, on_draft=None):
        asked.append(question)
        if question in boom:
            raise RuntimeError("boom")
        if question in interrupt:
            raise KeyboardInterrupt
        state["rounds"] = rounds_by_question.get(question, [])
        return f"answer to {question}"

    def tool_rounds():
        provider_calls.append(1)
        return state["rounds"]

    stdout, stderr = Out(), Out(tty=tty)
    code = run_session(answer, stdin=In(*lines, tty=tty), stdout=stdout, stderr=stderr,
                       tool_rounds=tool_rounds)
    return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue(),
                           asked=asked, provider_calls=provider_calls)


def test_the_count_line_follows_the_answer_on_a_terminal():
    r = session(["q1\n"], tty=True, rounds_by_question={"q1": [GIT_LOG]})
    assert COUNT_1 in r.err
    assert r.out == "answer to q1\n"  # stdout is the answer and nothing else


def test_no_tools_on_a_terminal_says_so():
    r = session(["q1\n"], tty=True)
    assert COUNT_0 in r.err


def test_piped_input_has_no_count_line():
    r = session(["q1\n"], tty=False, rounds_by_question={"q1": [GIT_LOG]})
    assert "▸" not in r.err
    assert r.out == "answer to q1\n"


def test_slash_tools_lists_the_last_answered_question_and_is_not_a_question():
    r = session(["q1\n", "/tools\n"], tty=True, rounds_by_question={"q1": [GIT_LOG, OPEN]})
    assert "round 0  git_log  path=src/auth.py n=5" in r.err
    assert "round 1  open_file  path=src/auth.py lines=1-20" in r.err
    assert r.asked == ["q1"]  # never sent to the model
    assert r.out == "answer to q1\n"


def test_slash_tools_before_any_question():
    r = session(["/tools\n"], tty=True)
    assert "No question has been answered yet." in r.err
    assert r.asked == []


def test_slash_tools_after_a_question_without_tools():
    r = session(["q1\n", "/tools\n"], tty=True)
    assert "No tools were called for the last question." in r.err


def test_slash_tools_works_with_piped_input_and_stdout_stays_answers_only():
    r = session(["q1\n", "/tools\n"], tty=False, rounds_by_question={"q1": [GIT_LOG]})
    assert "round 0  git_log  path=src/auth.py n=5" in r.err
    assert r.out == "answer to q1\n"


def test_a_failed_question_leaves_the_previous_list_in_place():
    r = session(["q1\n", "boom\n", "/tools\n"], tty=True, boom=("boom",),
                rounds_by_question={"q1": [GIT_LOG]})
    assert "round 0  git_log" in r.err
    assert r.provider_calls == [1]  # asked for once, after q1 only
    assert r.err.count("▸ ") == 1  # no count line for the failed question


def test_an_interrupted_question_leaves_the_previous_list_in_place():
    r = session(["q1\n", "stop\n", "/tools\n"], tty=True, interrupt=("stop",),
                rounds_by_question={"q1": [GIT_LOG]})
    assert "round 0  git_log" in r.err
    assert r.provider_calls == [1]


def test_only_the_exact_line_is_a_command():
    r = session(["/tools now\n"], tty=True)
    assert r.asked == ["/tools now"]


def test_surrounding_spaces_are_ignored_like_for_exit():
    r = session(["q1\n", "  /tools  \n"], tty=True, rounds_by_question={"q1": [GIT_LOG]})
    assert r.asked == ["q1"]
    assert "round 0  git_log" in r.err


def test_without_a_tool_source_nothing_extra_is_printed():
    out, err = Out(), Out(tty=True)
    code = run_session(lambda q, on_draft=None: "a", stdin=In("q\n", tty=True),
                       stdout=out, stderr=err)
    assert code == 0
    assert "▸" not in err.getvalue()
    assert out.getvalue() == "a\n"


# --- main: the real audit log feeds the line and /tools (AC-4.1, 4.2, 4.4) ---------


@pytest.fixture
def world(tmp_path, monkeypatch):
    tmp = tmp_path.resolve()
    monkeypatch.setenv("HOME", str(tmp / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp / "home"))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "xdg"))
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    repo = build_history_repo(tmp / "repo")

    class Generator(CitingGenerator):
        def __init__(self, profile, *, server_url, timeout_seconds):
            super().__init__(before=['<tool>git_log(path="src/auth.py", n=5)</tool>'])
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
    (repo.path / "codecompass.toml").write_text(
        f'[embedder]\nmodel = "stub"\nrevision = "stub-{tmp.name}"\ndimension = 8\n'
        f'[reranker]\nrevision = "rerank-{tmp.name}"\n')
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(tmp=tmp, repo=repo)


QUESTION = "Why does authenticate retry?\n"


def test_main_reports_the_real_tool_call_through_slash_tools(world):
    stdout, stderr = Out(), Out()
    code = main(["--index-dir", str(world.tmp / "idx")],
                stdin=In(QUESTION, "/tools\n"), stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue()
    assert "round 0  git_log  path=src/auth.py n=5" in stderr.getvalue()
    assert "cache miss" in stderr.getvalue()
    assert "round 0" not in stdout.getvalue()


def test_main_shows_the_count_line_on_a_terminal(world, monkeypatch):
    monkeypatch.setattr(tui, "_start_warm_up", lambda *a, **k: None)
    stdout, stderr = Out(), Out(tty=True)
    code = main(["--no-draft", "--index-dir", str(world.tmp / "idx")],
                stdin=In(QUESTION, tty=True), stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue()
    assert COUNT_1 in stderr.getvalue()


def test_a_result_without_an_audit_log_counts_as_no_tool_calls(world, monkeypatch):
    monkeypatch.setattr(online, "ask", lambda *a, **k: SimpleNamespace(answer="plain"))
    stdout, stderr = Out(), Out()
    code = main(["--index-dir", str(world.tmp / "idx")],
                stdin=In("q?\n", "/tools\n"), stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue()
    assert stdout.getvalue() == "plain\n"
    assert "No tools were called for the last question." in stderr.getvalue()
