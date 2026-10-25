"""Parse tool calls from the model's text output (Article VIII.2, Plan D5)."""

from __future__ import annotations

import ast
import re

from codecompass.online.models import ToolCall

_BLOCK = re.compile(r"<tool>(.*?)</tool>", re.DOTALL)
_UNCLOSED = re.compile(r"<tool>.*\Z", re.DOTALL)


def _parse_one(source: str) -> ToolCall | None:
    """``name(key=literal, ...)`` or None. Parsed with ast, never evaluated."""
    try:
        node = ast.parse(source.strip(), mode="eval").body
    except SyntaxError:
        return None
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)) or node.args:
        return None
    args = {}
    for kw in node.keywords:
        if kw.arg is None or not isinstance(kw.value, ast.Constant):
            return None
        if not isinstance(kw.value.value, (str, int)) or isinstance(kw.value.value, bool):
            return None
        args[kw.arg] = kw.value.value
    return ToolCall(tool=node.func.id, args=args)


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Well-formed tool calls in order; malformed blocks are ignored."""
    calls = (_parse_one(m.group(1)) for m in _BLOCK.finditer(text))
    return [c for c in calls if c is not None]


def strip_tool_blocks(text: str) -> str:
    """Remove all tool blocks, including an unclosed one at the end."""
    return _UNCLOSED.sub("", _BLOCK.sub("", text)).strip()
