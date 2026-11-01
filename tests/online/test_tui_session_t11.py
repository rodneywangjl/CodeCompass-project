"""T1.1 (Spec 004) the session loop: tests first.

Contract under test (Spec 004 AC-1.2, AC-1.5, AC-1.6, AC-1.7, AC-1.8, AC-1.11):
  run_session(answer, *, stdin, stdout, stderr) -> int
  - answer(question) -> str is called once per non-blank line, with the line
    stripped; its text is the only thing written to stdout
  - /exit, /quit and end of input return 0
  - prompt, status line and hints go to stderr, and only when the stream is
    a terminal; a failed question prints "error: ..." to stderr and the
    session carries on; Ctrl-C never ends the session
No model, no network: `answer` is a fake.
"""

import io

import pytest

from codecompass.online.tui import run_session

CLEAR = "\r\x1b[K"


class In:
    """Scripted stdin: each item is a line, or an exception to raise at that read."""

    def __init__(self, *items, tty=False):
        self._items = list(items)
        self._tty = tty

    def isatty(self):
        return self._tty

    def readline(self):
        if not self._items:
            return ""  # end of input
        item = self._items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class Out(io.StringIO):
    def __init__(self, tty=False):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


class FakeAnswer:
    def __init__(self, replies=None, raises=None):
        self.questions = []
        self._replies = replies or {}
        self._raises = raises or {}

    def __call__(self, question):
        self.questions.append(question)
        if question in self._raises:
            raise self._raises[question]
        return self._replies.get(question, f"answer to {question}")


def run(answer, *lines, stdin_tty=False, stderr_tty=False):
    stdout, stderr = Out(), Out(tty=stderr_tty)
    code = run_session(answer, stdin=In(*lines, tty=stdin_tty), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_each_question_is_answered_and_only_the_answers_reach_stdout():
    answer = FakeAnswer()
    code, out, err = run(answer, "first?\n", "second?\n")
    assert code == 0
    assert answer.questions == ["first?", "second?"]
    assert out == "answer to first?\nanswer to second?\n"
    assert err == ""


def test_the_answer_text_is_printed_exactly_with_one_trailing_newline():
    answer = FakeAnswer(replies={"a": "⚠ WARNING: flagged\n\n[UNVERIFIED] [1] x.py\n",
                                 "b": "no newline"})
    _, out, _ = run(answer, "a\n", "b\n")
    assert out == "⚠ WARNING: flagged\n\n[UNVERIFIED] [1] x.py\nno newline\n"


def test_the_question_is_stripped_and_blank_lines_are_ignored():
    answer = FakeAnswer()
    _, out, _ = run(answer, "\n", "   \n", "  why retry?  \n", "\t\n")
    assert answer.questions == ["why retry?"]
    assert out == "answer to why retry?\n"


def test_a_last_line_without_a_newline_is_still_a_question():
    answer = FakeAnswer()
    run(answer, "no newline at end")
    assert answer.questions == ["no newline at end"]


@pytest.mark.parametrize("command", ["/exit", "/quit", "  /exit  "])
def test_exit_commands_end_the_session_with_zero(command):
    answer = FakeAnswer()
    code, out, _ = run(answer, f"{command}\n", "never asked?\n")
    assert code == 0
    assert answer.questions == []
    assert out == ""


def test_end_of_input_ends_the_session_with_zero():
    code, out, _ = run(FakeAnswer())
    assert (code, out) == (0, "")


def test_ctrl_c_at_the_prompt_prints_a_hint_and_keeps_going():
    answer = FakeAnswer()
    code, out, err = run(answer, KeyboardInterrupt(), "still here?\n")
    assert code == 0
    assert answer.questions == ["still here?"]
    assert out == "answer to still here?\n"
    assert "/exit" in err and "Ctrl-D" in err


def test_ctrl_c_during_a_question_abandons_it_and_returns_to_the_prompt():
    answer = FakeAnswer(raises={"slow?": KeyboardInterrupt()})
    code, out, err = run(answer, "slow?\n", "next?\n")
    assert code == 0
    assert answer.questions == ["slow?", "next?"]
    assert out == "answer to next?\n"  # nothing printed for the abandoned question
    assert "interrupted" in err.lower()


def test_an_error_is_reported_to_stderr_and_the_session_continues():
    answer = FakeAnswer(raises={"boom?": RuntimeError("generator unreachable at :8080")})
    code, out, err = run(answer, "boom?\n", "ok?\n")
    assert code == 0
    assert out == "answer to ok?\n"
    assert "error: generator unreachable at :8080" in err
    assert "Traceback" not in err


def test_an_error_with_no_message_still_says_what_happened():
    answer = FakeAnswer(raises={"boom?": TimeoutError()})
    _, _, err = run(answer, "boom?\n")
    assert "error:" in err and "TimeoutError" in err


def test_piped_input_prints_no_prompt_and_no_status_line():
    _, out, err = run(FakeAnswer(), "q?\n", stdin_tty=False, stderr_tty=False)
    assert err == ""
    assert "\x1b" not in out and ">" not in out


def test_a_terminal_gets_a_prompt_before_each_question_on_stderr():
    _, out, err = run(FakeAnswer(), "one?\n", "two?\n", stdin_tty=True, stderr_tty=True)
    assert err.count("> ") >= 3  # before each question and before end of input
    assert "> " not in out


def test_a_terminal_shows_one_status_line_that_is_cleared_after_the_answer():
    _, out, err = run(FakeAnswer(), "one?\n", stdin_tty=True, stderr_tty=True)
    assert err.count("Thinking") == 1
    assert err.index("Thinking") < err.index(CLEAR)
    assert out == "answer to one?\n"


def test_the_status_line_is_cleared_even_when_the_question_fails():
    answer = FakeAnswer(raises={"boom?": RuntimeError("down")})
    _, _, err = run(answer, "boom?\n", stdin_tty=True, stderr_tty=True)
    assert err.index("Thinking") < err.index(CLEAR) < err.index("error: down")


def test_no_status_line_when_stderr_is_not_a_terminal_even_if_stdin_is():
    _, _, err = run(FakeAnswer(), "one?\n", stdin_tty=True, stderr_tty=False)
    assert "Thinking" not in err and "\x1b" not in err
