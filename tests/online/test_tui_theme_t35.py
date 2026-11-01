"""T3.5 /theme command tests (tests-first).

Contract under test (Spec 004 AC-5.7; Plan 004 section 8; Q13 to Q15):
  - /theme and /theme X are commands, never questions; they reply on stderr
  - none turns colour off and rose-pine turns it on, for everything printed afterwards,
    on both streams, each only if that stream can show colour
  - rose-pine overrides NO_COLOR and --no-color, but not what the terminal can show
  - the choice lasts for the session and writes nothing to disk
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
SGR = re.compile(r"\x1b\[[0-9;]*m")
UNAVAILABLE = ("Colour is not available here: neither stdout nor stderr is a terminal "
               "that can show colour.")


@pytest.fixture(autouse=True)
def tty_is_fd_7(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: fd == TTY_FD)


def on(theme="dark"):
    return view.Style("truecolor", theme)


# --- Style.capability and ThemeSwitch (AC-5.7) ---------------------------------------


def test_a_style_remembers_what_its_stream_can_show():
    assert view.Style("truecolor", "dark").capability == "truecolor"
    assert view.Style("none", "dark").capability == "none"
    assert view.Style("none", "dark", capability="256").capability == "256"


def test_a_style_switched_off_paints_nothing_but_keeps_its_capability():
    style = view.Style("none", "dark", capability="truecolor")
    assert style.paint("x", "accent") == "x"
    assert style.answer("See [1].") == "See [1]."
    assert style.capability == "truecolor"


def test_state_names_the_theme_and_the_variant():
    assert view.ThemeSwitch("dark", [on()]).state() == "rose-pine (dark)"
    assert view.ThemeSwitch("light", [on("light")]).state() == "rose-pine (light)"
    assert view.ThemeSwitch("dark", [view.Style("none", "dark", "truecolor")]).state() == "none"
    assert view.ThemeSwitch("dark", []).state() == "none"


def test_no_argument_shows_the_current_choice_and_the_options():
    assert view.ThemeSwitch("dark", [on()]).command("") == (
        "Theme: rose-pine (dark). Choices: none, rose-pine.")
    assert view.ThemeSwitch("dark", []).command("") == "Theme: none. Choices: none, rose-pine."


def test_none_switches_every_style_off():
    out, err = on(), on()
    switch = view.ThemeSwitch("dark", [out, err])
    assert switch.command("none") == "Theme: none."
    assert out.level == err.level == "none"
    assert switch.state() == "none"


def test_rose_pine_restores_each_styles_own_capability():
    out = view.Style("none", "dark", capability="truecolor")
    err = view.Style("none", "dark", capability="256")
    switch = view.ThemeSwitch("dark", [out, err])
    assert switch.command("rose-pine") == "Theme: rose-pine (dark)."
    assert (out.level, err.level) == ("truecolor", "256")


def test_rose_pine_names_the_light_variant_when_that_is_the_theme():
    style = view.Style("none", "light", capability="truecolor")
    assert view.ThemeSwitch("light", [style]).command("rose-pine") == "Theme: rose-pine (light)."


def test_choosing_the_current_theme_again_changes_nothing():
    style = on()
    switch = view.ThemeSwitch("dark", [style])
    assert switch.command("rose-pine") == "Theme: rose-pine (dark)."
    assert style.level == "truecolor"


def test_without_any_colour_terminal_rose_pine_is_refused():
    switch = view.ThemeSwitch("dark", [])
    assert switch.command("rose-pine") == UNAVAILABLE
    assert switch.state() == "none"


@pytest.mark.parametrize("argument", ["neon", "NONE", "rose pine", "none now", "Rose-Pine"])
def test_an_unknown_argument_changes_nothing(argument):
    style = on()
    switch = view.ThemeSwitch("dark", [style])
    assert switch.command(argument) == (
        f"Unknown theme {argument!r}. Choices: none, rose-pine.")
    assert style.level == "truecolor"


# --- run_session (AC-5.7) -------------------------------------------------------------


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


ANSWER = "See [1]."


def session(lines, *, tty=True, theme=None, style=None, chrome=None):
    asked = []

    def answer(question, on_draft=None):
        asked.append(question)
        return ANSWER

    stdout, stderr = Out(), Out(tty=tty)
    run_session(answer, stdin=In(*lines, tty=tty), stdout=stdout, stderr=stderr,
                theme=theme, style=style, chrome=chrome)
    return SimpleNamespace(asked=asked, out=stdout.getvalue(), err=stderr.getvalue())


def test_theme_lines_are_commands_and_reply_on_stderr():
    switch = view.ThemeSwitch("dark", [on()])
    r = session(["/theme\n", "/theme none\n", "/theme neon\n"], theme=switch)
    assert r.asked == []
    assert r.out == ""
    assert "Theme: rose-pine (dark). Choices: none, rose-pine.\n" in r.err
    assert "Theme: none.\n" in r.err
    assert "Unknown theme 'neon'. Choices: none, rose-pine.\n" in r.err


def test_the_command_works_with_piped_input():
    r = session(["/theme rose-pine\n"], tty=False, theme=view.ThemeSwitch("dark", []))
    assert r.err == UNAVAILABLE + "\n"
    assert r.asked == [] and r.out == ""


def test_switching_between_questions_changes_the_colour_of_what_follows():
    out, err = on(), on()
    switch = view.ThemeSwitch("dark", [out, err])
    r = session(["q1\n", "/theme none\n", "q2\n", "/theme rose-pine\n", "q3\n"],
                theme=switch, style=out, chrome=err)
    coloured = on().answer(ANSWER)
    assert coloured != ANSWER
    assert r.out == f"{coloured}\n{ANSWER}\n{coloured}\n"  # earlier output is left as it was
    assert r.asked == ["q1", "q2", "q3"]
    assert on().paint(">", "accent") + " " in r.err  # coloured prompt before and after
    assert "> " in r.err  # a plain prompt (the coloured one has an escape after the >)
    assert "Theme: none.\n" in r.err  # the reply that turned colour off is plain
    assert on().paint("Theme: rose-pine (dark).", "muted") in r.err  # and the one that turned it on is not


def test_the_interface_goes_plain_while_the_theme_is_none():
    out, err = on(), on()
    switch = view.ThemeSwitch("dark", [out, err])
    r = session(["/theme none\n", "q1\n"], theme=switch, style=out, chrome=err)
    after_none = r.err.split("Theme: none.\n", 1)[1]
    assert not SGR.search(after_none)  # prompt, status line and tool line are all plain
    assert r.out == ANSWER + "\n"


def test_without_a_theme_switch_theme_is_just_a_line():
    r = session(["/theme none\n"])
    assert r.asked == ["/theme none"]


# --- main (AC-5.7) --------------------------------------------------------------------


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

    class Generator(StubGenerator):
        def __init__(self, profile, *, server_url, timeout_seconds):
            super().__init__(["It retries [1].\n\nSources\n"
                              "[1] src/nowhere.py, lines 1-3 (indexed at abc1234)\n"])
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


QUESTION = "Why does authenticate retry?\n"
DARK_TRUE = {"COLORTERM": "truecolor", "CODECOMPASS_THEME": "dark"}


def run_main(world, monkeypatch, lines, argv=(), env=None, stdout=None, stderr=None,
             stdin_tty=True):
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    stdout, stderr = stdout or TtyOut(), stderr or TtyOut()
    code = main(["--no-draft", "--index-dir", str(world.tmp / "idx"), *argv],
                stdin=In(*lines, tty=stdin_tty), stdout=stdout, stderr=stderr)
    return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue())


BANNER_LINE = on().paint(formatter.BANNER, "danger")


def test_rose_pine_overrides_the_no_color_flag(world, monkeypatch):
    r = run_main(world, monkeypatch, ["/theme rose-pine\n", QUESTION], ["--no-color"], DARK_TRUE)
    assert r.code == 0, r.err
    assert on().paint("Theme: rose-pine (dark).", "muted") in r.err
    assert BANNER_LINE in r.out.split("\n")


def test_rose_pine_overrides_the_no_color_variable(world, monkeypatch):
    r = run_main(world, monkeypatch, ["/theme rose-pine\n", QUESTION],
                 env={**DARK_TRUE, "NO_COLOR": "1"})
    assert BANNER_LINE in r.out.split("\n")


def test_none_turns_a_coloured_session_plain(world, monkeypatch):
    r = run_main(world, monkeypatch, [QUESTION, "/theme none\n", QUESTION], env=DARK_TRUE)
    assert r.code == 0, r.err
    lines = r.out.split("\n")
    assert lines.count(BANNER_LINE) == 1  # the first answer
    assert lines.count(formatter.BANNER) == 1  # the second one, plain
    assert "Theme: none.\n" in r.err


def test_the_variant_follows_the_theme_option(world, monkeypatch):
    dark = run_main(world, monkeypatch, ["/theme\n"], env=DARK_TRUE)
    assert "Theme: rose-pine (dark). Choices: none, rose-pine.\n" in view.strip_escapes(dark.err)
    light = run_main(world, monkeypatch, ["/theme\n"], ["--theme", "light"],
                     {"COLORTERM": "truecolor"})
    assert "Theme: rose-pine (light). Choices: none, rose-pine.\n" in view.strip_escapes(light.err)


def test_a_stream_that_cannot_show_colour_stays_plain(world, monkeypatch):
    r = run_main(world, monkeypatch, ["/theme rose-pine\n", QUESTION], ["--no-color"],
                 DARK_TRUE, stdout=Out())
    assert not SGR.search(r.out)  # stdout is a pipe
    assert on().paint("Theme: rose-pine (dark).", "muted") in r.err  # stderr can show colour


def test_with_nothing_that_can_show_colour_it_says_so(world, monkeypatch):
    r = run_main(world, monkeypatch, ["/theme rose-pine\n", QUESTION], env=DARK_TRUE,
                 stdout=Out(), stderr=Out(), stdin_tty=False)
    assert UNAVAILABLE + "\n" in r.err
    assert not SGR.search(r.out) and not SGR.search(r.err)


def test_a_dumb_terminal_cannot_be_given_colour(world, monkeypatch):
    r = run_main(world, monkeypatch, ["/theme rose-pine\n", QUESTION],
                 env={"TERM": "dumb", "COLORTERM": "truecolor"})
    assert UNAVAILABLE + "\n" in r.err
    assert not SGR.search(r.out)


def test_the_choice_is_not_saved_anywhere(world, monkeypatch):
    run_main(world, monkeypatch, ["/theme none\n", "/theme rose-pine\n"], env=DARK_TRUE)
    assert not (world.tmp / "xdg").exists()
    assert not (world.tmp / "home").exists()
