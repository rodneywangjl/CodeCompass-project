"""T8.2 multi-round tool loop tests (tests-first).

Contract under test (Spec AC-3.1, AC-3.5, AC-3.6; Plan D8, D15, D16):
  - a tool request runs the tool, appends the model's request as an
    assistant message and the result as a <tool_result> user message, then
    calls the generator again
  - each tool round is logged: round, tool, args, cache_hit, error
  - the tool's commit records become citable evidence (AgentRun.commits)
  - agent.harness.make_tool_runner(repo, commit, settings, count_tokens)
    wires execute + per-query cache + output cap; a repeated call is a hit
"""

from codecompass.online.agent import harness
from codecompass.online.config import ToolsConfig
from codecompass.online.models import ToolCall
from tests.online.harness_support import ANSWER, CHUNKS, RECORD, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_LOG, StubGenerator


def test_tool_round_then_answer():
    gen, tools = StubGenerator([TOOL_CALL_LOG, ANSWER]), FakeTools()
    run = harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=tools, max_rounds=3)
    assert run.answer == ANSWER and run.answer_round == 1
    assert len(gen.calls) == 2
    assert tools.calls == [ToolCall(tool="git_log", args={"path": "src/auth.py", "n": 10})]
    assert run.rounds == [{"round": 0, "tool": "git_log",
                           "args": {"path": "src/auth.py", "n": 10},
                           "cache_hit": False, "error": False,
                           "result_summary": "0173e4e ..."}]
    assert run.commits == [RECORD]


def test_request_and_result_are_appended_in_order():
    gen = StubGenerator([TOOL_CALL_LOG, ANSWER])
    harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    second = gen.calls[1]
    assert second[2] == {"role": "assistant", "content": TOOL_CALL_LOG}
    assert second[3]["role"] == "user"
    assert second[3]["content"].startswith('<tool_result tool="git_log" path="src/auth.py" n="10">')
    assert second[3]["content"].endswith("</tool_result>")
    assert "0173e4e ..." in second[3]["content"]


def test_tool_runner_caches_repeated_calls(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    run_tool = harness.make_tool_runner(repo.path, repo.commits["wip"], ToolsConfig(),
                                        StubGenerator(["x"]).count_tokens)
    call = ToolCall(tool="git_log", args={"path": "src/auth.py", "n": 2})
    first, hit1 = run_tool(call)
    second, hit2 = run_tool(call)
    assert (hit1, hit2) == (False, True)
    assert first == second and len(first.commits) == 2
