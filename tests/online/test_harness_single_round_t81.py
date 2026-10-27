"""T8.1 single-round answer tests (tests-first).

Contract under test (Spec AC-3.1 no-tool path; Plan §1, D15):
  - agent.harness.run_agent(generator, question, chunks, *, run_tool,
    max_rounds, tools_enabled=True) -> AgentRun
  - a direct answer: one generate call, answer returned, answer_round 0,
    no tool rounds, round_limit_hit False
"""

from codecompass.online.agent import harness
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.stub_generator import StubGenerator


def test_direct_answer_takes_one_call():
    gen, tools = StubGenerator([ANSWER]), FakeTools()
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=tools, max_rounds=3)
    assert run.answer == ANSWER
    assert len(gen.calls) == 1 and run.generator_calls == 1
    assert run.answer_round == 0
    assert run.rounds == [] and tools.calls == []
    assert run.round_limit_hit is False
    assert run.commits == []
