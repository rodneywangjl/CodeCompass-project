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


def classify_size(n_tokens: int, policy: SizePolicy) -> str:
    if n_tokens > policy.hard_max_tokens:
        return "over_hard_max"
    if n_tokens > policy.target_tokens:
        return "over_target"
    return "fits"
