"""T2.4 (Spec 004) the draft in the terminal: tests first.

Contract under test (Spec 004 AC-2.1, AC-2.2, AC-2.4):
  run_session(answer, *, stdin, stdout, stderr, draft=False) -> int
  - with draft=True and a terminal on stderr, answer(question, on_draft=callback) is
    used: the model's text goes to stderr under a "DRAFT - NOT CHECKED" header, every
    line prefixed "draft │ " and dimmed, control characters removed; then
    "Draft finished after N s." and "── Checked answer (replaces the draft above) ──";
    stdout gets only the checked answer
  - otherwise answer(question) is called with no callback and nothing is streamed
  - a failure or Ctrl-C after some draft prints "(draft discarded)"; a question
    that produced no draft text shows none of this
  main passes draft=not --no-draft.
No model, no network: `answer` is a fake that "writes" the pieces it is given.
"""

import re

import pytest

from codecompass.online.tui import main, run_session
from tests.online.test_tui_main_t12 import world  # noqa: F401 (fixture)
from tests.online.test_tui_session_t11 import CLEAR, In, Out

HEADER = "⚠ DRAFT — NOT CHECKED. The model is still writing. Do not rely on this text."
DIM, RESET = "\x1b[2m", "\x1b[0m"
MARK = "draft │ "
CHECKED = "── Checked answer (replaces the draft above) ──"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class Drafting:
    """An answer function that streams `pieces` to on_draft, then returns `reply`."""

    def __init__(self, pieces=(), reply="checked answer", then=None):
        self.pieces, self.reply, self.then = list(pieces), reply, then
        self.callbacks = []  # per call: was on_draft given?

    def __call__(self, question, on_draft=None):
        self.callbacks.append(on_draft is not None)
        for piece in self.pieces if on_draft else ():
            on_draft(piece)
        if self.then:
            raise self.then
        return self.reply


def run(answer, *lines, draft=True, tty=True, stderr_tty=None):
    stdout, stderr = Out(), Out(tty=tty if stderr_tty is None else stderr_tty)
    code = run_session(answer, stdin=In(*lines, tty=tty), stdout=stdout, stderr=stderr,
                       draft=draft)
    return code, stdout.getvalue(), stderr.getvalue()


def plain(text):
    return ANSI.sub("", text)


def test_the_draft_goes_to_stderr_under_a_header_with_every_line_marked():
    code, out, err = run(Drafting(["Hel", "lo\nwor", "ld"]), "q?\n")
    assert code == 0
    assert out == "checked answer\n"  # stdout: the checked answer, nothing of the draft
    assert plain(err).count(HEADER) == 1
    assert f"{MARK}Hello\n" in plain(err) and f"{MARK}world\n" in plain(err)
    assert "Hello" not in out and "world" not in out


def test_every_marked_line_is_dimmed():
    _, _, err = run(Drafting(["one\ntwo\nthree"]), "q?\n")
    lines = [line for line in err.split("\n") if MARK in line]
    assert len(lines) == 3 and all(line.startswith(DIM) for line in lines)
    assert err.count(RESET) >= 3


def test_a_line_split_across_pieces_is_marked_once():
    _, _, err = run(Drafting(["abc", "def\nghi"]), "q?\n")
    assert plain(err).count(MARK) == 2
    assert f"{MARK}abcdef\n" in plain(err) and f"{MARK}ghi\n" in plain(err)


def test_blank_lines_in_the_draft_are_kept_and_still_marked():
    _, _, err = run(Drafting(["a\n\nb"]), "q?\n")
    assert f"{MARK}a\n{MARK}\n{MARK}b\n" in plain(err)


def test_the_header_replaces_the_status_line_and_comes_before_any_text():
    _, _, err = run(Drafting(["text"]), "q?\n")
    assert err.index("Thinking") < err.index(CLEAR) < err.index("DRAFT") < err.index(MARK)


def test_the_checked_answer_follows_the_draft_after_two_closing_lines():
    _, out, err = run(Drafting(["draft text"], reply="final [1]\n\nSources\n[1] x"), "q?\n")
    shown = plain(err)
    assert re.search(r"Draft finished after \d+ s\.\n", shown)
    assert shown.index("draft text") < shown.index("Draft finished") < shown.index(CHECKED)
    assert shown.split(CHECKED)[1].strip() in ("", ">")  # only the next prompt follows
    assert out == "final [1]\n\nSources\n[1] x\n"


