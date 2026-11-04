"""T20.1 tool-use prompt tests (tests-first).

Contract under test (Spec AC-3.1, AC-3.7, AC-3.8; Plan D3, D4, D13 item 10,
D14, D17; Article I.2, V.1, V.5, VII.3):
  - with tools on, the system prompt puts the tool decision first, says the
    code context has no commit history, names when each tool is needed, and
    applies the insufficient-evidence rule only after tools
  - with tools off, the system prompt is unchanged (configuration (b) stays put)
  - with tools on, the first user message ends with TOOL_CHECK after the code
    context; with tools off it is unchanged
  - ask() counts the tool check in the D4 prefix
  - (model) a real generator calls a git tool for a why question
"""

import dataclasses

import pytest

import codecompass.online as online
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.agent import harness
from codecompass.online.context import format_context
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.online.model_support import real_config, real_generator
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

NO_TOOLS = """You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository.

Rules:
1. Cite every claim with numbered markers [1], [2], etc.
2. End with a Sources section listing each citation, one per line. Start
   each line with its marker, with no bullet or number before it. For code,
   copy the chunk's header line exactly (the part before " | "). Example:
   Sources
   [1] file/path.py, lines X-Y (indexed at <7-char hash>)
   [2] Commit <7-char hash>, "<subject>", <author>, <date>
3. If the evidence is insufficient, say what you could not determine.
   Do NOT guess or make up file names, line numbers, or commit hashes.
4. If the commit history gives no reason for the code (e.g. vague commit
   messages, or no history found), say so. Do NOT invent a reason."""

TOOL_CHECK = """Before you answer: if the code context above does not show everything the
answer needs (for a why, when or who question: the commit history), reply
with only one <tool> call instead."""

QUESTION = "Why does authenticate retry?"


def _rules(prompt: str) -> list[str]:
    """The numbered rules of a system prompt, each with its indented lines."""
    body = prompt.split("Rules:\n", 1)[1]
    rules: list[str] = []
    for line in body.splitlines():
        if line[:1].isdigit():
            rules.append(line)
        else:
            rules[-1] += "\n" + line
    return rules


# --- system prompt, tools on ---------------------------------------------------

def test_the_tool_rule_comes_first():
    first = _rules(harness.system_prompt(tools_enabled=True))[0]
    assert first.startswith("1. Before you answer, check that the code context is enough.")
    assert '<tool>search_again(query="' in first


def test_the_tool_rule_comes_before_the_citation_rules():
    prompt = harness.system_prompt(tools_enabled=True)
    assert prompt.index("<tool>") < prompt.index("Cite every claim")
    assert prompt.index("<tool>") < prompt.index("End with a Sources section")


def test_the_prompt_says_the_code_context_has_no_commit_history():
    prompt = harness.system_prompt(tools_enabled=True)
    intro = " ".join(prompt.split("Rules:", 1)[0].split())
    assert "It has no commit history" in intro
    assert "You can call tools to get more." in intro


@pytest.mark.parametrize("cue, tools", [
    ("the question asks why, when or by whom code was written or changed",
     "use git_log or git_blame"),
    ("the answer needs a function, class or value the context does not show",
     "use search_again or open_file"),
    ("a piece of code you need is cut off", "use open_file"),
])
def test_the_prompt_names_when_each_tool_is_needed(cue, tools):
    flat = " ".join(harness.system_prompt(tools_enabled=True).split())
    at = flat.index(cue)
    assert tools in flat[at:at + len(cue) + 80]


def test_a_tool_reply_holds_the_tool_call_and_nothing_else():
    first = " ".join(_rules(harness.system_prompt(tools_enabled=True))[0].split())
    assert "reply with ONE tool call and nothing else" in first


def test_the_insufficient_evidence_rule_applies_after_tools():
    prompt = harness.system_prompt(tools_enabled=True)
    rule = next(r for r in _rules(prompt) if "could not determine" in r)
    assert "still insufficient after using tools" in " ".join(rule.split())
    assert prompt.index("<tool>") < prompt.index("could not determine")


def test_the_indexed_at_hash_is_not_offered_as_the_commit_that_explains_code():
    flat = " ".join(harness.system_prompt(tools_enabled=True).split())
    assert '(the "indexed at" hash is not that commit)' in flat


