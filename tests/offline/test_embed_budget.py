"""Embedding batches are bounded by memory cost, not only by count (bug fix).

Bug: ``embed_in_batches`` sorted chunks by length and cut them into batches of
``batch_size``. The longest chunks therefore arrived together in the last
batches. Attention memory grows with batch size times the square of the longest
sequence, so 32 chunks of ~2,800 tokens needed ~12 GB and indexing a 491-file
repo on the CPU filled RAM and swap (indexing spm_proj, 2026-11-01).

Fix under test: a batch is cut when ``len(batch) * longest ** 2`` would exceed
``max_batch_cost``, where lengths are real embedder tokens when the embedder can
count them. A single text over the budget still goes through, alone.
"""

import dataclasses
import random

from codecompass.offline import orchestrator
from codecompass.offline.config import EmbedderConfig, config_from_dict, load_config
from codecompass.offline.embedding import embed_in_batches
from codecompass.offline.models import EmbedderIdentity
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder

BUDGET = 32 * 1024 ** 2  # the default: batches of up to 1,024 tokens are unaffected


class WordEmbedder:
    """Fake embedder: one token per word. Records every batch it is given."""

    identity = EmbedderIdentity(model="fake", revision="r", dimension=2)

    def __init__(self):
        self.batches = []

    def tokenize(self, text):
        return text.split()

    def embed(self, texts):
        self.batches.append(list(texts))
        # The vector encodes the text, so a test can tell which text it belongs to.
        return [[float(len(t.split())), float(sum(map(ord, t)) % 9973)] for t in texts]


def _words(n, tag="w"):
    return " ".join([tag] * n)


def _cost(batch, embedder):
    return len(batch) * max(len(embedder.tokenize(t)) for t in batch) ** 2


def _mixed_texts():
    """Mostly short chunks, a tail of long ones, one beyond the model's limit."""
    texts = [_words(10 + i % 5, f"s{i}") for i in range(70)]
    texts += [_words(3000, f"long{i}") for i in range(6)]
    texts += [_words(9300, "huge")]
    random.Random(7).shuffle(texts)
    return texts


# AC: no batch of more than one text exceeds the cost budget.
def test_no_multi_text_batch_exceeds_the_budget():
    emb, texts = WordEmbedder(), _mixed_texts()
    embed_in_batches(emb, texts, 32, BUDGET)
    for batch in emb.batches:
        assert len(batch) == 1 or _cost(batch, emb) <= BUDGET, (
            len(batch), max(len(emb.tokenize(t)) for t in batch))


# The reported case: 32 chunks of ~2,800 tokens must not travel together.
def test_the_reported_case_is_split():
    emb = WordEmbedder()
    texts = [_words(2800, f"c{i}") for i in range(32)]
    embed_in_batches(emb, texts, 32, BUDGET)
    assert max(len(b) for b in emb.batches) <= 4  # 4 * 2800**2 is under 32 * 1024**2
    assert len(emb.batches) >= 8


# No regression for the common case: short chunks still fill a batch.
def test_short_chunks_still_fill_a_batch():
    emb = WordEmbedder()
    texts = [_words(100, f"s{i}") for i in range(64)]
    embed_in_batches(emb, texts, 32, BUDGET)
    assert [len(b) for b in emb.batches] == [32, 32]


# The count limit still applies on top of the budget.
def test_batch_size_still_caps_the_count():
    emb = WordEmbedder()
    embed_in_batches(emb, [_words(5, f"s{i}") for i in range(10)], 3, BUDGET)
    assert all(len(b) <= 3 for b in emb.batches)


# Edge: a text above the budget on its own is embedded, alone, never dropped.
def test_one_oversize_text_is_embedded_alone():
    emb = WordEmbedder()
    huge = _words(9300, "huge")
    out = embed_in_batches(emb, [_words(5, "a"), huge, _words(6, "b")], 32, BUDGET)
    assert [huge] in emb.batches
    assert len(out) == 3


# Order: every vector lands on the text it was made from, whatever the input order.
def test_vectors_map_back_to_the_input_order():
    emb, texts = WordEmbedder(), _mixed_texts()
    out = embed_in_batches(emb, texts, 32, BUDGET)
    assert out == [emb.embed([t])[0] for t in texts]


# Lengths are tokens, not characters: few tokens in many characters is cheap.
def test_lengths_are_embedder_tokens_not_characters():
    emb = WordEmbedder()
    texts = ["x" * 20000 + f"{i}" for i in range(32)]  # one word each, huge in characters
    embed_in_batches(emb, texts, 32, BUDGET)
    assert [len(b) for b in emb.batches] == [32]


# Embedder without a token counter (the stub): falls back to character counts
# and keeps the old guarantees (bounded count, length-sorted).
def test_embedder_without_tokenize_still_batches_sorted():
    emb = StubEmbedder()
    seen = []
    real = emb.embed
    emb.embed = lambda texts: (seen.append(list(texts)), real(texts))[1]
    texts = ["x" * n for n in (50, 5, 500, 20, 9, 300)]
    out = embed_in_batches(emb, texts, 2, BUDGET)
    assert all(len(b) <= 2 for b in seen)
    flat = [t for b in seen for t in b]
    assert flat == sorted(flat, key=len)
    assert out == real(texts)


# With no budget the behaviour is the old one: count only.
def test_no_budget_means_count_only():
    emb = WordEmbedder()
    texts = [_words(2800, f"c{i}") for i in range(32)]
    embed_in_batches(emb, texts, 32, None)
    assert [len(b) for b in emb.batches] == [32]


def test_nothing_to_embed_makes_no_call():
    emb = WordEmbedder()
    assert embed_in_batches(emb, [], 32, BUDGET) == []
    assert emb.batches == []


# Config: the budget is a named setting with a default, not a magic number.
def test_config_has_a_default_budget():
    assert load_config(None).embedder.max_batch_cost == BUDGET
    assert EmbedderConfig().max_batch_cost == BUDGET


def test_config_accepts_the_budget_from_toml_data():
    cfg = config_from_dict({"embedder": {"max_batch_cost": 1_000_000}})
    assert cfg.embedder.max_batch_cost == 1_000_000


# Wiring: the orchestrator passes the configured budget through to the batching.
def test_orchestrator_honours_the_configured_budget(tmp_path):
    class Spy(StubEmbedder):
        def __init__(self):
            super().__init__()
            self.batches = []

        def tokenize(self, text):
            return list(text)  # one token per character

        def embed(self, texts):
            self.batches.append(list(texts))
            return super().embed(texts)

    budget = 4000
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    cfg = dataclasses.replace(cfg, embedder=dataclasses.replace(
        cfg.embedder, batch_size=32, max_batch_cost=budget))
    spy = Spy()
    orchestrator.run(fx.path, config=cfg, index_dir=tmp_path / "idx", embedder=spy)
    assert spy.batches
    for batch in spy.batches:
        assert len(batch) == 1 or len(batch) * max(map(len, batch)) ** 2 <= budget
    assert any(len(b) < 32 for b in spy.batches)
