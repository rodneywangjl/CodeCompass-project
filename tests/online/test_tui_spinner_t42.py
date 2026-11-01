"""T4.2 spinner tests (tests-first).

Contract under test (Spec 004 AC-6.3, 6.6; Plan 004 section 9):
  - the status line reads "✻ Thinking… (12s · ctrl-c to cancel)" and keeps tui.STATUS's text
  - Spinner redraws it in place with the elapsed seconds; paused or stopped it writes nothing
  - one daemon thread does the redrawing and stops cleanly
  - it stops before the draft header, an error, an interruption and the end of a question,
    and a tool block is never interrupted by it
  - not live: the old "Thinking…" status line
"""

import io
import threading
import time
from types import SimpleNamespace

import pytest

from codecompass.online import tui
from codecompass.online import tui_live as live
from codecompass.online import tui_view as view
from codecompass.online.tui import main, run_session
from tests.online.test_tui_live_tools_t41 import (  # the same stand-ins and fixture
    GIT_LOG, OPEN, In, Out, TtyOut, run_main, tty_is_fd_7, world)

S = view.Style("truecolor", "dark")
P = S.paint
SPIN = "✻"


# --- status_text ------------------------------------------------------------------------


def test_the_status_text():
    assert live.status_text(0) == "✻ Thinking… (0s · ctrl-c to cancel)"
    assert live.status_text(12) == "✻ Thinking… (12s · ctrl-c to cancel)"
    assert tui.STATUS in live.status_text(5)


def test_the_status_text_is_painted_by_role():
    assert live.status_text(12, S) == (P("✻", "accent") + " " + P(tui.STATUS, "info") + " "
                                       + P("(12s · ctrl-c to cancel)", "muted"))
    assert view.strip_escapes(live.status_text(12, S)) == live.status_text(12)


# --- Spinner, driven by hand ------------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def spinner():
    writes, clock = [], Clock()
    return live.Spinner(writes.append, clock=clock, threaded=False), writes, clock


def test_start_draws_the_first_frame_and_tick_redraws_it_in_place():
    spin, writes, clock = spinner()
    spin.start()
    assert writes == [live.CLEAR_LINE + live.status_text(0)]
    clock.now += 3.7
    spin.tick()
    assert writes[-1] == live.CLEAR_LINE + live.status_text(3)


def test_paused_it_writes_nothing_and_resume_redraws():
    spin, writes, clock = spinner()
    spin.start()
    spin.pause()
    clock.now += 2
    spin.tick()
    assert len(writes) == 1
    spin.resume()
    assert writes[-1] == live.CLEAR_LINE + live.status_text(2)


def test_stopped_it_never_writes_again():
    spin, writes, clock = spinner()
    spin.start()
    spin.stop()
    count = len(writes)
    clock.now += 5
    spin.tick()
    spin.resume()
    spin.stop()  # stopping twice is fine
    assert len(writes) == count


def test_the_real_thread_redraws_and_stops_cleanly():
    writes = []
    spin = live.Spinner(writes.append, interval=0.005)
    spin.start()
    deadline = time.monotonic() + 2
    while len(writes) < 3 and time.monotonic() < deadline:
        time.sleep(0.005)
    spin.stop()
    assert len(writes) >= 3
    assert not spin.thread.is_alive() and spin.thread.daemon
    count = len(writes)
    time.sleep(0.03)
    assert len(writes) == count


# --- run_session with a spinner (AC-6.3) -------------------------------------------------


def spun(answer, *, tty=True, interval=1.0, draft=False):
    stdout, stderr = Out(), Out(tty=tty)
    run_session(answer, stdin=In("q\n", tty=tty), stdout=stdout, stderr=stderr, draft=draft,
                live_tools=True, spinner=True, spinner_interval=interval)
    return stdout.getvalue(), stderr.getvalue()


def test_a_question_shows_the_spinner_and_clears_it_at_the_end():
    out, err = spun(lambda q, on_draft=None, on_tool=None: "the answer")
    assert live.CLEAR_LINE + live.status_text(0) in err
    assert err.endswith(live.CLEAR_LINE) or SPIN not in err.rsplit(live.CLEAR_LINE, 1)[1]
    assert out == "the answer\n"


def test_tool_blocks_are_never_interrupted_by_the_spinner():
    def answer(question, on_draft=None, on_tool=None):
        for _ in range(20):
            on_tool(GIT_LOG)
            time.sleep(0.002)
            on_tool(OPEN)
        return "done"

    _, err = spun(answer, interval=0.0005)
    for entry in (GIT_LOG, OPEN):
        block = "\n".join(live.tool_lines(entry)) + "\n"
        assert err.count(block) == 20  # every block arrived whole


def test_the_spinner_stops_before_the_draft_header():
    def answer(question, on_draft=None, on_tool=None):
        on_draft("hello\n")
        time.sleep(0.02)
        return "hello"

    _, err = spun(answer, interval=0.002, draft=True)
    after = err.split(tui.DRAFT_HEADER, 1)[1]
    assert SPIN not in after


def test_the_spinner_stops_before_an_error():
    def answer(question, on_draft=None, on_tool=None):
        time.sleep(0.01)
        raise RuntimeError("boom")

    _, err = spun(answer, interval=0.002)
    assert "error: boom" in err
    assert SPIN not in err.split("error: boom", 1)[1]


def test_the_spinner_stops_when_a_question_is_interrupted():
    def answer(question, on_draft=None, on_tool=None):
        time.sleep(0.01)
        raise KeyboardInterrupt

    _, err = spun(answer, interval=0.002)
    assert "Interrupted." in err
    assert SPIN not in err.split("Interrupted.", 1)[1]


def test_no_spinner_thread_is_left_running():
    before = threading.active_count()
    spun(lambda q, on_draft=None, on_tool=None: "x", interval=0.002)
    time.sleep(0.02)
    assert threading.active_count() <= before


def test_without_a_terminal_there_is_no_spinner():
    out, err = spun(lambda q, on_draft=None, on_tool=None: "x", tty=False)
    assert SPIN not in err


def test_without_the_spinner_option_the_old_status_line_is_used():
    out, err = Out(), Out(tty=True)
    run_session(lambda q, on_draft=None: "x", stdin=In("q\n"), stdout=out, stderr=err)
    assert tui.STATUS in err.getvalue() and SPIN not in err.getvalue()


# --- main --------------------------------------------------------------------------------


def test_main_shows_the_spinner_on_a_live_terminal(world):
    r = run_main(world)
    assert r.code == 0, r.err
    assert live.status_text(0) in r.err


def test_main_with_plain_uses_the_old_status_line(world):
    r = run_main(world, ["--plain"])
    assert tui.STATUS in r.err and SPIN not in r.err
