"""T14.3 wiring tests (tests-first).

Contract under test (Constitution V.2, VI.1, VI.4 as of 1.4.0; Plan D14, D17, D18):
  - tools.ToolContext(count_tokens, handles=None, reranker=None, retrieval=None,
    seen=set()) carries what open_file and search_again need;
    tools.execute(..., context=ctx) dispatches all four tools
  - open_file(path) without lines takes its outline from the index
    (VectorStore.symbols_for_path)
  - search_again with no index is an error result; chunks a tool returns are
    added to ctx.seen, so search_again never repeats them
  - make_tool_runner(..., handles=, reranker=, retrieval=, seen=) builds the context
  - the harness collects every tool's chunks in AgentRun.chunks
  - the D14 tool rule and the malformed-call hint list all tools
  - ask(): code shown by open_file is citable (F); the same citation without
    the tool is flagged (G)
"""

import dataclasses

import pytest

import codecompass.offline as offline
import codecompass.online as online
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.agent import harness, tools
from codecompass.online.config import RetrievalConfig, ToolsConfig
from codecompass.online.context import RetrievedChunk, format_chunk
from codecompass.online.models import ToolCall
from tests.online.ask_support import config, stubs
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

COUNT = StubGenerator(["x"]).count_tokens


@pytest.fixture(scope="module")
def indexed(tmp_path_factory):
    root = tmp_path_factory.mktemp("wiring")
    repo = build_history_repo(root / "repo")
    cfg = dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    offline.ensure_current(repo.path, config=cfg, index_dir=root / "idx",
                           embedder=StubEmbedder())
    h = offline.open_index(repo.path, config=cfg, index_dir=root / "idx",
                           embedder=StubEmbedder())
    yield repo, h
    h.close()


def run(repo, h, tool, args, ctx):
    return tools.execute(repo.path, h.meta.indexed_commit, ToolCall(tool=tool, args=args),
                         settings=ToolsConfig(), context=ctx)


def full_ctx(h, **kw):
    return tools.ToolContext(count_tokens=COUNT, handles=h, reranker=StubReranker(),
                             retrieval=RetrievalConfig(), **kw)


# --- execute() dispatches the new tools --------------------------------------------

def test_execute_runs_open_file(indexed):
    repo, h = indexed
    out = run(repo, h, "open_file", {"path": "src/auth.py", "lines": "6-12"},
              tools.ToolContext(count_tokens=COUNT))
    assert not out.error and out.chunks[0].start_line == 6


def test_open_file_rejects_unknown_arguments(indexed):
    repo, h = indexed
    out = run(repo, h, "open_file", {"path": "src/auth.py", "n": 3},
              tools.ToolContext(count_tokens=COUNT))
    assert out.error and "unexpected" in out.text


def test_outline_comes_from_the_index(indexed):
    repo, h = indexed
    names = [name for name, _, _ in h.vector.symbols_for_path("src/auth.py")]
    assert "authenticate" in names
    out = run(repo, h, "open_file", {"path": "src/auth.py"}, full_ctx(h))
    assert "authenticate" in out.text and out.chunks == ()


def test_search_again_without_an_index_is_an_error(indexed):
    repo, h = indexed
    out = run(repo, h, "search_again", {"query": "noop"},
              tools.ToolContext(count_tokens=COUNT))
    assert out.error and "not available" in out.text


def test_search_again_results_are_added_to_seen(indexed):
    repo, h = indexed
    ctx = full_ctx(h)
    first = run(repo, h, "search_again", {"query": "def noop return None"}, ctx)
    assert first.chunks
    assert {c.chunk_id for c in first.chunks} <= ctx.seen
    again = run(repo, h, "search_again", {"query": "def noop return None"}, ctx)
    assert {c.chunk_id for c in first.chunks}.isdisjoint(c.chunk_id for c in again.chunks)


def test_tool_runner_builds_the_context(indexed):
    repo, h = indexed
    runner = harness.make_tool_runner(repo.path, h.meta.indexed_commit, ToolsConfig(), COUNT,
                                      handles=h, reranker=StubReranker(),
                                      retrieval=RetrievalConfig(), seen=set())
    out, hit = runner(ToolCall(tool="search_again", args={"query": "noop"}))
    assert not out.error and not hit


# --- the harness collects tool evidence --------------------------------------------

def test_harness_collects_tool_chunks():
    chunk = RetrievedChunk("open_file:src/util.py:1-2", "def noop():\n    return None",
                           "src/util.py", 1, 2, "python", "a1b2c3d" + "0" * 33)
    shown = tools.ToolOutput(text=format_chunk(chunk), chunks=(chunk,))
    gen = StubGenerator(['<tool>open_file(path="src/util.py", lines="1-2")</tool>', ANSWER])
    result = harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(shown), max_rounds=3)
    assert result.chunks == [chunk]


# --- the model is told about every tool ----------------------------------------------

@pytest.mark.parametrize("example", [
    '<tool>search_again(query="', '<tool>open_file(path="file/path.py", lines="X-Y")</tool>',
    '<tool>open_file(path="file/path.py")</tool>', '<tool>git_blame(path="',
    '<tool>git_log(path="'])
def test_prompt_lists_every_tool(example):
    assert example in harness.system_prompt(tools_enabled=True)


def test_malformed_hint_lists_the_new_tools():
    hint = harness.malformed_result_message("oops")
    assert "open_file(path=" in hint and "search_again(query=" in hint


# --- end to end: citations to tool code (VI.4) -------------------------------------

def _ask(tmp_path, responses):
    repo = build_history_repo(tmp_path / "repo")
    cfg = config(tmp_path)
    cfg = dataclasses.replace(cfg, retrieval=dataclasses.replace(cfg.retrieval, final_k=1))
    answer = (f"noop returns None [1].\n\nSources\n"
              f"[1] src/util.py, lines 1-2 (indexed at {repo.commits['wip'][:7]})")
    gen = StubGenerator([r if r != "ANSWER" else answer for r in responses])
    return online.ask(repo.path, "Why does authenticate retry on timeout?", config=cfg,
                      index_dir=tmp_path / "idx", **stubs(gen))


def test_citing_code_shown_by_open_file_is_verified(tmp_path):
    result = _ask(tmp_path, ['<tool>open_file(path="src/util.py", lines="1-2")</tool>',
                             "ANSWER"])
    assert [c["tool"] for c in result.audit_log["tool_calls"]] == ["open_file"]
    assert result.citation_outcome == "F"


def test_same_citation_without_the_tool_is_flagged(tmp_path):
    result = _ask(tmp_path, ["ANSWER"])
    assert result.citation_outcome == "G"
