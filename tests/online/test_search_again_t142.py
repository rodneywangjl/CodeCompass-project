"""T14.2 search_again tests (tests-first).

Contract under test (Constitution IV, V.2, VI.4 as of 1.4.0; Plan D3, D18):
  - tools.search_again(handles, query, *, seen, reranker, config, max_tokens,
    count_tokens) -> ToolOutput
  - runs the model's query (not the original question) through the existing
    hybrid retrieval and re-ranker
  - skips chunks already in context (`seen`: chunk ids); returns the remaining
    chunks in re-rank order while they fit max_tokens, in the D3 format
    (text == format_context(chunks)); ToolOutput.chunks holds them for VI.4
  - nothing new: a plain message, no chunks, not an error
  - best new chunk too big to show: no chunks, and a hint to use open_file on it
  - query must be a non-empty string of at most 200 characters (ToolArgumentError)
"""

import dataclasses

import pytest

import codecompass.offline as offline
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.agent import tools
from codecompass.online.config import RetrievalConfig
from codecompass.online.context import format_context
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

COUNT = StubGenerator(["x"]).count_tokens
BIG = 10_000
QUERY = "def noop return None"


@pytest.fixture(scope="module")
def handles(tmp_path_factory):
    root = tmp_path_factory.mktemp("search")
    repo = build_history_repo(root / "repo")
    cfg = dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    offline.ensure_current(repo.path, config=cfg, index_dir=root / "idx",
                           embedder=StubEmbedder())
    h = offline.open_index(repo.path, config=cfg, index_dir=root / "idx",
                           embedder=StubEmbedder())
    yield h
    h.close()


def search(handles, query=QUERY, *, seen=(), reranker=None, max_tokens=BIG):
    return tools.search_again(handles, query, seen=set(seen),
                              reranker=reranker or StubReranker(),
                              config=RetrievalConfig(), max_tokens=max_tokens,
                              count_tokens=COUNT)


# --- finding code ---------------------------------------------------------------

def test_returns_reranked_chunks_in_the_d3_format(handles):
    out = search(handles)
    assert not out.error
    assert out.chunks
    assert out.chunks[0].path == "src/util.py"       # best match for the query
    assert out.text == format_context(list(out.chunks))


def test_uses_the_models_query(handles):
    reranker = StubReranker()
    search(handles, "authenticate MAX_RETRIES", reranker=reranker)
    assert reranker.calls[-1][0] == "authenticate MAX_RETRIES"


# --- skipping what the model already has ----------------------------------------

def test_chunks_already_in_context_are_skipped(handles):
    first = search(handles)
    seen = {first.chunks[0].chunk_id}
    again = search(handles, seen=seen)
    assert seen.isdisjoint(c.chunk_id for c in again.chunks)


def test_nothing_new_is_a_plain_message(handles):
    everything = search(handles, max_tokens=BIG)
    out = search(handles, seen={c.chunk_id for c in everything.chunks})
    assert out.chunks == () and not out.error
    assert "nothing new" in out.text.lower()


# --- fitting the token cap ------------------------------------------------------

def test_result_fits_the_cap(handles):
    full = search(handles)
    cap = COUNT(format_context([full.chunks[0]]))      # room for exactly one chunk
    out = search(handles, max_tokens=cap)
    assert len(out.chunks) == 1
    assert COUNT(out.text) <= cap


def test_best_chunk_too_big_suggests_open_file(handles):
    out = search(handles, max_tokens=5)
    assert out.chunks == () and not out.error
    assert "open_file" in out.text and "src/util.py" in out.text


# --- query validation -----------------------------------------------------------

@pytest.mark.parametrize("query", ["", "   ", "x" * 201, 42, None])
def test_bad_queries_are_rejected(handles, query):
    with pytest.raises(tools.ToolArgumentError):
        search(handles, query)
