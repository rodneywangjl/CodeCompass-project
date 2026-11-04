"""T19.1 code-tool results reach the model (tests-first).

Bug (dev test 2 Nov 2026, B3, D2, D6, D11): every tool result without commits
was sent as "No commit history found for <path>", so the model never saw what
open_file and search_again returned, while their chunks were still citable.

Contract under test (Spec AC-3.5, AC-3.7, AC-4.1; Plan D16, D18; Article I.1,
V.3, V.5, VI.1):
  - open_file and search_again results reach the model as the tool's own text:
    code with its D3 header, an outline, or a hint
  - every chunk added as evidence (AgentRun.chunks) was in a message the model saw
  - a git_log or git_blame run with no commits still says
    "No commit history found for <path>" (plus the line range for blame)
  - the D16 wrapper and the user role are unchanged
"""

import pytest

from codecompass.online.agent import harness, tools
from codecompass.online.agent.tools import ToolOutput
from codecompass.online.context import RetrievedChunk, format_chunk, format_context
from tests.online.harness_support import ANSWER, CHUNKS, SHA, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

NO_HISTORY = "No commit history found"

OPEN_RANGE = '<tool>open_file(path="src/util.py", lines="1-2")</tool>'
OPEN_OUTLINE = '<tool>open_file(path="src/util.py")</tool>'
SEARCH = '<tool>search_again(query="retry backoff")</tool>'

UTIL = RetrievedChunk("u1", "def backoff(n):\n    return 2 ** n", "src/util.py", 1, 2,
                      "python", SHA)
CLIENT = RetrievedChunk("k1", "def call(client):\n    return client.get()",
                        "src/client.py", 4, 5, "python", SHA)


def _result_seen(call: str, output: ToolOutput) -> tuple[str, harness.AgentRun]:
    """Run one tool round; return the tool-result message the model received."""
    gen = StubGenerator([call, ANSWER])
    run = harness.run_agent(gen, "How does it back off?", CHUNKS,
                            run_tool=FakeTools(output), max_rounds=3)
    message = gen.calls[1][-1]
    assert message["role"] == "user"
    return message["content"], run


# --- open_file --------------------------------------------------------------------

def test_open_file_code_reaches_the_model():
    seen, _ = _result_seen(OPEN_RANGE, ToolOutput(text=format_chunk(UTIL), chunks=(UTIL,)))
    assert format_chunk(UTIL) in seen
    assert NO_HISTORY not in seen


def test_open_file_outline_reaches_the_model():
    outline = ("Outline of src/util.py (indexed at a1b2c3d):\n  backoff  lines 1-2\n"
               'Read code with open_file(path="src/util.py", lines="X-Y").')
    seen, _ = _result_seen(OPEN_OUTLINE, ToolOutput(text=outline))
    assert outline in seen
    assert NO_HISTORY not in seen


def test_open_file_hint_without_an_outline_reaches_the_model():
    hint = ("No outline available for src/util.py at a1b2c3d. Ask for a line range "
            'instead, e.g. open_file(path="src/util.py", lines="1-60").')
    seen, _ = _result_seen(OPEN_OUTLINE, ToolOutput(text=hint))
    assert hint in seen
    assert NO_HISTORY not in seen


def test_a_real_open_file_result_reaches_the_model(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    count = StubGenerator(["x"]).count_tokens

    def run_tool(call):
        return tools.open_file(repo.path, repo.commits["wip"], call.args["path"],
                               call.args["lines"], max_tokens=10_000,
                               count_tokens=count), False

    gen = StubGenerator(['<tool>open_file(path="src/auth.py", lines="6-12")</tool>', ANSWER])
    run = harness.run_agent(gen, "How does authenticate work?", CHUNKS,
                            run_tool=run_tool, max_rounds=3)
    seen = gen.calls[1][-1]["content"]
    assert "def authenticate(client, user, password):" in seen
    assert format_chunk(run.chunks[0]) in seen
    assert NO_HISTORY not in seen


# --- search_again -----------------------------------------------------------------

def test_search_again_chunks_reach_the_model():
    found = (UTIL, CLIENT)
    seen, _ = _result_seen(SEARCH, ToolOutput(text=format_context(list(found)),
                                              chunks=found))
    for chunk in found:
        assert format_chunk(chunk) in seen
    assert NO_HISTORY not in seen


@pytest.mark.parametrize("reply", [
    "Nothing new found for 'retry backoff': every match is already in the context above.",
    ("The best new match, src/util.py lines 1-400, is too large to show here. Read part "
     'of it with open_file(path="src/util.py", lines="1-400").'),
])
def test_search_again_replies_without_code_reach_the_model(reply):
    seen, _ = _result_seen(SEARCH, ToolOutput(text=reply))
    assert reply in seen
    assert NO_HISTORY not in seen


# --- evidence the model was shown (Article VI.1) ----------------------------------

@pytest.mark.parametrize("call, output", [
    (OPEN_RANGE, ToolOutput(text=format_chunk(UTIL), chunks=(UTIL,))),
    (SEARCH, ToolOutput(text=format_context([UTIL, CLIENT]), chunks=(UTIL, CLIENT))),
])
def test_every_citable_tool_chunk_was_shown_to_the_model(call, output):
    gen = StubGenerator([call, ANSWER])
    run = harness.run_agent(gen, "How does it back off?", CHUNKS,
                            run_tool=FakeTools(output), max_rounds=3)
    shown = "\n".join(m["content"] for m in gen.calls[-1])
    assert run.chunks
    for chunk in run.chunks:
        assert format_chunk(chunk) in shown


# --- git tools keep the Article V.5 message ----------------------------------------

def test_git_log_without_commits_still_says_no_history():
    seen, _ = _result_seen('<tool>git_log(path="src/util.py", n=5)</tool>',
                           ToolOutput(text="no commits found for src/util.py"))
    assert "No commit history found for src/util.py" in seen


def test_git_blame_without_commits_still_says_no_history_with_the_range():
    seen, _ = _result_seen('<tool>git_blame(path="src/util.py", lines="1-2")</tool>',
                           ToolOutput(text=""))
    assert "No commit history found for src/util.py lines 1-2" in seen


# --- D16 wrapper ----------------------------------------------------------------------

def test_code_tool_result_keeps_the_d16_wrapper():
    seen, _ = _result_seen(OPEN_RANGE, ToolOutput(text=format_chunk(UTIL), chunks=(UTIL,)))
    assert seen.startswith('<tool_result tool="open_file" path="src/util.py" lines="1-2">')
    assert seen.endswith("</tool_result>")
