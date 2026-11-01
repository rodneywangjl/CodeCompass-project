"""T4.4 markdown-styled answers tests (tests-first).

Contract under test (Spec 004 AC-6.5, 6.6; Q16; Plan 004 section 9):
  - in the model-written body: "# h" bold heading, **bold**, *italic*, `code`, fenced blocks
    (fence lines dropped, code styled) and "- "/"* " bullets as "• ", with the punctuation gone
  - underscores are never emphasis; an unclosed or lone delimiter leaves its line alone
  - banners, notes, the stale warning, mark lines, (not cited), [N] markers, the Sources
    heading and everything after it are never touched
  - an answer without markdown is shown exactly as before; colour off shows the answer exactly
  - main: on in live mode with colour; --plain and pipes show the answer as it is
"""

import io
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.online import tui
from codecompass.online import tui_view as view
from codecompass.online.citation import checker, formatter
from codecompass.online.context import RetrievedChunk
from codecompass.online.tui import main
from tests.online.test_tui_answer_color_t33 import ANSWERS
from tests.online.test_tui_live_tools_t41 import In, Out, TtyOut, tty_is_fd_7  # noqa: F401

S = view.Style("truecolor", "dark")
P = S.paint
BOLD, ITALIC = "\x1b[1m", "\x1b[3m"


def md(text, style=S):
    return view.render_markdown(text, style)


def plain(text):
    return view.strip_escapes(md(text))


# --- what is styled, and the punctuation consumed (AC-6.5) -----------------------------


def test_a_heading_loses_its_hashes_and_is_bold():
    out = md("# Retry logic\n\n## Why it exists")
    assert plain("# Retry logic\n\n## Why it exists") == "Retry logic\n\nWhy it exists"
    assert out.count(BOLD) == 2


def test_bold_and_italic_lose_their_asterisks():
    assert plain("It **retries** three *times*.") == "It retries three times."
    out = md("It **retries** three *times*.")
    assert BOLD in out and ITALIC in out


def test_inline_code_loses_its_backticks_and_is_styled():
    assert plain("Set `MAX_RETRIES` to 5.") == "Set MAX_RETRIES to 5."
    assert P("MAX_RETRIES", "info") in md("Set `MAX_RETRIES` to 5.")


def test_markdown_inside_inline_code_is_left_as_code():
    assert plain("Use `**kwargs` here.") == "Use **kwargs here."


def test_a_fenced_block_loses_its_fence_lines_and_its_code_is_styled():
    text = "Here:\n```python\nx = [1]\n```\nafter [1]"
    out = md(text).split("\n")
    assert out[0] == "Here:"
    assert out[1] == P("x = [1]", "info")  # a [1] in code is not a marker
    assert view.strip_escapes(out[2]) == "after [1]" and P("[1]", "accent") in out[2]
    assert len(out) == 3


def test_bullets_become_dots():
    assert plain("- one\n* two\n  - nested") == "• one\n• two\n  • nested"


@pytest.mark.parametrize("line", [
    "my_module.py and snake_case_name and __init__",
    "an unclosed **bold here",
    "a lone ` backtick",
    "a lone * star",
    "2*3*4 is arithmetic",
    "*not italic because of a space *",
])
def test_lines_that_are_not_markdown_are_left_alone(line):
    assert md(line) == S.answer(line)
    assert plain(line) == line


# --- nothing the checker produced is touched (AC-6.5, Article VI.3) ---------------------

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
GOOD = "src/auth.py, lines 42-58 (indexed at a1b2c3d)"


def test_a_real_checked_answer_with_markdown_in_its_body():
    answer = formatter.render(checker.check(
        f"It **retries** [1].\n\n- step `one`\n\nSources\n[1] {GOOD}", CHUNKS, []))
    out = md(answer)
    expected = answer.replace("**", "").replace("`", "").replace("\n- ", "\n• ")
    assert view.strip_escapes(out) == expected  # only the punctuation went
    assert P(formatter.PARTIAL_NOTE, "warn") in out.split("\n")  # the note, as before
    assert (P("[1]", "accent") + " " + GOOD) in out.split("\n")  # the Sources entry, as before
    assert P("(not cited)", "tag") in out


def test_nothing_after_the_sources_heading_is_rewritten():
    out = md("Body.\n\nSources\n[1] **looks** like `markdown`")
    assert view.strip_escapes(out).split("\n")[-1] == "[1] **looks** like `markdown`"


def test_banner_and_mark_lines_are_shown_exactly_as_before():
    text = ANSWERS["failed"]
    assert md(text) == S.answer(text)


@pytest.mark.parametrize("case", sorted(ANSWERS))
def test_an_answer_without_markdown_is_shown_exactly_as_before(case):
    assert md(ANSWERS[case]) == S.answer(ANSWERS[case])


def test_no_word_is_added_removed_or_reordered():
    text = "# Title\n\nIt **really** retries `three` *times*.\n\n- a\n- b"
    assert plain(text).split() == ["Title", "It", "really", "retries", "three", "times.",
                                   "•", "a", "•", "b"]


def test_with_colour_off_the_answer_is_shown_exactly():
    text = "It **retries** `three` times."
    assert view.render_markdown(text, view.Style("none", "dark")) == text
    assert view.render_markdown(text, None) == text


# --- main (AC-6.5, AC-6.6) ---------------------------------------------------------------


@pytest.fixture
def answering(tmp_path, monkeypatch):
    """main on a real fixture repo, with ask() returning a markdown answer."""
    from tests.support.fixture_repo import build_history_repo
    tmp = tmp_path.resolve()
    monkeypatch.setenv("HOME", str(tmp / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "xdg"))
    for name in ("GENERATOR_PROFILE", "NO_COLOR", "TERM", "WT_SESSION", "COLORFGBG",
                 "CODECOMPASS_THEME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COLORTERM", "truecolor")
    repo = build_history_repo(tmp / "repo")

    class Generator:
        def __init__(self, profile, *, server_url, timeout_seconds):
            self.profile = profile

        def health_check(self):
            return True

    monkeypatch.setattr("codecompass.online.generator.llama.LlamaServerGenerator", Generator)
    monkeypatch.setattr(online, "ask", lambda *a, **k: SimpleNamespace(
        answer="It **retries** `three` times.", audit_log={}))
    monkeypatch.setattr(tui, "_start_warm_up", lambda *a, **k: None)
    monkeypatch.chdir(repo.path)

    def run(argv=(), stdout=None, stderr=None, stdin_tty=True):
        stdout, stderr = stdout or TtyOut(), stderr or TtyOut()
        code = main(["--no-draft", *argv], stdin=In("q\n", tty=stdin_tty), stdout=stdout,
                    stderr=stderr)
        return SimpleNamespace(code=code, out=stdout.getvalue(), err=stderr.getvalue())
    return run


def test_main_styles_the_markdown_on_a_live_colour_terminal(answering):
    r = answering()
    assert r.code == 0, r.err
    assert view.strip_escapes(r.out) == "It retries three times.\n"
    assert BOLD in r.out


def test_main_with_plain_shows_the_markdown_as_it_is(answering):
    r = answering(["--plain"])
    assert view.strip_escapes(r.out) == "It **retries** `three` times.\n"


def test_main_with_piped_output_shows_the_answer_exactly(answering):
    r = answering(stdout=Out(), stderr=Out(), stdin_tty=False)
    assert r.out == "It **retries** `three` times.\n"


def test_main_without_colour_shows_the_answer_exactly(answering):
    r = answering(["--no-color"])
    assert r.out == "It **retries** `three` times.\n"
