"""Pure text helpers for the terminal UI (Spec 004 US4, US5): no input or output here.

The tool records are the entries of the audit log's ``tool_calls`` (Article V.4).
Colour (US5) is foreground colour only, on a real terminal only, in one of two
Rosé Pine themes.
"""

from __future__ import annotations

import os
import re

LIMIT = 100  # longest value shown from a tool call; longer ones end with "…"
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _clean(value) -> str:
    """One printable line: control characters removed, long text cut (AC-4.3)."""
    text = _CONTROL.sub("", str(value).replace("\n", " ").replace("\t", " "))
    return text if len(text) <= LIMIT else text[:LIMIT] + "…"


def tool_calls(rounds) -> list[dict]:
    """The calls that ran: entries that name a tool (AC-4.1)."""
    return [entry for entry in rounds if entry.get("tool") is not None]


def summary_line(rounds) -> str:
    n = len(tool_calls(rounds))
    if n == 0:
        return "▸ No tools called"
    return f"▸ {n} tool{'s' if n != 1 else ''} called — type /tools to see them"


def _executed(entry) -> list[str]:
    args = " ".join(f"{key}={_clean(value)}" for key, value in entry.get("args", {}).items())
    head = f"round {entry.get('round', 0)}  {entry['tool']}" + (f"  {args}" if args else "")
    detail = ["cache hit" if entry.get("cache_hit") else "cache miss"]
    if entry.get("error"):
        detail.append("failed")
    if entry.get("result_summary"):
        detail.append(_clean(entry["result_summary"]))
    return [head, " " * 9 + " · ".join(detail)]


def _other(entry) -> list[str]:
    """A round that ran no tool, so that every round is accounted for (AC-4.2)."""
    where = f"round {entry.get('round', 0)}  "
    if entry.get("malformed"):
        return [where + "malformed request, no tool ran"]
    if entry.get("final_call"):
        return [where + "request refused: the round limit was reached"]
    if entry.get("reason") == "tools disabled":
        return [where + "request ignored: tools are off in this mode"]
    return []


def format_tools(rounds) -> str:
    """The text `/tools` prints (AC-4.2, Plan 004 section 8)."""
    lines = []
    for entry in rounds:
        lines += _executed(entry) if entry.get("tool") is not None else _other(entry)
    if not tool_calls(rounds):
        return "\n".join(["No tools were called for the last question."] + lines)
    return "\n".join(["Tools called for the last question:"] + lines)


# --- colour (Spec 004 US5) -----------------------------------------------------------

THEMES = ("auto", "dark", "light")

# role -> (hex colour, bold). dark = Rosé Pine Moon, light = Rosé Pine Dawn; the light
# error colour is a darker shade of Dawn's love because Dawn's own colours are too pale
# for it (AC-5.1, Plan 004 section 8).
PALETTES = {
    "dark": {"accent": ("#c4a7e7", False), "info": ("#9ccfd8", False),
             "warn": ("#f6c177", False), "tag": ("#ea9a97", False),
             "danger": ("#eb6f92", True), "ok": ("#3e8fb0", False),
             "muted": ("#6272a4", False)},
    "light": {"accent": ("#907aa9", True), "info": ("#286983", False),
              "warn": ("#b4637a", False), "tag": ("#797593", False),
              "danger": ("#91344f", True), "ok": ("#286983", False),
              "muted": ("#797593", False)},
}
# the backgrounds the contrast of each theme is measured against
BACKGROUNDS = {"dark": ("#232136", "#000000"), "light": ("#faf4ed", "#ffffff")}

_CUBE = (0, 95, 135, 175, 215, 255)  # the levels of the xterm 6x6x6 colour cube
_SGR = re.compile(r"\x1b\[[0-9;]*m")


def color_level(stream, environ, *, no_color: bool = False) -> str:
    """"truecolor", "256" or "none" for *stream* (AC-5.2).

    Colour needs a real terminal, that is a file descriptor that is a tty; a stand-in
    stream without one never gets it. NO_COLOR (when not empty), --no-color and
    TERM=dumb turn it off.
    """
    if no_color or environ.get("NO_COLOR") or environ.get("TERM") == "dumb":
        return "none"
    try:
        real = os.isatty(stream.fileno())
    except (AttributeError, OSError, ValueError):
        real = False
    if not real:
        return "none"
    if environ.get("COLORTERM") in ("truecolor", "24bit") or environ.get("WT_SESSION"):
        return "truecolor"
    if "256color" in environ.get("TERM", ""):
        return "256"
    return "none"


def theme_name(flag, environ) -> str:
    """"dark" or "light" from --theme, then CODECOMPASS_THEME, then the terminal (AC-5.6)."""
    choice = flag if flag is not None else (environ.get("CODECOMPASS_THEME") or "auto")
    if choice not in THEMES:
        raise ValueError(f"unknown theme {choice!r}; use one of: {', '.join(THEMES)}")
    if choice != "auto":
        return choice
    # COLORFGBG is "foreground;background" (best effort: only some terminals set it)
    background = environ.get("COLORFGBG", "").split(";")[-1]
    return "light" if background in ("7", "15") else "dark"


def to_256(hex_colour: str) -> int:
    """The xterm-256 entry (16 to 255) nearest to ``#rrggbb``."""
    rgb = tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    levels = [min(range(6), key=lambda i: abs(_CUBE[i] - value)) for value in rgb]
    cube = (16 + 36 * levels[0] + 6 * levels[1] + levels[2],
            tuple(_CUBE[i] for i in levels))
    step = min(range(24), key=lambda i: abs(8 + 10 * i - sum(rgb) / 3))
    grey = (232 + step, (8 + 10 * step,) * 3)
    return min((cube, grey), key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c[1])))[0]


def strip_escapes(text: str) -> str:
    """*text* without its colour sequences."""
    return _SGR.sub("", text)


class Style:
    """Paint text in the colour of a role, for one colour level and theme (AC-5.1)."""

    def __init__(self, level: str, theme: str) -> None:
        self.level, self.theme = level, theme

    def paint(self, text: str, role: str) -> str:
        colour, bold = PALETTES[self.theme][role]  # an unknown role is a KeyError
        if self.level == "none" or not text:
            return text
        if self.level == "truecolor":
            params = "38;2;" + ";".join(str(int(colour[i:i + 2], 16)) for i in (1, 3, 5))
        else:
            params = f"38;5;{to_256(colour)}"
        return f"\x1b[{'1;' if bold else ''}{params}m{text}\x1b[0m"
