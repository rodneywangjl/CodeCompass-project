"""Chunks are sized with the embedder's own tokenizer (bug fix; Spec 001 C7, AC-3.3).

Bug: the chunkers accept an injected ``tokenizer`` but the orchestrator never
passed one, so every file was sized by whitespace-separated words. Code is far
denser than that: in spm_proj a 488-line function counted as 2,790 "words" but
was 9,297 real tokens, over the embedder's 8,192-token limit (Article VIII.1),
and a single chunk that size cannot be embedded in a reasonable amount of memory.

Here the fake embedder counts one token per character, so a line that is one
"word" is many tokens. The chunker has to follow the embedder, not the words.
"""

import dataclasses

import pytest

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from tests.support.fixture_repo import _commit, _git
from tests.support.stub_embedder import StubEmbedder

TARGET, HARD_MAX = 200, 600  # in the embedder's tokens (here: characters)


def _dense_python():
    # One whitespace-separated word per line (plus the def): ~80 words, ~2,600 characters.
    return "def dense():\n" + "".join(
        f"    v{i}=f(1,2,3,4,5,6,7,8,9)\n" for i in range(80))


def _dense_go():
    return "package main\n\n" + "".join(
        f"v{i}:=f(1,2,3,4,5,6,7,8,9)\n" for i in range(80))


FILES = {"src/dense.py": _dense_python, "src/dense.go": _dense_go}


class CharTokenEmbedder(StubEmbedder):
    """One token per character; records every text it is asked to embed."""

    def __init__(self):
        super().__init__()
        self.texts = []

    def tokenize(self, text):
        return list(text)

    def embed(self, texts):
        self.texts.extend(texts)
        return super().embed(texts)


class WordOnlyEmbedder(StubEmbedder):
    """No tokenize method: the chunker keeps its word-count default."""

    def __init__(self):
        super().__init__()
        self.texts = []

    def embed(self, texts):
        self.texts.extend(texts)
        return super().embed(texts)


def _repo(tmp_path, path):
    repo = tmp_path / "repo"
    (repo / path).parent.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / path).write_text(FILES[path]())
    _git(repo, "add", "-A")
    _commit(repo, "dense file")
    return repo


def _config():
    cfg = load_config(None)
    return dataclasses.replace(cfg, chunking=dataclasses.replace(
        cfg.chunking, target_tokens=TARGET, hard_max_tokens=HARD_MAX))


def _run(tmp_path, path, embedder):
    repo = _repo(tmp_path, path)
    orchestrator.run(repo, config=_config(), index_dir=tmp_path / "idx",
                     embedder=embedder)
    return embedder


# AC-3.3 / C7: no emitted chunk exceeds the limit, counted in the embedder's tokens.
@pytest.mark.parametrize("path", sorted(FILES))  # structured (py) and fallback (go)
def test_no_chunk_exceeds_the_hard_max_in_embedder_tokens(tmp_path, path):
    emb = _run(tmp_path, path, CharTokenEmbedder())
    assert len(emb.texts) > 1, "the dense file should have been split"
    assert max(len(t) for t in emb.texts) <= HARD_MAX


# The sizing is not lost: the whole file is still covered by the chunks.
def test_all_lines_still_land_in_some_chunk(tmp_path):
    emb = _run(tmp_path, "src/dense.py", CharTokenEmbedder())
    joined = "\n".join(emb.texts)
    for i in range(80):
        assert f"v{i}=f(" in joined


# An embedder with no tokenizer keeps the old word-count sizing (stub embedders).
def test_embedder_without_tokenize_keeps_word_sizing(tmp_path):
    emb = _run(tmp_path, "src/dense.py", WordOnlyEmbedder())
    assert len(emb.texts) == 1  # ~80 words: well under the target when counted as words
