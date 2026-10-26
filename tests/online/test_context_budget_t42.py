"""T4.2 context budgeting tests (tests-first).

Contract under test (Spec AC-2.6, AC-5.7; Plan D4; Article V.1 as of 1.3.0):
  - context.chunk_budget(profile, tools, prefix_tokens) =
      context_window - max_tokens - prefix_tokens
      - max_verifier_rounds * max_tool_output_tokens
  - context.fit_chunks(chunks, budget, count_tokens) keeps chunks in order
    while each formatted block fits; the first that does not fit ends it
  - context.check_round_reserve(profile, tools, system_tokens) raises a
    ValueError naming Article V.1 when the tool reserve leaves no room
  - tools.max_tool_output_tokens defaults to 768 (Plan §7)
"""

from pathlib import Path

import pytest

from codecompass.online import context
from codecompass.online.config import ModelProfile, ToolsConfig
from codecompass.online.context import RetrievedChunk, format_chunk
from tests.support.stub_generator import StubGenerator

COUNT = StubGenerator(["x"]).count_tokens


def _chunk(cid, words):
    return RetrievedChunk(cid, " ".join(["w"] * words), f"src/{cid}.py", 1, 2,
                          "python", "a" * 40)


CHUNKS = [_chunk("a", 10), _chunk("b", 10), _chunk("c", 10)]
BLOCK = COUNT(format_chunk(CHUNKS[0]))


def test_default_tool_output_cap():
    assert ToolsConfig().max_tool_output_tokens == 768


def test_budget_reserves_answer_prefix_and_tool_rounds():
    profile = ModelProfile(model_id="m", context_window=8192, max_tokens=2048)
    tools = ToolsConfig(max_verifier_rounds=3, max_tool_output_tokens=768)
    assert context.chunk_budget(profile, tools, prefix_tokens=100) == 8192 - 2048 - 100 - 3 * 768


def test_chunks_added_in_order_until_the_budget_is_exceeded():
    assert context.fit_chunks(CHUNKS, 2 * BLOCK, COUNT) == CHUNKS[:2]
    assert context.fit_chunks(CHUNKS, 3 * BLOCK, COUNT) == CHUNKS


def test_tiny_or_negative_budget_gives_no_chunks():
    assert context.fit_chunks(CHUNKS, BLOCK - 1, COUNT) == []
    assert context.fit_chunks(CHUNKS, -5, COUNT) == []


def test_profiles_differing_only_in_window_fit_different_counts():
    tools = ToolsConfig(max_verifier_rounds=0)
    small = ModelProfile(model_id="m", context_window=2 * BLOCK + 10, max_tokens=10)
    large = ModelProfile(model_id="m", context_window=3 * BLOCK + 10, max_tokens=10)
    fit = [len(context.fit_chunks(CHUNKS, context.chunk_budget(p, tools, 0), COUNT))
           for p in (small, large)]
    assert fit == [2, 3]


def test_round_reserve_that_leaves_no_room_fails_loudly():
    profile = ModelProfile(model_id="m", context_window=4096, max_tokens=2048)
    context.check_round_reserve(profile, ToolsConfig(), system_tokens=200)
    with pytest.raises(ValueError, match="Article V.1"):
        context.check_round_reserve(
            profile, ToolsConfig(max_verifier_rounds=10), system_tokens=200)


def test_context_module_names_no_model():
    source = (Path(context.__file__)).read_text().lower()
    for name in ("qwen", "14b", "32b", "jina", "bge"):
        assert name not in source
