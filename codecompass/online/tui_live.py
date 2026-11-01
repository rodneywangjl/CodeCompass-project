"""The live terminal interface (Spec 004 US6): standard library only.

Pure helpers where possible; the few that touch a stream take it as an argument.
"""

from __future__ import annotations

import os
import threading
import time

from codecompass.online.tui_view import _clean

CLEAR_LINE = "\r\x1b[K"  # back to the start of the line, and erase it
THINKING = "Thinking…"
# one lock for everything written to the terminal while a question runs (AC-6.3)
LOCK = threading.RLock()


def is_terminal(stream, environ) -> bool:
    """True for a real terminal: a tty file descriptor, and TERM is not "dumb" (AC-6.1).

    A stand-in stream without a descriptor is never one, so earlier tests keep the
    old output.
    """
    try:
        real = os.isatty(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return False
    return real and environ.get("TERM") != "dumb"


def _paint(style, text: str, role: str) -> str:
    return style.paint(text, role) if style else text


def tool_lines(entry, style=None) -> list[str]:
    """The two lines shown for one executed tool call (AC-6.2)."""
    args = ", ".join(f"{key}={_clean(value)}" for key, value in entry.get("args", {}).items())
    first = f"{_paint(style, '●', 'accent')} {_clean(entry['tool'])}({args})"
    result = _clean(entry.get("result_summary") or "")
    if entry.get("error"):
        shown = _paint(style, "failed", "danger") + (f" · {result}" if result else "")
    else:
        shown = result or "(no output)"
    return [first, f"  {_paint(style, '⎿', 'muted')} {shown}"]


def status_text(seconds: int, style=None) -> str:
    """The status line while a question runs (AC-6.3)."""
    return (f"{_paint(style, '✻', 'accent')} {_paint(style, THINKING, 'info')} "
            f"{_paint(style, f'({seconds}s · ctrl-c to cancel)', 'muted')}")


class Spinner:
    """Redraw the status line in place with the elapsed seconds (AC-6.3).

    *write* puts text on the terminal. All drawing happens under *lock*, which the
    caller shares with everything else it writes during a question, so writers never
    interleave. With *threaded* a daemon thread calls tick() every *interval* seconds;
    without it the caller ticks (the tests do).
    """

    def __init__(self, write, *, clock=time.monotonic, interval: float = 1.0, style=None,
                 lock=None, threaded: bool = True) -> None:
        self._write, self._clock, self._interval = write, clock, interval
        self._style, self.lock, self._threaded = style, lock or LOCK, threaded
        self._running = self._paused = False
        self._t0 = 0.0
        self._stopping = threading.Event()
        self.thread = None

    def _draw(self) -> None:
        self._write(CLEAR_LINE + status_text(int(self._clock() - self._t0), self._style))

    def start(self) -> None:
        with self.lock:
            self._t0, self._running, self._paused = self._clock(), True, False
            self._draw()
        if self._threaded:
            self.thread = threading.Thread(target=self._loop, name="codecompass-spinner",
                                           daemon=True)
            self.thread.start()

    def _loop(self) -> None:
        while not self._stopping.wait(self._interval):
            self.tick()

    def tick(self) -> None:
        with self.lock:
            if self._running and not self._paused:
                self._draw()

    def pause(self) -> None:
        with self.lock:
            self._paused = True

    def resume(self) -> None:
        with self.lock:
            if self._running:
                self._paused = False
                self._draw()

    def stop(self) -> None:
        """No more drawing, and the thread is gone. Clearing the line is the caller's job."""
        with self.lock:
            self._running = False
        self._stopping.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join()


# --- the boxed prompt (AC-6.4) ---------------------------------------------------------

MIN_WIDTH = 20
CURSOR_INTO_BOX = "\x1b[2A\r\x1b[4C"  # from the status line up to the box's middle row, after "> "
LEAVE_BOX = "\n\n"  # after Enter the cursor is on the bottom border: past it and the status line
LEAVE_BOX_UNREAD = "\n\n\n"  # still on the middle row (end of input, Ctrl-C): past all three


def box_lines(width: int, style=None) -> tuple[str, str, str]:
    """The top, middle and bottom rows of the prompt box, each *width* columns wide."""
    width = max(width, MIN_WIDTH)
    top = _paint(style, "╭" + "─" * (width - 2) + "╮", "muted")
    bar = _paint(style, "│", "muted")
    middle = f"{bar} {_paint(style, '>', 'accent')} " + " " * (width - 5) + bar
    bottom = _paint(style, "╰" + "─" * (width - 2) + "╯", "muted")
    return top, middle, bottom


def status_line(repo: str, profile: str, model: str, width: int, style=None) -> str:
    """"  <repo folder> · <profile> · <model>", cut to *width* (AC-6.4)."""
    text = f"  {repo} · {profile} · {model}"
    if len(text) > width:
        text = text[:max(width - 1, 0)] + "…"
    return _paint(style, text, "muted")


def prompt_box(width: int, info, style=None) -> str:
    """Everything written for one boxed prompt, ending with the cursor inside the box."""
    width = max(width, MIN_WIDTH)
    return "\n".join([*box_lines(width, style), status_line(*info, width=width, style=style)]
                     ) + CURSOR_INTO_BOX

