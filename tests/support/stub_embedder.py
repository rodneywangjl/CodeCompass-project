"""Deterministic stub embedder for the required (model-free) test suite."""

from __future__ import annotations

import hashlib
import math

from codecompass.offline.models import EmbedderIdentity

DIMENSION = 8


class StubEmbedder:
    """Hash-derived vectors: deterministic, fixed dimension, order-preserving."""

    def __init__(self, dimension: int = DIMENSION) -> None:
        self.identity = EmbedderIdentity(
            model="stub", revision="stub-1", dimension=dimension
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        dim = self.identity.dimension
        vec = [digest[i % len(digest)] / 255.0 for i in range(dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
