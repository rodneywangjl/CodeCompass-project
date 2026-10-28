"""T13.1 real cross-encoder re-ranker tests (tests-first).

Contract under test (Spec AC-2.7; Article VIII.1 as of 1.2.1: the re-ranker
revision is pinned):
  - reranker.revision defaults to a pinned 40-character commit and can be set
    in codecompass.toml
  - retrieval.reranker.BgeReranker(reranker_config) loads lazily through
    sentence_transformers.CrossEncoder with that model, revision and device
  - model-marked (local only): a relevant chunk outscores an irrelevant one,
    and scoring is deterministic
"""

import re
import sys
import types

import pytest

from codecompass.online.config import OnlineConfig, RerankerConfig, load_online_config
from codecompass.online.retrieval import reranker


def test_revision_is_pinned_by_default_and_configurable(tmp_path):
    assert re.fullmatch(r"[0-9a-f]{40}", OnlineConfig().reranker.revision)
    f = tmp_path / "codecompass.toml"
    f.write_text('[reranker]\nrevision = "' + "a" * 40 + '"\n')
    assert load_online_config(f).reranker.revision == "a" * 40


def test_loader_passes_model_revision_and_device(monkeypatch):
    seen = {}

    class FakeCrossEncoder:
        def __init__(self, model, **kwargs):
            seen.update(model=model, **kwargs)

        def predict(self, pairs, **kwargs):
            return [float(len(text)) for _, text in pairs]

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(CrossEncoder=FakeCrossEncoder))
    cfg = RerankerConfig(model="org/model", revision="b" * 40, device="cpu")
    model = reranker.BgeReranker(cfg)
    assert seen == {}, "the model must load lazily, on first use"
    assert model.rerank("q", ["ab", "abcd"]) == [2.0, 4.0]
    assert seen == {"model": "org/model", "revision": "b" * 40, "device": "cpu"}
    assert model.rerank("q", []) == []


@pytest.mark.model
def test_real_reranker_prefers_the_relevant_chunk():
    model = reranker.BgeReranker(OnlineConfig().reranker)
    relevant = ("def authenticate(client, user, password):\n"
                "    for attempt in range(MAX_RETRIES):\n"
                "        try:\n            return client.login(user, password)\n"
                "        except TimeoutError:\n            time.sleep(2 ** attempt)\n")
    irrelevant = "def noop():\n    return None\n"
    question = "Why does login retry when it times out?"
    first = model.rerank(question, [relevant, irrelevant])
    assert first[0] > first[1]
    assert model.rerank(question, [relevant, irrelevant]) == first
