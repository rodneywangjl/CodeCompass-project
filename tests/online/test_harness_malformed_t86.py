"""T8.6 malformed tool-call retry tests (tests-first).

Contract under test (v2 architecture E6 "invalid / malformed -> E3"; Article V.1):
  - tool_parser.malformed_blocks(text) -> the raw text of every <tool> block that
    parse_tool_calls() could not read (bad syntax, or an unclosed tail)
  - a malformed call is not treated as the final answer: the model gets a
    <tool_result error="..."> message showing the correct format, and tries again
  - a malformed attempt uses one round, so the loop stays bounded at
    max_verifier_rounds + 2 generator calls
  - with tools disabled (rag / no_retrieval modes) nothing changes: blocks are
    stripped and the reply is the answer
"""

import pytest

from codecompass.online.agent import harness
from codecompass.online.agent import tool_parser as tp
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.stub_generator import MALFORMED_TOOL_CALL, TOOL_CALL_BLAME, StubGenerator

BAD_SYNTAX = 'Let me check the history.\n<tool>git_blame("src/auth.py", "1-12")</tool>'


# --- parser: finding malformed blocks -------------------------------------------

@pytest.mark.parametrize("text", [
    '<tool>git_blame("a.py")</tool>',
    "<tool>not python at all</tool>",
    "<tool></tool>",
    '<tool>git_blame(path="a.py"',          # unclosed tail (e.g. cut off by max_tokens)
])
def test_malformed_blocks_are_found(text):
    assert len(tp.malformed_blocks(text)) == 1


def test_well_formed_call_and_plain_answer_have_no_malformed_blocks():
    assert tp.malformed_blocks(TOOL_CALL_BLAME) == []
    assert tp.malformed_blocks(ANSWER) == []


# --- harness: retrying ---------------------------------------------------------

@pytest.mark.parametrize("bad", [BAD_SYNTAX, MALFORMED_TOOL_CALL])
def test_malformed_call_gets_an_error_and_another_round(bad):
    tools = FakeTools()
    gen = StubGenerator([bad, TOOL_CALL_BLAME, ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=tools, max_rounds=3)
    assert run.answer == ANSWER
    assert len(gen.calls) == 3
    assert len(tools.calls) == 1                      # only the valid call ran
    retry = gen.calls[1]
    assert retry[-2] == {"role": "assistant", "content": bad}
    feedback = retry[-1]
    assert feedback["role"] == "user"
    assert feedback["content"].startswith("<tool_result")
    assert 'error="' in feedback["content"]
    assert "could not be read" in feedback["content"]
    assert 'git_blame(path="' in feedback["content"]   # shows the correct format


def test_malformed_attempt_is_logged_as_a_round():
    gen = StubGenerator([BAD_SYNTAX, ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    assert run.rounds[0]["round"] == 0
    assert run.rounds[0]["malformed"] is True
    assert run.rounds[0]["error"] is True
    assert run.rounds[0]["tool"] is None
    assert run.answer_round == 1


def test_malformed_attempt_uses_a_round():
    tools = FakeTools()
    gen = StubGenerator([BAD_SYNTAX, TOOL_CALL_BLAME, ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=tools, max_rounds=1)
    assert tools.calls == []                          # the one round went on the bad call
    assert run.round_limit_hit is True
    assert len(gen.calls) == 3
    assert gen.calls[2][-1]["content"] == harness.FINAL_MESSAGE
    assert run.answer == ANSWER


def test_always_malformed_stays_bounded():
    gen = StubGenerator([BAD_SYNTAX])                 # repeats forever
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    assert len(gen.calls) == 5                        # max_verifier_rounds + 2
    assert run.round_limit_hit is True
    assert "<tool>" not in run.answer


def test_tools_disabled_still_strips_and_answers():
    gen = StubGenerator(["It retries [1]. " + BAD_SYNTAX])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(), max_rounds=3,
                            tools_enabled=False)
    assert len(gen.calls) == 1
    assert "<tool>" not in run.answer
