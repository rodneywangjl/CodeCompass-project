"""T3.3 coloured answer tests (tests-first).

Contract under test (Spec 004 AC-5.4, AC-5.6; Plan 004 section 8; Articles VI.3, VI.5):
  - colour is added around the flagged banner and notes, the UNVERIFIED mark, the (not cited)
    tags, [N] markers, the last Sources heading and the stale warning, and nowhere else
  - with every escape sequence removed the output is exactly the answer
  - lookalikes (mid-line marks, arr[0], text in a code fence) are left alone
  - no colour is ever used for "ok": nothing is styled as verified
  - colour off is byte-identical; colour on stdout is decided by stdout alone
  - an unknown CODECOMPASS_THEME is a startup error
"""

import io
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.offline.models import EmbedderIdentity
from codecompass.online import tui_view as view
from codecompass.online.citation import checker, formatter
from codecompass.online.context import RetrievedChunk
from codecompass.online.tui import main, run_session
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

TTY_FD = 7
SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
GOOD = "src/auth.py, lines 42-58 (indexed at a1b2c3d)"
BAD = "src/other.py, lines 1-2 (indexed at a1b2c3d)"


@pytest.fixture(autouse=True)
def tty_is_fd_7(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: fd == TTY_FD)


def render(text):
    return formatter.render(checker.check(text, CHUNKS, []))


CASES = {
    "cited": f"Retries three times [1].\n\nSources\n[1] {GOOD}",
    "failed": f"It retries [1] and [2].\n\nSources\n[1] {GOOD}\n[2] {BAD}",
    "missing_entry": f"It retries [1] and [3].\n\nSources\n[1] {GOOD}",
    "partly_uncited": f"First [1].\n\nSecond has no marker.\n\nSources\n[1] {GOOD}",
    "uncited": "I think it retries.",
    "no_evidence": online.NO_EVIDENCE,
}
ANSWERS = {name: render(text) for name, text in CASES.items()}
ANSWERS["stale"] = f"{online.STALE_WARNING}\nReason: index failed\n\n{ANSWERS['failed']}"

DARK = view.Style("truecolor", "dark")
P = DARK.paint


def lines_of(text, style=DARK):
    return style.answer(text).split("\n")


# --- the text never changes (AC-5.4) -------------------------------------------------


@pytest.mark.parametrize("level", ["truecolor", "256"])
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("case", sorted(ANSWERS))
def test_with_the_escapes_removed_the_answer_is_exact(level, theme, case):
    text = ANSWERS[case]
    assert view.strip_escapes(view.Style(level, theme).answer(text)) == text


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("case", sorted(ANSWERS))
def test_colour_off_is_byte_identical(theme, case):
    assert view.Style("none", theme).answer(ANSWERS[case]) == ANSWERS[case]


def test_the_final_newline_and_blank_lines_are_kept():
    text = "A [1].\n\n\nB\n"
    assert view.strip_escapes(DARK.answer(text)) == text


# --- what is painted, and in which role (AC-5.4) -------------------------------------


def test_the_flagged_banner_is_painted_as_danger_on_its_whole_line():
    assert P(formatter.BANNER, "danger") in lines_of(ANSWERS["failed"])


def test_the_notes_and_the_stale_warning_are_painted_as_warn():
    assert P(formatter.PARTIAL_NOTE, "warn") in lines_of(ANSWERS["partly_uncited"])
    assert P(formatter.UNCITED_NOTE, "warn") in lines_of(ANSWERS["uncited"])
    stale = lines_of(ANSWERS["stale"])
    assert P(online.STALE_WARNING, "warn") in stale
    assert "Reason: index failed" in stale  # the reason line itself stays plain


def test_unverified_marks_and_markers_in_a_failed_answer():
    lines = lines_of(ANSWERS["failed"])
    assert ("It retries " + P("[1]", "accent") + " and " + P("[2]", "accent") + ".") in lines
    assert (P("[1]", "accent") + " " + GOOD) in lines  # the verified entry has no mark
    assert (P("[UNVERIFIED]", "danger") + " " + P("[2]", "accent") + " " + BAD) in lines


def test_a_marker_with_no_entry_line():
    lines = lines_of(ANSWERS["missing_entry"])
    assert (P("[UNVERIFIED]", "danger") + " " + P("[3]", "accent")
            + " (no matching Sources entry)") in lines


def test_the_not_cited_tag_is_painted_and_its_space_is_not():
    lines = lines_of(ANSWERS["partly_uncited"])
    assert ("Second has no marker. " + P("(not cited)", "tag")) in lines


def test_the_sources_heading_is_painted_as_info():
    assert P("Sources", "info") in lines_of(ANSWERS["cited"])


def test_only_the_last_sources_heading_is_painted():
    lines = lines_of("Sources\nabc\nSources\n[1] x")
    assert lines[0] == "Sources"
    assert lines[2] == P("Sources", "info")


def test_multi_digit_markers_are_painted():
    assert lines_of("see [12] and [3]")[0] == (
        "see " + P("[12]", "accent") + " and " + P("[3]", "accent"))


# --- lookalikes are left alone (AC-5.4) ----------------------------------------------


@pytest.mark.parametrize("line", [
    "arr[0] and x[1] and [a] and [1x] and a[2]",
    "the text [UNVERIFIED] in the middle of a line",
    "a [NOT REFERENCED IN ANSWER] lookalike mid-line",
    "close (not cited) in the middle of a line",
    formatter.BANNER + " and more text on the same line",
    "WARNING: Some citations could not be verified",
])
def test_lookalikes_are_not_painted(line):
    assert lines_of(line) == [line]


