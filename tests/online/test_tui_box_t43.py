"""T4.3 boxed prompt and status line tests (tests-first).

Contract under test (Spec 004 AC-6.4, 6.6; Plan 004 section 9):
  - a rounded box exactly as wide as the terminal (at least 20 columns) with "│ > " inside
  - a muted status line under it: "<repo folder> · <profile> · <model>", cut to the width
  - the cursor is moved up into the box (ESC[2A, then column 5) and, once a line is read,
    the output continues below the status line; EOF and Ctrl-C leave the box too
  - not live: the old "> " prompt
"""

import io

from codecompass.online import tui
from codecompass.online import tui_live as live
from codecompass.online import tui_view as view
from codecompass.online.tui import run_session
from tests.online.test_tui_live_tools_t41 import In, Out, run_main, tty_is_fd_7, world  # noqa: F401

S = view.Style("truecolor", "dark")
P = S.paint
INFO = ("spm_proj", "dev-7b-gpu", "Qwen2.5-Coder-7B-Instruct")


def test_the_box_rows():
    top, middle, bottom = live.box_lines(30)
    assert top == "╭" + "─" * 28 + "╮"
    assert middle == "│ > " + " " * 25 + "│"
    assert bottom == "╰" + "─" * 28 + "╯"
    assert len(top) == len(middle) == len(bottom) == 30


def test_the_box_is_never_narrower_than_20():
    assert all(len(row) == 20 for row in live.box_lines(5))


def test_the_status_line():
    assert live.status_line(*INFO, width=80) == "  spm_proj · dev-7b-gpu · Qwen2.5-Coder-7B-Instruct"
    narrow = live.status_line(*INFO, width=20)
    assert len(narrow) <= 20 and narrow.endswith("…")


def test_the_box_and_the_status_line_are_painted_and_strip_back():
    top, middle, bottom = live.box_lines(30, S)
    assert top == P("╭" + "─" * 28 + "╮", "muted")
    assert middle == P("│", "muted") + " " + P(">", "accent") + " " + " " * 25 + P("│", "muted")
    assert [view.strip_escapes(row) for row in (top, middle, bottom)] == list(live.box_lines(30))
    assert live.status_line(*INFO, width=80, style=S) == P(live.status_line(*INFO, width=80), "muted")


def test_the_prompt_text_puts_the_cursor_inside_the_box():
    rows = live.box_lines(30)
    expected = "\n".join([*rows, live.status_line(*INFO, width=30)]) + "\x1b[2A\r\x1b[4C"
    assert live.prompt_box(30, INFO) == expected


def boxed(*lines, raise_at_prompt=False):
    """A boxed session; with raise_at_prompt, one Ctrl-C at the prompt and then end of input."""
    stdin = In(*lines)
    if raise_at_prompt:
        calls = []

        def readline():
            calls.append(1)
            if len(calls) == 1:
                raise KeyboardInterrupt
            return ""
        stdin.readline = readline
    stdout, stderr = Out(), Out(tty=True)
    run_session(lambda q, on_draft=None: "the answer", stdin=stdin, stdout=stdout,
                stderr=stderr, boxed=True, box_width=30, status_info=INFO)
    return stdout.getvalue(), stderr.getvalue()


def test_after_a_line_is_read_the_output_continues_below_the_status_line():
    out, err = boxed("q\n")
    box = live.prompt_box(30, INFO)
    assert err.startswith(box + live.LEAVE_BOX)
    assert out == "the answer\n"


def test_end_of_input_leaves_the_box():
    _, err = boxed()
    assert err == live.prompt_box(30, INFO) + live.LEAVE_BOX_UNREAD


def test_ctrl_c_at_the_prompt_leaves_the_box_before_the_hint():
    _, err = boxed(raise_at_prompt=True)
    box = live.prompt_box(30, INFO)
    assert err.startswith(box + live.LEAVE_BOX_UNREAD + "(type /exit or press Ctrl-D to quit)\n")


def test_exit_still_ends_the_session():
    _, err = boxed("/exit\n", "never asked\n")
    assert err == live.prompt_box(30, INFO) + live.LEAVE_BOX


def test_the_box_is_painted_with_a_chrome_style():
    stdout, stderr = Out(), Out(tty=True)
    run_session(lambda q, on_draft=None: "x", stdin=In(), stdout=stdout, stderr=stderr,
                boxed=True, box_width=30, status_info=INFO, chrome=S)
    assert stderr.getvalue().startswith(live.prompt_box(30, INFO, S))


def test_not_boxed_is_the_old_prompt():
    stdout, stderr = Out(), Out(tty=True)
    run_session(lambda q, on_draft=None: "x", stdin=In("q\n"), stdout=stdout, stderr=stderr)
    assert stderr.getvalue().startswith(tui.PROMPT)
    assert "╭" not in stderr.getvalue()


def test_main_shows_the_box_and_the_status_line_on_a_live_terminal(world):  # noqa: F811
    r = run_main(world)
    assert r.code == 0, r.err
    assert "╭" in r.err and "│ > " in r.err
    assert "repo · dev · Qwen2.5-Coder-14B-Instruct" in r.err


def test_main_with_plain_has_no_box(world):  # noqa: F811
    r = run_main(world, ["--plain"])
    assert "╭" not in r.err and tui.PROMPT in r.err
