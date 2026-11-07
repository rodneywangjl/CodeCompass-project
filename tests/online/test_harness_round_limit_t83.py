"""T8.3 round limit enforcement tests (tests-first).

Contract under test (Spec AC-3.1, AC-3.9, FR-6; Plan D15; Article V.1 as of 1.3.0):
  - at most max_rounds tools run; a tool request after the last allowed
    result is not run: the harness appends harness.FINAL_MESSAGE and calls
    the generator once more; <tool> blocks in that reply are removed
  - generator calls = max_rounds + 2 (each tool round, the reply that
    still asks for a tool, the final call); round_limit_hit is True; the log has
    every tool round plus a final_call entry
  - only the first <tool> block in a response runs; the rest are logged
  - T19.4: each round asks for a different call (n varies), so every round runs a
    tool; a repeat is not run again and would not test the limit
"""

import pytest

from codecompass.online.agent import harness
from tests.online.harness_support import CHUNKS, FakeTools
from tests.support.stub_generator import TOOL_CALL_BLAME, TOOL_CALL_LOG, StubGenerator

FINAL = TOOL_CALL_LOG + "\nRetries come from MAX_RETRIES."


@pytest.mark.parametrize("limit", [3, 1, 5])
def test_limit_runs_that_many_tools_then_one_final_call(limit):
    distinct = [f'<tool>git_log(path="src/auth.py", n={n})</tool>' for n in range(1, limit + 2)]
    gen = StubGenerator(distinct + [FINAL])
    tools = FakeTools()
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=tools, max_rounds=limit)
    assert len(tools.calls) == limit
    assert len(gen.calls) == limit + 2 == run.generator_calls
    assert gen.calls[-1][-1] == {"role": "user", "content": harness.FINAL_MESSAGE}
    assert run.answer == "Retries come from MAX_RETRIES."
    assert run.round_limit_hit is True
    assert [r["round"] for r in run.rounds if "tool" in r] == list(range(limit))
    assert run.rounds[-1] == {"round": limit, "final_call": True, "ignored_calls": 1}


def test_zero_rounds_goes_straight_to_the_final_call():
    gen = StubGenerator([TOOL_CALL_LOG, "No tools needed."])
    tools = FakeTools()
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=tools, max_rounds=0)
    assert tools.calls == [] and len(gen.calls) == 2
    assert run.answer == "No tools needed." and run.round_limit_hit


def test_only_the_first_tool_block_runs():
    gen = StubGenerator([TOOL_CALL_BLAME + "\n" + TOOL_CALL_LOG, "Done."])
    tools = FakeTools()
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=tools, max_rounds=3)
    assert [c.tool for c in tools.calls] == ["git_blame"]
    assert run.rounds[0]["ignored_calls"] == 1