def test_the_draft_is_never_written_to_stdout():
    _, out, _ = run(Drafting(["secret draft"]), "q?\n")
    assert "secret draft" not in out and "DRAFT" not in out and MARK not in out


def test_each_question_gets_its_own_header_and_closing_lines():
    _, _, err = run(Drafting(["x"]), "one?\n", "two?\n")
    assert plain(err).count(HEADER) == 2 and plain(err).count(CHECKED) == 2


def test_a_question_that_produced_no_draft_text_shows_no_draft_chrome():
    _, out, err = run(Drafting([]), "q?\n")  # e.g. only tool rounds
    assert out == "checked answer\n"
    assert "DRAFT" not in err and "Draft finished" not in err and CHECKED not in err
    assert err.index("Thinking") < err.index(CLEAR)  # the status line is still cleared


def test_control_characters_from_the_model_never_reach_the_terminal():
    _, _, err = run(Drafting(["\x1b[31mred\x1b[0m and \x1b]0;title\x07 beep\x07\r over"]),
                    "q?\n")
    assert "red" in err and "over" in err
    assert "\x1b[31m" not in err and "\x1b]0;" not in err
    assert "\r" not in err.replace(CLEAR, "") and "\x07" not in err
    assert set(ANSI.findall(err)) <= {DIM, RESET, "\x1b[K"}  # only escapes we write ourselves


@pytest.mark.parametrize("kind", [RuntimeError("boom"), KeyboardInterrupt()])
def test_a_failure_after_some_draft_discards_it_cleanly(kind):
    answer = Drafting(["partial"], then=kind)
    code, out, err = run(answer, "q?\n", "next?\n")
    shown = plain(err)
    assert code == 0 and "partial" in shown
    assert re.search(r"partial\n\(draft discarded\)\n", shown)
    assert ("error: boom" if isinstance(kind, RuntimeError) else "Interrupted.") in shown
    assert shown.index("(draft discarded)") < shown.index(
        "error: boom" if isinstance(kind, RuntimeError) else "Interrupted.")
    assert out == ""  # and the session carried on to the next question
    assert len(answer.callbacks) == 2


def test_a_failure_with_no_draft_text_has_no_discard_line():
    _, _, err = run(Drafting([], then=RuntimeError("boom")), "q?\n")
    assert "error: boom" in err and "discarded" not in err


@pytest.mark.parametrize("draft, tty, stderr_tty", [
    (False, True, None),     # --no-draft
    (True, False, False),    # piped
    (True, True, False),     # stderr redirected, though stdin is a terminal
])
def test_nothing_is_streamed_when_drafting_is_off_or_stderr_is_not_a_terminal(
        draft, tty, stderr_tty):
    answer = Drafting(["should not be shown"])
    _, out, err = run(answer, "q?\n", draft=draft, tty=tty, stderr_tty=stderr_tty)
    assert answer.callbacks == [False]  # answer(question) was called with no callback
    assert out == "checked answer\n"
    assert "DRAFT" not in err and MARK not in err and CHECKED not in err


def test_an_answer_function_that_takes_only_a_question_still_works_without_draft():
    stdout, stderr = Out(), Out(tty=True)
    code = run_session(lambda q: f"re: {q}", stdin=In("hi?\n", tty=True), stdout=stdout,
                       stderr=stderr, draft=False)
    assert code == 0 and stdout.getvalue() == "re: hi?\n"


# --- main passes the flag ----------------------------------------------------------------


def test_main_streams_a_draft_by_default_on_a_terminal(world, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    world.run([], "q?\n", tty=True)
    assert callable(world.asks[0].on_draft)


def test_no_draft_option_turns_it_off(world, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    world.run(["--no-draft"], "q?\n", tty=True)
    assert world.asks[0].on_draft is None


def test_piped_input_passes_no_callback(world, monkeypatch):  # noqa: F811
    monkeypatch.chdir(world.repo.path)
    world.run([], "q?\n", tty=False)
    assert world.asks[0].on_draft is None


def test_help_lists_no_draft(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "--no-draft" in capsys.readouterr().out
