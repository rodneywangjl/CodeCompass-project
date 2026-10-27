"""Generator interface and errors (Article VIII.4, Plan §4)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Generator(Protocol):
    def generate(self, messages: list[dict]) -> str:
        """Send chat messages, return the model's text response."""
        ...

    def count_tokens(self, text: str) -> int:
        """Tokens *text* occupies in this generator's context window (Plan D4)."""
        ...


class GeneratorError(RuntimeError):
    """The generator could not answer: server unreachable, timed out or not ready."""


class ServerMismatchError(GeneratorError):
    """The running llama-server cannot serve the active profile (AC-5.12)."""
