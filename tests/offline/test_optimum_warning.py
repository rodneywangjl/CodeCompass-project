"""The jina remote code's harmless 'optimum is not installed' warning is hidden.

Only that one message, only while the embedder loads. Uses a fake
sentence_transformers, so no model download is needed.
"""

import sys
import types
import warnings

from codecompass.offline.config import EmbedderConfig
from codecompass.offline.embedding import CodeEmbedder

OPTIMUM = ("optimum is not installed. To use OnnxConfig and BertOnnxConfig, "
           "make sure that `optimum` package is installed")


def _fake_sentence_transformers(monkeypatch, emitted):
    """Install a SentenceTransformer whose constructor emits *emitted* warnings."""
    class FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            for message in emitted:
                warnings.warn(message, UserWarning)

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def _load_and_collect(emitted, monkeypatch):
    _fake_sentence_transformers(monkeypatch, emitted)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        CodeEmbedder(EmbedderConfig())._load()
    return [str(w.message) for w in caught]


def test_optimum_warning_is_hidden_while_loading(monkeypatch):
    assert _load_and_collect([OPTIMUM], monkeypatch) == []


def test_other_warnings_during_load_are_still_shown(monkeypatch):
    other = "something else is deprecated"
    assert _load_and_collect([OPTIMUM, other], monkeypatch) == [other]


def test_the_filter_does_not_outlive_the_load(monkeypatch):
    _load_and_collect([], monkeypatch)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn(OPTIMUM, UserWarning)
    assert [str(w.message) for w in caught] == [OPTIMUM]
