"""Embedder protocol (the production code embedder lands in T10.1)."""

from __future__ import annotations

from typing import Protocol

from codecompass.offline.models import EmbedderIdentity


class Embedder(Protocol):
    identity: EmbedderIdentity

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch deterministically, preserving input order."""
        ...
