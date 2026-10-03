"""Embedder protocol (the production code embedder lands in T10.1)."""

from __future__ import annotations

from typing import Protocol

from codecompass.offline.models import EmbedderIdentity


class Embedder(Protocol):
    identity: EmbedderIdentity

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch deterministically, preserving input order."""
        ...


def embed_in_batches(embedder: Embedder, texts: list[str], batch_size: int) -> list:
    """Embed length-sorted in batches, mapping vectors back to input order (O4)."""
    if not texts:
        return []
    step = batch_size or len(texts)
    order = sorted(range(len(texts)), key=lambda k: len(texts[k]))
    got: dict[int, list[float]] = {}
    for j in range(0, len(order), step):
        slot = order[j:j + step]
        for k, vector in zip(slot, embedder.embed([texts[k] for k in slot])):
            got[k] = vector
    return [got[k] for k in range(len(texts))]
