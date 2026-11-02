"""Pure text helpers for the terminal UI (Spec 004 US4, US5): no input or output here.

The tool records are the entries of the audit log's ``tool_calls`` (Article V.4).
Colour (US5) is foreground colour only, on a real terminal only, in one of two
Rosé Pine themes.
"""

from __future__ import annotations

import os
import re

from codecompass.online import STALE_WARNING
from codecompass.online.citation import formatter

LIMIT = 100  # longest value shown from a tool call; longer ones end with "…"
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _clean(value) -> str:
    """One printable line: control characters removed, long text cut (AC-4.3)."""
    text = _CONTROL.sub("", str(value).replace("\n", " ").replace("\t", " "))
    return text if len(text) <= LIMIT else text[:LIMIT] + "…"


def tool_calls(rounds) -> list[dict]:
    """The calls that ran: entries that name a tool (AC-4.1)."""
    return [entry for entry in rounds if entry.get("tool") is not None]


def _plain(text: str, role: str) -> str:
    return text


def summary_line(rounds, style=None) -> str:
    n = len(tool_calls(rounds))
    if n == 0:
        text = "▸ No tools called"
    else:
        text = f"▸ {n} tool{'s' if n != 1 else ''} called — type /tools to see them"
    return style.paint(text, "info") if style else text


def _executed(entry, paint) -> list[str]:
    args = " ".join(f"{key}={_clean(value)}" for key, value in entry.get("args", {}).items())
    head = (paint(f"round {entry.get('round', 0)}", "muted") + "  "
            + paint(entry["tool"], "accent") + (f"  {args}" if args else ""))
    detail = [paint("cache hit", "ok") if entry.get("cache_hit") else paint("cache miss", "muted")]
    if entry.get("error"):
        detail.append(paint("failed", "danger"))
    if entry.get("result_summary"):
        detail.append(_clean(entry["result_summary"]))
    return [head, " " * 9 + " · ".join(detail)]


def _other(entry, paint) -> list[str]:
    """A round that ran no tool, so that every round is accounted for (AC-4.2)."""
    where = f"round {entry.get('round', 0)}  "
    if entry.get("malformed"):
        return [paint(where + "malformed request, no tool ran", "warn")]
    if entry.get("final_call"):
        return [paint(where + "request refused: the round limit was reached", "warn")]
    if entry.get("reason") == "tools disabled":
        return [paint(where + "request ignored: tools are off in this mode", "warn")]
    return []


def format_tools(rounds, style=None) -> str:
    """The text `/tools` prints (AC-4.2, Plan 004 section 8); *style* only adds colour."""
    paint = style.paint if style else _plain
    lines = []
    for entry in rounds:
        lines += (_executed(entry, paint) if entry.get("tool") is not None
                  else _other(entry, paint))
    if not tool_calls(rounds):
        return "\n".join([paint("No tools were called for the last question.", "muted")] + lines)
    return "\n".join([paint("Tools called for the last question:", "muted")] + lines)


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


# --- colouring a checked answer (AC-5.4) -----------------------------------------------

_MARKER = re.compile(r"(?<![\w\]])\[(\d+)\]")  # as the checker finds markers
_HEADING = re.compile(r"\s*(?:#+\s*)?\**\s*sources\s*\**\s*:?\s*\**\s*", re.IGNORECASE)
_WHOLE_LINE = {formatter.BANNER: "danger", formatter.UNCITED_NOTE: "warn",
               formatter.PARTIAL_NOTE: "warn", STALE_WARNING: "warn"}

# markdown in the model-written body (Spec 004 AC-6.5); underscores are never emphasis
_MD_HEADING = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
_MD_BULLET = re.compile(r"^(\s*)[-*]\s+(?=\S)")
_MD_CODE = re.compile(r"`([^`\n]+)`")
_MD_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_MD_ITALIC = re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])")
BOLD_ON, BOLD_OFF, ITALIC_ON, ITALIC_OFF = "\x1b[1m", "\x1b[22m", "\x1b[3m", "\x1b[23m"


