"""T8.4 tool error handling tests (tests-first).

Contract under test (Spec AC-3.3, AC-3.4; Plan D6, D16):
  - a rejected or failed tool call is sent back as a <tool_result ... error="...">
    message and the model gets another round; nothing crashes
  - an exception raised by the tool runner becomes an error result too
"""

from codecompass.online.agent import harness
from codecompass.online.agent.tools import ToolOutput
from codecompass.online.config import ToolsConfig
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_BLAME, StubGenerator


def test_disallowed_tool_and_bad_args_come_back_as_errors(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    run_tool = harness.make_tool_runner(repo.path, repo.commits["wip"], ToolsConfig(),
                                        StubGenerator(["x"]).count_tokens)
    gen = StubGenerator(['<tool>cat(path="src/auth.py")</tool>',
                         '<tool>git_blame(path="../secret")</tool>', ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=run_tool, max_rounds=3)
    assert run.answer == ANSWER and len(gen.calls) == 3
    results = [m["content"] for m in gen.calls[2] if m["content"].startswith("<tool_result")]
    assert len(results) == 2
    assert all('error="' in r for r in results)
    assert "not allowed" in results[0] and "inside the repository" in results[1]
    assert [r["error"] for r in run.rounds] == [True, True]


def test_timeout_output_is_shown_and_the_loop_continues():
    timed_out = ToolOutput(text="error: git blame timed out after 30s", error=True)
    gen = StubGenerator([TOOL_CALL_BLAME, ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(timed_out),
                            max_rounds=3)
    assert run.answer == ANSWER
    assert "timed out after 30s" in gen.calls[1][-1]["content"]


def test_runner_exception_becomes_an_error_result():
    def broken(call):
        raise OSError("git not found")

    gen = StubGenerator([TOOL_CALL_BLAME, ANSWER])
    run = harness.run_agent(gen, "Why?", CHUNKS, run_tool=broken, max_rounds=3)
    assert run.answer == ANSWER
    assert 'error="' in gen.calls[1][-1]["content"]
    assert "git not found" in gen.calls[1][-1]["content"]
    assert run.rounds[0]["error"] is True
