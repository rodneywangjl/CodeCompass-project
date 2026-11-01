"""The live terminal interface (Spec 004 US6): standard library only.

Pure helpers where possible; the few that touch a stream take it as an argument.
"""

from __future__ import annotations

import os

from codecompass.online.tui_view import _clean


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
