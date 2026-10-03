"""T3.1 token sizing tests (tests-first)."""

from codecompass.offline.chunking.sizing import (
    SizePolicy,
    batch_count,
    classify_size,
    count_tokens,
)


def _tok(text):
    return text.split()


def test_counts_come_from_injected_tokenizer():
    assert count_tokens("a b c", _tok) == 3
    assert count_tokens("", _tok) == 0


def test_batch_equals_per_item():
    texts = ["a b", "", "x y z"]
    assert batch_count(texts, _tok) == [count_tokens(t, _tok) for t in texts]


def test_policy_thresholds():
    p = SizePolicy(target_tokens=10, hard_max_tokens=20)
    assert classify_size(5, p) == "fits"
    assert classify_size(10, p) == "fits"
    assert classify_size(11, p) == "over_target"
    assert classify_size(20, p) == "over_target"
    assert classify_size(21, p) == "over_hard_max"
