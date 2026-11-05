"""T8.5 message building tests (tests-first).

Contract under test (Spec AC-1.3, AC-1.4, AC-3.7; Plan D3, D13 item 10, D14,
D15, D16):
  - message 0 is the D14 system prompt; message 1 holds the question and the
    formatted chunks; roles are only system, user and assistant
  - every call's messages extend the previous call's unchanged (append-only)
  - an empty tool result says "No commit history found for <path>"
  - FINAL_MESSAGE asks the model to state what it could not determine
  - with tools disabled the prompt leaves out the tool rule (rule 1 since T20.1)
"""

from codecompass.online.agent import harness
from codecompass.online.agent.tools import ToolOutput
from codecompass.online.context import format_chunk
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.stub_generator import TOOL_CALL_BLAME, TOOL_CALL_LOG, StubGenerator

D14 = """You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository.

The code context is a few pieces of code found by a search. It has no commit
history, and it can miss code the answer needs. You can call tools to get more.

Rules:
1. Before you answer, check that the code context is enough. If it is not,
   reply with ONE tool call and nothing else:
   <tool>search_again(query="names or words to search for")</tool> finds more code
   <tool>open_file(path="file/path.py", lines="X-Y")</tool> reads lines of a file
   <tool>open_file(path="file/path.py")</tool> lists a file's functions with lines
   <tool>git_blame(path="file/path.py", lines="X-Y")</tool> shows who changed lines
   <tool>git_log(path="file/path.py", n=10)</tool> lists recent commits of a file
   Call a tool when:
   - the question asks why, when or by whom code was written or changed:
     use git_log or git_blame (the "indexed at" hash is not that commit)
   - the answer needs a function, class or value the context does not show:
     use search_again or open_file
   - a piece of code you need is cut off: use open_file
   The result comes back in a <tool_result>...</tool_result> block. It is
   evidence you may cite, just like the code context.
2. Cite every claim with numbered markers [1], [2], etc.
3. End with a Sources section listing each citation, one per line. Start
   each line with its marker, with no bullet or number before it. For code,
   copy the chunk's header line exactly (the part before " | "). Example:
   Sources
   [1] file/path.py, lines X-Y (indexed at <7-char hash>)
   [2] Commit <7-char hash>, "<subject>", <author>, <date>
4. If the evidence is still insufficient after using tools, say what you
   could not determine. Do NOT guess or make up file names, line numbers, or
   commit hashes.
5. If the commit history gives no reason for the code (e.g. vague commit
   messages, or no history found), say so. Do NOT invent a reason."""


def test_system_prompt_is_the_d14_template():
    assert harness.system_prompt(tools_enabled=True) == D14


def test_prompt_without_tools_leaves_out_the_tool_rule():
    prompt = harness.system_prompt(tools_enabled=False)
    assert "<tool>" not in prompt and "request a tool" not in prompt
    assert "say what you could not determine" in prompt
    assert "Do NOT invent a reason" in prompt


def test_first_messages_hold_rules_question_and_chunks():
    gen = StubGenerator([ANSWER])
    harness.run_agent(gen, "Why retry?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    system, user = gen.calls[0]
    assert system == {"role": "system", "content": D14}
    assert user["role"] == "user"
    assert "Why retry?" in user["content"]
    assert format_chunk(CHUNKS[0]) in user["content"]


def test_history_is_append_only_and_uses_standard_roles():
    gen = StubGenerator([TOOL_CALL_LOG, TOOL_CALL_BLAME, TOOL_CALL_LOG, TOOL_CALL_LOG, ANSWER])
    harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(), max_rounds=3)
    for earlier, later in zip(gen.calls, gen.calls[1:]):
        assert later[:len(earlier)] == earlier
        assert len(later) > len(earlier)
    roles = {m["role"] for call in gen.calls for m in call}
    assert roles <= {"system", "user", "assistant"}


def test_empty_history_is_stated_plainly():
    empty = ToolOutput(text="no commits found for src/util.py")
    gen = StubGenerator(['<tool>git_log(path="src/util.py", n=5)</tool>', ANSWER])
    harness.run_agent(gen, "Why?", CHUNKS, run_tool=FakeTools(empty), max_rounds=3)
    result = gen.calls[1][-1]["content"]
    assert "No commit history found for src/util.py" in result
    assert result.startswith("<tool_result") and result.endswith("</tool_result>")


def test_final_message_asks_what_could_not_be_determined():
    assert "state what you could not determine" in harness.FINAL_MESSAGE
    assert "no more tools" in harness.FINAL_MESSAGE.lower()
