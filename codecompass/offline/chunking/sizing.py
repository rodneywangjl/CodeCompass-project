"""Token counting and size policy (AC-3.3 support, C7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizePolicy:
    target_tokens: int = 512
    hard_max_tokens: int = 8192


def count_tokens(text: str, tokenizer) -> int:
    """Count tokens with an injected tokenizer (callable text -> token list)."""
    return len(tokenizer(text))


def batch_count(texts: list[str], tokenizer) -> list[int]:
    return [count_tokens(t, tokenizer) for t in texts]


def split_long_line(text: str, tokenizer, hard_max: int) -> list[str]:
    """Split one line over the hard max into pieces that each count within it (T11.1).

    Splits by characters and re-counts every piece with *tokenizer*, so it never
    joins tokens (the embedder's tokenizer returns integer ids). The pieces
    concatenate back to *text* exactly. Raises ValueError when a single character
    still counts over the limit, rather than emitting an oversize piece.
    """
    if not text:
        return []
    window = max(1, len(text) * hard_max // max(1, count_tokens(text, tokenizer)))
    pieces: list[str] = []
    start = 0
    while start < len(text):
        size = min(window, len(text) - start)
        piece = text[start:start + size]
        n = count_tokens(piece, tokenizer)
        while n > hard_max and size > 1:
            size = max(1, min(size - 1, size * hard_max // n))
            piece = text[start:start + size]
            n = count_tokens(piece, tokenizer)
        if n > hard_max:
            raise ValueError(f"one character counts {n} tokens, over the hard max of {hard_max}")
        pieces.append(piece)
        start += size
    return pieces


def classify_size(n_tokens: int, policy: SizePolicy) -> str:
    if n_tokens > policy.hard_max_tokens:
        return "over_hard_max"
    if n_tokens > policy.target_tokens:
        return "over_target"
    return "fits"
