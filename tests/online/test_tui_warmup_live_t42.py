"""T4.2 follow-up: the spinner and the warm-up message (tests-first).

Contract (Spec 004 AC-6.3, AC-3.2): on a live terminal, while the first question waits for the
warm-up, the spinner is paused so that "Preparing index and models…" stays readable; once the
warm-up is done the spinner is drawn again at once, so the old plain status line never lingers.
"""

import time
from types import SimpleNamespace

from codecompass.online import tui
from codecompass.online import tui_live as live
from tests.online.test_tui_live_tools_t41 import run_main, tty_is_fd_7, world  # noqa: F401

PREPARING = "Preparing index and models…"


def test_the_warm_up_message_is_not_drawn_over_and_the_spinner_returns_at_once(world, monkeypatch):
    def slow_join():
        time.sleep(1.3)  # longer than one spinner interval

    monkeypatch.setattr(tui, "_start_warm_up", lambda *a, **k: SimpleNamespace(
        is_alive=lambda: True, join=slow_join))
    r = run_main(world)
    assert r.code == 0, r.err
    waiting = r.err.split(PREPARING, 1)[1].split(live.CLEAR_LINE + tui.STATUS, 1)[0]
    assert "✻" not in waiting  # paused while the message is up
    assert live.CLEAR_LINE + tui.STATUS + live.CLEAR_LINE + "✻ Thinking…" in r.err
