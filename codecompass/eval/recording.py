"""Recording generator: keeps the full context each answer was built from (Spec 003 AC-8.2).

``RecordingGenerator(real)`` is passed to ``ask(..., generator=...)``. It passes every call
straight through to the real generator and keeps a copy of each message list sent and
each text returned, in order. Graders then see everything the model saw, including full
tool results, which the audit log keeps only as a first line (§13 C8). No Spec 002 code
changes: ``ask()`` already accepts a generator.
"""

from __future__ import annotations

import copy


class RecordingGenerator:
    """A pass-through generator that records ``{"messages", "output"}`` for every call."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls: list[dict] = []

    def generate(self, messages: list[dict], *, on_text=None) -> str:
        sent = copy.deepcopy(messages)
        extra = {} if on_text is None else {"on_text": on_text}
        output = self.inner.generate(messages, **extra)
        self.calls.append({"messages": sent, "output": output})
        return output

    def count_tokens(self, text: str) -> int:
        return self.inner.count_tokens(text)
