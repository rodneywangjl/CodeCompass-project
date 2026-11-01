"""T3.4 the look, --theme and --no-color tests (tests-first).

Contract under test (Spec 004 AC-5.3, 5.5, 5.6; Plan 004 section 8; Articles VI.3, VI.5):
  - the interface (prompt, startup lines, status, tool line and /tools, error: and
    warning: prefixes, the draft header) is coloured in its role, and its text never changes
  - with every colour removed, stderr is exactly what it is without colour
  - draft lines keep their marker and their dimming
  - stdout and stderr are coloured independently, each by its own stream
  - --no-color and NO_COLOR give plain text; --theme and CODECOMPASS_THEME choose colours only
  - nothing is coloured when the streams are not terminals
"""

import io
import re
from types import SimpleNamespace

import pytest

from codecompass.offline.models import EmbedderIdentity
from codecompass.online import tui
from codecompass.online import tui_view as view
from codecompass.online.citation import formatter
from codecompass.online.tui import main, run_session
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

TTY_FD = 7
S = view.Style("truecolor", "dark")
P = S.paint
SGR = re.compile(r"\x1b\[[0-9;]*m")

GIT_LOG = {"round": 0, "tool": "git_log", "args": {"path": "src/auth.py", "n": 5},
           "cache_hit": False, "error": False, "result_summary": 'f00dbab 2024-03-14 Alice "fix"'}
OPEN = {"round": 1, "tool": "open_file", "args": {"path": "src/auth.py", "lines": "1-20"},
        "cache_hit": True, "error": False,
        "result_summary": "--- src/auth.py, lines 1-20 | python ---"}
FAILED = {"round": 2, "tool": "open_file", "args": {"path": "../x"}, "cache_hit": False,
          "error": True, "result_summary": "error: path outside the repository"}
MALFORMED = {"round": 0, "tool": None, "args": {}, "malformed": True, "cache_hit": False,
             "error": True, "result_summary": "malformed tool call"}
REFUSED = {"round": 3, "final_call": True, "ignored_calls": 1}


@pytest.fixture(autouse=True)
def tty_is_fd_7(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: fd == TTY_FD)


# --- the tool text, painted by part (AC-5.3, AC-4.2) ---------------------------------


def test_the_count_line_is_painted_as_info():
    plain = view.summary_line([GIT_LOG])
    assert view.summary_line([GIT_LOG], S) == P(plain, "info")


def test_the_tools_text_is_painted_part_by_part():
    lines = view.format_tools([GIT_LOG, OPEN, FAILED, MALFORMED, REFUSED], S).split("\n")
    assert lines[0] == P("Tools called for the last question:", "muted")
    assert lines[1] == P("round 0", "muted") + "  " + P("git_log", "accent") + "  path=src/auth.py n=5"
    assert lines[2] == " " * 9 + P("cache miss", "muted") + ' · f00dbab 2024-03-14 Alice "fix"'
    assert lines[4] == " " * 9 + P("cache hit", "ok") + " · --- src/auth.py, lines 1-20 | python ---"
    assert lines[6] == (" " * 9 + P("cache miss", "muted") + " · " + P("failed", "danger")
                        + " · error: path outside the repository")
    assert P("round 0  malformed request, no tool ran", "warn") in lines
    assert P("round 3  request refused: the round limit was reached", "warn") in lines


def test_the_no_tools_text_is_muted():
    assert view.format_tools([], S) == P("No tools were called for the last question.", "muted")


