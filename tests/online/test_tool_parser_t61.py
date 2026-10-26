"""T6.1 tool-call parser tests (tests-first).

Contract under test (Spec AC-3.8, FR-13; Plan D5, D15):
  - tool_parser.parse_tool_calls(text) -> list[ToolCall], well-formed calls in
    order; the harness executes only the first (one tool per round)
  - format: <tool>name(key="value", n=10)</tool>; keyword arguments with
    literal values only
  - no <tool> block, or only malformed ones -> [] (treated as a final answer)
  - parsing never evaluates code
  - tool_parser.strip_tool_blocks(text) removes every <tool>...</tool> block
    and any unclosed <tool> tail (used for the forced final answer)
"""

import pytest

from codecompass.online.agent import tool_parser as tp
from codecompass.online.models import ToolCall


def test_parses_git_blame():
    calls = tp.parse_tool_calls(
        'Let me check.\n<tool>git_blame(path="src/auth.py", lines="42-58")</tool>')
    assert calls == [ToolCall(tool="git_blame",
                              args={"path": "src/auth.py", "lines": "42-58"})]


def test_parses_git_log_with_integer():
    assert tp.parse_tool_calls('<tool>git_log(path="src/auth.py", n=10)</tool>') == [
        ToolCall(tool="git_log", args={"path": "src/auth.py", "n": 10})]


def test_single_quotes_and_whitespace():
    assert tp.parse_tool_calls("<tool> git_log( path = 'a.py' ) </tool>") == [
        ToolCall(tool="git_log", args={"path": "a.py"})]


def test_no_tool_block_is_final_answer():
    assert tp.parse_tool_calls("The answer is 42 [1].\n\nSources\n[1] a.py") == []


@pytest.mark.parametrize("text", [
    '<tool>git_blame(path="a.py"',
    '<tool>git_blame(path="a.py")',
    "<tool>not python at all</tool>",
    '<tool>git_blame("a.py")</tool>',
    '<tool>git_blame(path=open("x"))</tool>',
    '<tool>os.system(cmd="ls")</tool>',
    "<tool>git_blame(**{'path': 'a.py'})</tool>",
    "<tool></tool>",
])
def test_malformed_blocks_are_ignored(text):
    assert tp.parse_tool_calls(text) == []


def test_never_evaluates_code(monkeypatch):
    import builtins

    def boom(*a, **k):
        raise AssertionError("eval called")

    monkeypatch.setattr(builtins, "eval", boom)
    tp.parse_tool_calls('<tool>git_log(path=__import__("os").getcwd())</tool>')


def test_multiple_blocks_returned_in_order():
    calls = tp.parse_tool_calls(
        '<tool>git_log(path="a.py")</tool> and <tool>git_blame(path="b.py")</tool>')
    assert [c.tool for c in calls] == ["git_log", "git_blame"]


def test_unknown_tool_names_still_parse():
    assert tp.parse_tool_calls('<tool>git_diff(path="a.py")</tool>')[0].tool == "git_diff"


def test_strip_tool_blocks():
    text = 'Answer [1].\n<tool>git_log(path="a.py")</tool>\nSources\n[1] x\n<tool>git_blame('
    assert tp.strip_tool_blocks(text) == "Answer [1].\n\nSources\n[1] x"
