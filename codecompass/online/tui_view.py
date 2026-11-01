"""Pure text helpers for the terminal UI (Spec 004 US4): no input or output here.

The tool records are the entries of the audit log's ``tool_calls`` (Article V.4).
"""

from __future__ import annotations

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