def test_nothing_inside_a_code_fence_is_painted():
    text = "```\nx = [1]\n[UNVERIFIED] y\nz (not cited)\n```\nafter [1]"
    out = lines_of(text)
    assert out[:5] == ["```", "x = [1]", "[UNVERIFIED] y", "z (not cited)", "```"]
    assert out[5] == "after " + P("[1]", "accent")  # outside the fence again


# --- nothing is styled as verified (AC-5.4, Article VI.5) ----------------------------


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_ok_colour_never_appears_in_an_answer(theme, monkeypatch):
    monkeypatch.setitem(view.PALETTES[theme], "ok", ("#010203", False))  # a sentinel
    style = view.Style("truecolor", theme)
    everything = "\n".join(style.answer(text) for text in ANSWERS.values())
    assert "\x1b[" in everything  # colour was used...
    assert "38;2;1;2;3" not in everything  # ...but never the sentinel


# --- run_session (AC-5.4) -------------------------------------------------------------


class In:
    def __init__(self, *lines):
        self._lines = list(lines)

    def isatty(self):
        return False

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class Out(io.StringIO):
    def isatty(self):
        return False


def test_run_session_writes_the_styled_answer():
    text = ANSWERS["failed"]
    out, err = Out(), Out()
    run_session(lambda q, on_draft=None: text, stdin=In("q\n"), stdout=out, stderr=err,
                style=DARK)
    assert out.getvalue() == DARK.answer(text) + "\n"
    assert view.strip_escapes(out.getvalue()) == text + "\n"


def test_run_session_without_a_style_is_unchanged():
    text = ANSWERS["failed"]
    out = Out()
    run_session(lambda q, on_draft=None: text, stdin=In("q\n"), stdout=out, stderr=Out())
    assert out.getvalue() == text + "\n"


# --- main: the choice is made from stdout and the environment (AC-5.2, 5.6) ----------


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
    (repo.path / "codecompass.toml").write_text(
        f'[embedder]\nmodel = "stub"\nrevision = "stub-{tmp.name}"\ndimension = 8\n'
        f'[reranker]\nrevision = "rerank-{tmp.name}"\n')
    monkeypatch.chdir(repo.path)
    return SimpleNamespace(tmp=tmp)


def run_main(world, monkeypatch, env=None, stdout=None):
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    stdout, stderr = stdout or TtyOut(), Out()
    code = main(["--index-dir", str(world.tmp / "idx")],
                stdin=In("Why does authenticate retry?\n"), stdout=stdout, stderr=stderr)
    return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue())


def dark_truecolor(world, monkeypatch):
    return run_main(world, monkeypatch, {"COLORTERM": "truecolor",
                                         "CODECOMPASS_THEME": "dark"})


def test_main_colours_the_flagged_banner_and_the_text_is_unchanged(world, monkeypatch):
    plain = run_main(world, monkeypatch, {"NO_COLOR": "1", "COLORTERM": "truecolor"})
    monkeypatch.delenv("NO_COLOR")
    coloured = dark_truecolor(world, monkeypatch)
    assert plain.code == coloured.code == 0, coloured.err
    assert "\x1b[" not in plain.out
    assert P(formatter.BANNER, "danger") in coloured.out.split("\n")
    assert view.strip_escapes(coloured.out) == plain.out  # not a word changed
    assert formatter.BANNER in plain.out  # and the banner is there without colour too


def test_main_uses_the_theme_from_the_environment(world, monkeypatch):
    light = view.Style("truecolor", "light")
    out = run_main(world, monkeypatch, {"COLORTERM": "truecolor",
                                        "CODECOMPASS_THEME": "light"})
    assert light.paint(formatter.BANNER, "danger") in out.out.split("\n")


def test_main_picks_the_light_theme_from_a_light_terminal(world, monkeypatch):
    light = view.Style("truecolor", "light")
    out = run_main(world, monkeypatch, {"COLORTERM": "truecolor", "COLORFGBG": "0;15"})
    assert light.paint(formatter.BANNER, "danger") in out.out.split("\n")


def test_main_falls_back_to_256_colours(world, monkeypatch):
    out = run_main(world, monkeypatch, {"TERM": "xterm-256color",
                                        "CODECOMPASS_THEME": "dark"})
    assert "38;5;" in out.out and "38;2;" not in out.out
    assert formatter.BANNER in view.strip_escapes(out.out)


def test_main_gives_no_colour_with_no_color_set(world, monkeypatch):
    out = run_main(world, monkeypatch, {"COLORTERM": "truecolor", "NO_COLOR": "1"})
    assert "\x1b" not in out.out


def test_main_gives_no_colour_when_stdout_is_not_a_terminal(world, monkeypatch):
    out = run_main(world, monkeypatch, {"COLORTERM": "truecolor"}, stdout=Out())
    assert "\x1b" not in out.out


def test_an_unknown_theme_in_the_environment_is_a_startup_error(world, monkeypatch):
    out = run_main(world, monkeypatch, {"COLORTERM": "truecolor",
                                        "CODECOMPASS_THEME": "neon"})
    assert out.code == 1
    assert "auto, dark, light" in out.err
    assert out.out == ""
