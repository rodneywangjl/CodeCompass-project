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


class CodeEmbedder:
    """Pinned local code embedder over sentence-transformers (T10.1).

    The model loads lazily on first use (and never when there is nothing to
    embed), runs on the configured device, and needs no paid service. The
    revision is pinned because loading requires ``trust_remote_code``.
    Implements the :class:`Embedder` protocol (batched, deterministic).
    """

    def __init__(self, embedder_config) -> None:
        self._config = embedder_config
        self.identity = EmbedderIdentity(
            model=embedder_config.model,
            revision=embedder_config.revision,
            dimension=embedder_config.dimension,
        )
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self._config.model,
                revision=self._config.revision or None,
                trust_remote_code=True,
                device=self._config.device,
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            list(texts), batch_size=self._config.batch_size,
            normalize_embeddings=True, show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [list(map(float, row)) for row in vectors]

    def tokenize(self, text: str) -> list[int]:
        """Token ids from the embedder's own tokenizer (C7, AC-3.3)."""
        return self._load().tokenizer.encode(text, add_special_tokens=False)
