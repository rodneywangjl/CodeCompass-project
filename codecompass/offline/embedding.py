"""Embedder protocol (the production code embedder lands in T10.1)."""

from __future__ import annotations

from typing import Protocol

from codecompass.offline.models import EmbedderIdentity


class Embedder(Protocol):
    identity: EmbedderIdentity

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch deterministically, preserving input order."""
        ...


def _lengths(embedder: Embedder, texts: list[str]) -> list[int]:
    """Token counts from the embedder when it can count, else character counts."""
    count = getattr(embedder, "tokenize", None)
    if callable(count):
        return [len(count(t)) for t in texts]
    return [len(t) for t in texts]


def _plan_batches(lengths: list[int], batch_size: int,
                  max_batch_cost: int | None) -> list[list[int]]:
    """Cut length-sorted positions into batches of bounded count and cost.

    Sorted ascending, the longest text of a batch is its last one, so adding a
    text costs ``(count + 1) * length ** 2``. A text over the budget on its own
    still gets a batch (of one): it is embedded, never dropped.
    """
    order = sorted(range(len(lengths)), key=lambda k: lengths[k])
    batches: list[list[int]] = []
    batch: list[int] = []
    for k in order:
        full = bool(batch) and (
            len(batch) >= batch_size
            or (max_batch_cost is not None
                and (len(batch) + 1) * lengths[k] ** 2 > max_batch_cost))
        if full:
            batches.append(batch)
            batch = []
        batch.append(k)
    if batch:
        batches.append(batch)
    return batches


def embed_in_batches(embedder: Embedder, texts: list[str], batch_size: int,
                     max_batch_cost: int | None = None) -> list:
    """Embed length-sorted in batches, mapping vectors back to input order (O4).

    A batch holds at most ``batch_size`` texts and, when ``max_batch_cost`` is
    set, at most ``texts * longest ** 2`` of that cost (attention memory grows
    with it), so long chunks never travel in a large batch.
    """
    if not texts:
        return []
    batches = _plan_batches(_lengths(embedder, texts),
                            batch_size or len(texts), max_batch_cost)
    got: dict[int, list[float]] = {}
    for slot in batches:
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


_SHARED: dict = {}
_SHARED_MAX = 4


def shared_embedder(embedder_config) -> CodeEmbedder:
    """The process-wide default embedder for *embedder_config* (plan 002 O1, O2).

    ensure_current and open_index share one instance per configuration, so the
    model loads once per process, not once per question. The key includes the
    embedder class as looked up now, so a substituted class never receives an
    instance built by another. The identity check against the index
    (Article II.4) is unchanged: it runs on every open_index.
    """
    key = (CodeEmbedder, embedder_config)
    if key not in _SHARED:
        if len(_SHARED) >= _SHARED_MAX:
            _SHARED.pop(next(iter(_SHARED)))  # drop the oldest
        _SHARED[key] = CodeEmbedder(embedder_config)
    return _SHARED[key]