def test_every_rule_still_holds_with_tools_on():
    prompt = harness.system_prompt(tools_enabled=True)
    for phrase in ("Cite every claim with numbered markers [1], [2], etc.",
                   "copy the chunk's header line exactly",
                   "Do NOT guess or make up file names, line numbers, or",
                   "Do NOT invent a reason.",
                   "evidence you may cite, just like the code context."):
        assert phrase in prompt
    assert [r[:2] for r in _rules(prompt)] == ["1.", "2.", "3.", "4.", "5."]


# --- system prompt, tools off (D17, Article VII.3) ------------------------------

def test_the_prompt_without_tools_is_unchanged():
    assert harness.system_prompt(tools_enabled=False) == NO_TOOLS


# --- tool check at the end of the first user message ----------------------------

def test_the_user_message_ends_with_the_tool_check_when_tools_are_on():
    message = harness.user_message(QUESTION, CHUNKS, tools_enabled=True)
    assert message.endswith("\n\n" + TOOL_CHECK)
    assert message.index(format_context(CHUNKS)) < message.index(TOOL_CHECK)


def test_the_user_message_without_tools_is_unchanged():
    old = f"Question: {QUESTION}\n\nCode context:\n\n{format_context(CHUNKS)}"
    assert harness.user_message(QUESTION, CHUNKS, tools_enabled=False) == old
    assert harness.user_message(QUESTION, CHUNKS) == old


def test_the_tool_check_follows_an_empty_context_too():
    message = harness.user_message(QUESTION, [], tools_enabled=True)
    assert "(none retrieved)" in message and message.endswith(TOOL_CHECK)


def test_run_agent_sends_the_tool_check_only_with_tools_on():
    on, off = StubGenerator([ANSWER]), StubGenerator([ANSWER])
    harness.run_agent(on, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3)
    harness.run_agent(off, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3,
                      tools_enabled=False)
    assert on.calls[0][1]["content"].endswith(TOOL_CHECK)
    assert TOOL_CHECK not in off.calls[0][1]["content"]


def test_the_tool_check_stays_in_place_across_rounds():
    gen = StubGenerator(['<tool>git_log(path="src/util.py", n=5)</tool>', ANSWER])
    harness.run_agent(gen, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3)
    assert gen.calls[1][:2] == gen.calls[0][:2]  # append-only (D13 item 10)
    assert sum(TOOL_CHECK in m["content"] for m in gen.calls[1]) == 1


# --- ask(): the tool check is budgeted (D4) -------------------------------------

class CountingGenerator(CitingGenerator):
    """CitingGenerator that records every text it is asked to count."""

    def __init__(self) -> None:
        super().__init__()
        self.counted: list[str] = []

    def count_tokens(self, text: str) -> int:
        self.counted.append(text)
        return super().count_tokens(text)


@pytest.mark.parametrize("mode, tools_on", [("rag_tools", True), ("rag", False)])
def test_ask_counts_the_tool_check_in_the_prefix(tmp_path, mode, tools_on):
    repo = build_history_repo(tmp_path / "repo")
    gen = CountingGenerator()
    online.ask(repo.path, QUESTION, config=config(tmp_path, mode=mode),
               index_dir=tmp_path / "idx", **stubs(gen))
    assert harness.user_message(QUESTION, [], tools_enabled=tools_on) in gen.counted
    assert gen.calls[0][1]["content"].endswith(TOOL_CHECK) is tools_on


# --- real model (local only) -----------------------------------------------------

@pytest.mark.model
def test_real_model_calls_a_git_tool_for_a_why_question(tmp_path):
    offline = dataclasses.replace(
        load_config(None), embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    cfg = real_config(tmp_path, offline=offline)
    gen = real_generator(cfg)
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, QUESTION, config=cfg, generator=gen,
                        reranker=StubReranker(), embedder=StubEmbedder(),
                        index_dir=tmp_path / "idx")
    print(result.answer)
    tools = [c["tool"] for c in result.audit_log["tool_calls"]]
    assert {"git_log", "git_blame"} & set(tools), f"no git tool called: {tools}"
