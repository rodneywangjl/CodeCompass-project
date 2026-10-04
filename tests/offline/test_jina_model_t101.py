"""T10.1 real code embedder tests (model-marked: local only, needs download)."""

import math

import pytest

pytestmark = pytest.mark.model

from codecompass.offline.config import load_config
from codecompass.offline.embedding import CodeEmbedder


def _embedder():
    return CodeEmbedder(load_config(None).embedder)


def test_loads_pinned_revision_with_recorded_dimension():
    emb = _embedder()
    assert emb.identity.revision, "revision must be pinned, never empty"
    vecs = emb.embed(["def f():\n    pass\n"])
    assert len(vecs[0]) == emb.identity.dimension == 768


def test_deterministic_and_batch_matches_single():
    emb = _embedder()
    texts = ["def f():\n    pass\n", "class A:\n    pass\n"]
    assert emb.embed(texts) == emb.embed(texts)
    singles = [emb.embed([t])[0] for t in texts]
    batched = emb.embed(texts)
    for s, b in zip(singles, batched):
        assert math.dist(s, b) < 1e-5


def test_tokenizer_and_query_finds_known_chunk():
    emb = _embedder()
    assert len(emb.tokenize("a b c")) == 3
    chunks = ["def get_user_by_id():\n    pass\n",
              "import os\n",
              "xxxx yyyy zzzz\n"]
    query = "find user by identifier"
    scored = sorted(
        ((math.dist(emb.embed([query])[0], v), i)
         for i, v in enumerate(emb.embed(chunks))),
        key=lambda t: t[0])
    assert scored[0][1] == 0