@pytest.mark.parametrize("level", ["truecolor", "256", "none"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_stripping_the_tool_text_gives_the_plain_text(level, theme):
    style = view.Style(level, theme)
    rounds = [GIT_LOG, OPEN, FAILED, MALFORMED, REFUSED]
    assert view.strip_escapes(view.format_tools(rounds, style)) == view.format_tools(rounds)
    assert view.strip_escapes(view.summary_line(rounds, style)) == view.summary_line(rounds)


def test_without_a_style_the_tool_text_is_what_t31_pinned():
    assert view.summary_line([GIT_LOG]) == "▸ 1 tool called — type /tools to see them"
    assert view.format_tools([GIT_LOG]).splitlines()[1] == "round 0  git_log  path=src/auth.py n=5"


# --- run_session with a chrome style (AC-5.3) ----------------------------------------


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


def scripted(chrome):
    """One session that answers with tools, lists them, fails, is interrupted, shows a draft."""
    state = {"rounds": []}

    def answer(question, on_draft=None):
        if question == "boom":
            raise RuntimeError("boom")
        if question == "stop":
            raise KeyboardInterrupt
        if on_draft:
            on_draft("thinking about it\n")
        state["rounds"] = [GIT_LOG, FAILED] if question == "tools" else []
        return f"answer to {question}"

    stdout, stderr = Out(), Out(tty=True)
    run_session(answer, stdin=In("tools\n", "/tools\n", "boom\n", "stop\n", "/tools\n", tty=True),
                stdout=stdout, stderr=stderr, draft=True,
                tool_rounds=lambda: state["rounds"], chrome=chrome)
    return stdout.getvalue(), stderr.getvalue()


def test_the_chrome_never_changes_stdout_or_any_word_of_stderr():
    plain_out, plain_err = scripted(None)
    styled_out, styled_err = scripted(S)
    assert styled_out == plain_out
    assert view.strip_escapes(styled_err) == view.strip_escapes(plain_err)
    assert styled_err != plain_err


def test_a_style_with_no_colour_behaves_like_no_style():
    assert scripted(view.Style("none", "dark")) == scripted(None)


def test_each_part_of_the_interface_is_painted_in_its_role():
    _, err = scripted(S)
    assert P(">", "accent") + " " in err  # the prompt
    assert P(tui.STATUS, "info") in err  # Thinking…
    assert P(view.summary_line([GIT_LOG, FAILED]), "info") in err  # the count line
    assert P("error:", "danger") + " boom\n" in err
    assert P(tui.DRAFT_HEADER, "warn") in err
    assert P("Tools called for the last question:", "muted") in err  # /tools
    assert P("git_log", "accent") in err


def test_draft_lines_keep_their_marker_and_their_dimming():
    _, err = scripted(S)
    assert f"{tui.DIM}{tui.DRAFT_MARK}" in err
    assert P(tui.DRAFT_MARK, "muted") not in err  # the chrome does not touch draft lines


def test_hints_and_notices_stay_plain():
    _, err = scripted(S)
    assert "Interrupted.\n" in err


# --- main: stdout and stderr, the flags, the environment (AC-5.2, 5.5, 5.6) ----------


class TtyOut(io.StringIO):
    """Stands in for a terminal: it has a file descriptor that os.isatty accepts."""

    def fileno(self):
        return TTY_FD

    def isatty(self):
        return True


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
    w = SimpleNamespace(tmp=tmp, repo=repo, healthy=True)

    class Generator(StubGenerator):
        def __init__(self, profile, *, server_url, timeout_seconds):
            super().__init__(["It retries [1].\n\nSources\n"
                              "[1] src/nowhere.py, lines 1-3 (indexed at abc1234)\n"])
            self.profile = profile

        def health_check(self):
            return w.healthy

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
    return w


def run_main(world, monkeypatch, argv=(), env=None, stdin_tty=True, stdout=None, stderr=None):
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    stdout, stderr = stdout or TtyOut(), stderr or TtyOut()
    code = main(["--no-draft", "--index-dir", str(world.tmp / "idx"), *argv],
                stdin=In("Why does authenticate retry?\n", tty=stdin_tty),
                stdout=stdout, stderr=stderr)
    return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue())


DARK_TRUE = {"COLORTERM": "truecolor", "CODECOMPASS_THEME": "dark"}


def test_the_startup_lines_prompt_and_status_are_painted_and_no_word_changes(world, monkeypatch):
    plain = run_main(world, monkeypatch, ["--no-color"], DARK_TRUE)
    coloured = run_main(world, monkeypatch, env=DARK_TRUE)
    assert plain.code == coloured.code == 0, coloured.err
    assert not SGR.search(plain.err)
    assert view.strip_escapes(coloured.err) == plain.err  # not a word changed
    first = plain.err.split("\n")[0]  # "codecompass: repo: <root>"
    assert first.startswith("codecompass: repo: ")
    assert (P("codecompass:", "accent") + " " + P(first[len("codecompass: "):], "muted")
            + "\n") in coloured.err
    assert P("Type a question. /exit or Ctrl-D to quit.", "muted") in coloured.err
    assert P(">", "accent") + " " in coloured.err
    assert P(tui.STATUS, "info") in coloured.err
    assert "▸" in coloured.err and P(view.summary_line([]), "info") in coloured.err


def test_no_color_flag_and_no_color_variable_give_the_same_plain_output(world, monkeypatch):
    flag = run_main(world, monkeypatch, ["--no-color"], {"COLORTERM": "truecolor"})
    monkeypatch.delenv("COLORTERM")
    variable = run_main(world, monkeypatch, env={"COLORTERM": "truecolor", "NO_COLOR": "1"})
    assert (flag.out, flag.err) == (variable.out, variable.err)
    assert not SGR.search(flag.out) and not SGR.search(flag.err)
    assert formatter.BANNER in flag.out  # the banner is there without colour too


def test_the_theme_flag_changes_colours_only(world, monkeypatch):
    light = view.Style("truecolor", "light")
    dark = run_main(world, monkeypatch, ["--theme", "dark"], {"COLORTERM": "truecolor"})
    lit = run_main(world, monkeypatch, ["--theme", "light"], {"COLORTERM": "truecolor"})
    assert view.strip_escapes(dark.out) == view.strip_escapes(lit.out)
    assert view.strip_escapes(dark.err) == view.strip_escapes(lit.err)
    assert P(formatter.BANNER, "danger") in dark.out.split("\n")
    assert light.paint(formatter.BANNER, "danger") in lit.out.split("\n")
    assert light.paint(">", "accent") + " " in lit.err


def test_the_flag_beats_the_environment_variable(world, monkeypatch):
    light = view.Style("truecolor", "light")
    out = run_main(world, monkeypatch, ["--theme", "light"],
                   {"COLORTERM": "truecolor", "CODECOMPASS_THEME": "dark"})
    assert light.paint(formatter.BANNER, "danger") in out.out.split("\n")


def test_an_unknown_theme_flag_is_a_startup_error(world, monkeypatch):
    out = run_main(world, monkeypatch, ["--theme", "neon"], {"COLORTERM": "truecolor"})
    assert out.code == 1
    assert "auto, dark, light" in out.err
    assert out.out == ""


def test_stdout_and_stderr_are_coloured_independently(world, monkeypatch):
    only_err = run_main(world, monkeypatch, env=DARK_TRUE, stdout=Out())
    assert not SGR.search(only_err.out)
    assert P(">", "accent") + " " in only_err.err
    only_out = run_main(world, monkeypatch, env=DARK_TRUE, stderr=Out(), stdin_tty=False)
    assert P(formatter.BANNER, "danger") in only_out.out.split("\n")
    assert not SGR.search(only_out.err)


def test_fully_piped_output_has_no_colour_whatever_the_environment(world, monkeypatch):
    out = run_main(world, monkeypatch, env=DARK_TRUE, stdin_tty=False,
                   stdout=Out(), stderr=Out())
    assert out.code == 0, out.err
    assert not SGR.search(out.out) and not SGR.search(out.err)


def test_the_warning_prefix_is_painted_and_the_message_is_not(world, monkeypatch):
    world.healthy = False
    out = run_main(world, monkeypatch, env=DARK_TRUE)
    assert P("warning:", "warn") + " llama-server is not reachable at " in out.err


def test_a_startup_error_prefix_is_painted(world, monkeypatch):
    for name, value in DARK_TRUE.items():
        monkeypatch.setenv(name, value)
    stdout, stderr = TtyOut(), TtyOut()
    code = main(["/definitely/not/a/path"], stdin=In(tty=True), stdout=stdout, stderr=stderr)
    assert code == 1
    assert stderr.getvalue().startswith(P("error:", "danger") + " path does not exist: ")


def test_the_waiting_for_warm_up_status_is_painted(world, monkeypatch):
    monkeypatch.setattr(tui, "_start_warm_up",
                        lambda *a, **k: SimpleNamespace(is_alive=lambda: True, join=lambda: None))
    out = run_main(world, monkeypatch, env=DARK_TRUE)
    assert out.code == 0, out.err
    assert f"{tui.CLEAR_LINE}{P('Preparing index and models…', 'info')}" in out.err
    assert f"{tui.CLEAR_LINE}{P(tui.STATUS, 'info')}" in out.err


def test_help_mentions_the_new_options(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    text = capsys.readouterr().out
    assert "--theme" in text and "--no-color" in text and "NO_COLOR" in text
