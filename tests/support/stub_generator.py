"""Deterministic stub generator for the required (model-free) test suite."""

from __future__ import annotations

import copy

TOOL_CALL_BLAME = '<tool>git_blame(path="src/auth.py", lines="1-12")</tool>'
TOOL_CALL_LOG = '<tool>git_log(path="src/auth.py", n=10)</tool>'
MALFORMED_TOOL_CALL = '<tool>git_blame(path="src/auth.py"'
ANSWER_NO_SOURCES = "I could not find enough evidence to answer this question."


def answer_citing(path: str, start: int, end: int, commit: str) -> str:
    """An answer with one code citation in the fixed Sources format (Article VI.4)."""
    return (
        f"The function is defined in {path} [1].\n\n"
        "Sources\n"
        f"[1] {path}, lines {start}-{end} (indexed at {commit[:7]})\n"
    )


class StubGenerator:
    """Returns canned responses in order, then repeats the last one."""

    def __init__(self, responses: list[str]) -> None:
        if not responses:
            raise ValueError("StubGenerator needs at least one response")
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def generate(self, messages: list[dict]) -> str:
        self.calls.append(copy.deepcopy(messages))
        index = min(len(self.calls), len(self._responses)) - 1
        return self._responses[index]

    def count_tokens(self, text: str) -> int:
        return len(text.split())
