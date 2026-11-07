"""T19.4 repeated tool calls are not run again (tests first, scripted stub generator).

Contract under test (Spec AC-3.1, AC-3.6; Article V.1, V.4; Plan D14):
  - a tool call with the same tool and arguments as an earlier round of the same
    question is not executed again (AgentRun.commits and .chunks are not doubled)
  - the model gets a short tool result saying the call was already run in round N
    and to use that earlier result, in the same <tool_result> wrapper
  - a call with different arguments still runs
  - the repeat is logged like other tool calls (cache_hit true, repeat_of N)
  - a repeat uses one round of max_verifier_rounds, so the loop stays bounded
"""

from codecompass.online.agent import harness
from codecompass.online.agent.tools import ToolOutput
from tests.online.harness_support import ANSWER, CHUNKS, RECORD, FakeTools
from tests.support.stub_generator import TOOL_CALL_LOG, StubGenerator

OTHER_LOG = '<tool>git_log(path="src/auth.py", n=5)</tool>'


def test_a_repeated_call_is_not_run_again():
    tools = FakeTools()
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_LOG, ANSWER])
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=tools, max_rounds=3)
    assert len(tools.calls) == 1
    assert run.answer == ANSWER and run.answer_round == 2
    assert run.commits == [RECORD]  # the repeat adds no commit records


def test_the_model_is_told_to_use_the_earlier_result():
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_LOG, ANSWER])
    harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    repeat = gen.calls[2][-1]  # the message sent before the third generator call
    assert repeat["role"] == "user"
    assert repeat["content"].startswith('<tool_result tool="git_log" path="src/auth.py" n="10">')
    assert repeat["content"].endswith("</tool_result>")
    assert "already run in round 0" in repeat["content"]
    assert "use the result from round 0" in repeat["content"]


def test_the_repeat_message_does_not_claim_no_history_was_found():
    empty = ToolOutput(text="", commits=())
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_LOG, ANSWER])
    harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=FakeTools(empty), max_rounds=3)
    assert "No commit history" not in gen.calls[2][-1]["content"]
    assert "already run in round 0" in gen.calls[2][-1]["content"]


def test_a_call_with_different_arguments_still_runs():
    tools = FakeTools()
    gen = StubGenerator([TOOL_CALL_LOG, OTHER_LOG, ANSWER])
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=tools, max_rounds=3)
    assert len(tools.calls) == 2 and tools.calls[1].args == {"path": "src/auth.py", "n": 5}
    assert [entry.get("repeat_of") for entry in run.rounds] == [None, None]


def test_the_repeat_is_in_the_audit_log_like_other_tool_calls():
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_LOG, ANSWER])
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    assert len(run.rounds) == 2
    assert run.rounds[1] == {"round": 1, "tool": "git_log",
                             "args": {"path": "src/auth.py", "n": 10},
                             "cache_hit": True, "error": False,
                             "result_summary": "already run in round 0",
                             "repeat_of": 0}


def test_a_repeat_uses_one_round_of_the_limit():
    # max_verifier_rounds=2: round 0 runs git_log, round 1 repeats it (a round used),
    # so the other call in round 2 never runs and the final answer-only call is made.
    tools = FakeTools()
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_LOG, OTHER_LOG, ANSWER])
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=tools, max_rounds=2)
    assert len(tools.calls) == 1
    assert run.round_limit_hit is True
    assert run.generator_calls == 4
