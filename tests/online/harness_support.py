"""Shared fixtures for the agent harness tests (T8.x)."""

from __future__ import annotations

from codecompass.online.agent.tools import CommitRecord, ToolOutput
from codecompass.online.context import RetrievedChunk

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "MAX_RETRIES = 5", "src/auth.py", 3, 3, "python", SHA)]
RECORD = CommitRecord(sha="0173e4e" + "1" * 33, author="Alice Tan",
                      date="2024-03-14", subject="Handle flaky upstream service")
ANSWER = "It retries [1].\n\nSources\n[1] src/auth.py, lines 3-3 (indexed at a1b2c3d)"


class FakeTools:
    """A run_tool callable: returns canned outputs in order and records calls."""

    def __init__(self, *outputs: ToolOutput) -> None:
        self.outputs = list(outputs) or [ToolOutput(text="0173e4e ...", commits=(RECORD,))]
        self.calls = []

    def __call__(self, call):
        self.calls.append(call)
        out = self.outputs[min(len(self.calls), len(self.outputs)) - 1]
        return out, False