class Style:
    """Paint text in the colour of a role, for one colour level and theme (AC-5.1)."""

    def __init__(self, level: str, theme: str, capability: str | None = None) -> None:
        # level is what is shown now; capability is what the stream could show, so that
        # /theme can switch colour off and on again (AC-5.7)
        self.level, self.theme = level, theme
        self.capability = level if capability is None else capability

    def paint(self, text: str, role: str) -> str:
        colour, bold = PALETTES[self.theme][role]  # an unknown role is a KeyError
        if self.level == "none" or not text:
            return text
        if self.level == "truecolor":
            params = "38;2;" + ";".join(str(int(colour[i:i + 2], 16)) for i in (1, 3, 5))
        else:
            params = f"38;5;{to_256(colour)}"
        return f"\x1b[{'1;' if bold else ''}{params}m{text}\x1b[0m"


    def answer(self, text: str, markdown: bool = False) -> str:
        """*text* with colour added around the flagged-answer parts, and nothing else.

        Only escape sequences are inserted: with them removed the result is *text*
        (AC-5.4). Marks, tags and banners are recognised only where the formatter puts
        them, so a lookalike in the middle of a line is not touched, nor is a code fence.
        With *markdown*, the model-written body (before the last Sources heading, and
        not a banner, note or mark line) is also styled and its markdown punctuation
        consumed (AC-6.5); nothing the checker produced is changed.
        """
        if self.level == "none":
            return text
        lines = text.split("\n")
        heading = max((i for i, line in enumerate(lines) if _HEADING.fullmatch(line)),
                      default=None)
        out, in_fence = [], False
        for i, line in enumerate(lines):
            body = markdown and (heading is None or i < heading)
            if line.strip().startswith("```"):
                in_fence = not in_fence
                if not body:
                    out.append(line)  # kept as it is; dropped from a styled body
            elif in_fence:
                out.append(self.paint(line, "info") if body else line)
            elif line in _WHOLE_LINE:
                out.append(self.paint(line, _WHOLE_LINE[line]))
            elif i == heading:
                out.append(self.paint(line, "info"))
            elif body and not line.startswith(formatter.MARK):
                out.append(self._inline(self._markdown_line(line)))
            else:
                out.append(self._inline(line))
        return "\n".join(out)

    def _markdown_line(self, line: str) -> str:
        if m := _MD_HEADING.match(line):
            return BOLD_ON + self.paint(self._markdown_inline(m.group(1)), "accent")
        if m := _MD_BULLET.match(line):
            return m.group(1) + "• " + self._markdown_inline(line[m.end():])
        return self._markdown_inline(line)

    def _markdown_inline(self, line: str) -> str:
        """Code spans, then bold and italic outside them; an unbalanced line stays as it is."""
        if line.count("`") % 2:
            return line
        parts = _MD_CODE.split(line)  # text, code, text, code, ...
        if sum(part.count("**") for part in parts[0::2]) % 2:
            return line
        out = []
        for index, part in enumerate(parts):
            if index % 2:
                out.append(self.paint(part, "info"))
            else:
                part = _MD_BOLD.sub(lambda m: BOLD_ON + m.group(1) + BOLD_OFF, part)
                out.append(_MD_ITALIC.sub(lambda m: ITALIC_ON + m.group(1) + ITALIC_OFF, part))
        return "".join(out)

    def _inline(self, line: str) -> str:
        head = tail = ""
        if line.startswith(formatter.MARK):  # "[UNVERIFIED] ": the space stays plain
            head = self.paint(formatter.MARK.rstrip(), "danger") + " "
            line = line[len(formatter.MARK):]
        if line.endswith(formatter.TAG):  # " (not cited)": the space stays plain
            tail = " " + self.paint(formatter.TAG.strip(), "tag")
            line = line[:-len(formatter.TAG)]
        return head + _MARKER.sub(lambda m: self.paint(m.group(0), "accent"), line) + tail


UNAVAILABLE = ("Colour is not available here: neither stdout nor stderr is a terminal "
               "that can show colour.")


class ThemeSwitch:
    """The `/theme` command: none or rose-pine for the rest of the session (AC-5.7).

    *styles* are the live styles of the streams that could ever show colour; the
    command changes their level in place. Nothing is saved.
    """

    def __init__(self, variant: str, styles) -> None:
        self.variant, self.styles = variant, list(styles)

    def state(self) -> str:
        on = any(style.level != "none" for style in self.styles)
        return f"rose-pine ({self.variant})" if on else "none"

    def command(self, argument: str) -> str:
        """Apply `/theme <argument>` and return the reply."""
        if argument == "":
            return f"Theme: {self.state()}. Choices: none, rose-pine."
        if argument == "none":
            for style in self.styles:
                style.level = "none"
            return "Theme: none."
        if argument == "rose-pine":
            capable = [style for style in self.styles if style.capability != "none"]
            if not capable:
                return UNAVAILABLE
            for style in capable:
                style.level = style.capability
            return f"Theme: {self.state()}."
        return f"Unknown theme {argument!r}. Choices: none, rose-pine."


def render_markdown(text: str, style) -> str:
    """The checked answer as shown in live mode: markdown styled (AC-6.5), then AC-5.4."""
    if style is None or style.level == "none":
        return text
    return style.answer(text, markdown=True)

