"""T19.6 citation example: tests first (Spec 002 AC-1.1; Articles VI.1, VI.4, VII.3, VIII.4).

Contract under test:
  - [prompt] citation_example defaults to false. With false (or no flag), the system
    prompt is byte-for-byte today's prompt, with and without tools.
  - With true, the prompt is today's prompt plus ONE short example answer: [N] markers in
    the body and a Sources section in the format citation/parser.py reads. The example
    names only an invented file, so it cannot be mistaken for evidence from a repo.
  - The example parses with citation/parser.py into the entries it shows.
  - The flag loads, layers and rejects a non-boolean, and ask() logs it.
Stub embedder, re-ranker and generator only; no network, GPU or model.
"""

import dataclasses
from pathlib import Path

import pytest

import codecompass.online as online
from codecompass.online import config as online_config
from codecompass.online.agent import harness
from codecompass.online.citation.parser import body_markers, parse_answer
from codecompass.online.config import load_online_config, load_online_config_layers
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo

REPO_ROOT = Path(__file__).resolve().parents[2]

# Today's prompts, captured on main before T19.6. The flag-off prompts must equal these.
PROMPT_WITHOUT_TOOLS = 'You are CodeCompass, a code Q&A assistant. Answer the developer\'s question\nusing ONLY the code context provided below. Do not use your training knowledge\nabout the repository.\n\nRules:\n1. Cite every claim with numbered markers [1], [2], etc.\n2. End with a Sources section listing each citation, one per line. Start\n   each line with its marker, with no bullet or number before it. For code,\n   copy the chunk\'s header line exactly (the part before " | "). Example:\n   Sources\n   [1] file/path.py, lines X-Y (indexed at <7-char hash>)\n   [2] Commit <7-char hash>, "<subject>", <author>, <date>\n3. If the evidence is insufficient, say what you could not determine.\n   Do NOT guess or make up file names, line numbers, or commit hashes.\n4. If the commit history gives no reason for the code (e.g. vague commit\n   messages, or no history found), say so. Do NOT invent a reason.'
PROMPT_WITH_TOOLS = 'You are CodeCompass, a code Q&A assistant. Answer the developer\'s question\nusing ONLY the code context provided below. Do not use your training knowledge\nabout the repository.\n\nThe code context is a few pieces of code found by a search. It has no commit\nhistory, and it can miss code the answer needs. You can call tools to get more.\n\nRules:\n1. Before you answer, check that the code context is enough. If it is not,\n   reply with ONE tool call and nothing else:\n   <tool>search_again(query="names or words to search for")</tool> finds more code\n   <tool>open_file(path="file/path.py", lines="X-Y")</tool> reads lines of a file\n   <tool>open_file(path="file/path.py")</tool> lists a file\'s functions with lines\n   <tool>git_blame(path="file/path.py", lines="X-Y")</tool> shows who changed lines\n   <tool>git_log(path="file/path.py", n=10)</tool> lists recent commits of a file\n   Call a tool when:\n   - the question asks why, when or by whom code was written or changed:\n     use git_log or git_blame (the "indexed at" hash is not that commit)\n   - the answer needs a function, class or value the context does not show:\n     use search_again or open_file\n   - a piece of code you need is cut off: use open_file\n   The result comes back in a <tool_result>...</tool_result> block. It is\n   evidence you may cite, just like the code context.\n2. Cite every claim with numbered markers [1], [2], etc.\n3. End with a Sources section listing each citation, one per line. Start\n   each line with its marker, with no bullet or number before it. For code,\n   copy the chunk\'s header line exactly (the part before " | "). Example:\n   Sources\n   [1] file/path.py, lines X-Y (indexed at <7-char hash>)\n   [2] Commit <7-char hash>, "<subject>", <author>, <date>\n4. If the evidence is still insufficient after using tools, say what you\n   could not determine. Do NOT guess or make up file names, line numbers, or\n   commit hashes.\n5. If the commit history gives no reason for the code (e.g. vague commit\n   messages, or no history found), say so. Do NOT invent a reason.'

LOADERS = [load_online_config, lambda path: load_online_config_layers([path])]


def write(path, text):
    path.write_text(text)
    return path


def _baseline(tools):
    return PROMPT_WITH_TOOLS if tools else PROMPT_WITHOUT_TOOLS


# --- the prompt (Article VII.3) ---------------------------------------------------------------


@pytest.mark.parametrize("tools", [False, True])
def test_the_default_prompt_is_today_s_prompt(tools):
    assert harness.system_prompt(tools_enabled=tools) == _baseline(tools)


@pytest.mark.parametrize("tools", [False, True])
def test_flag_off_gives_today_s_prompt_byte_for_byte(tools):
    prompt = harness.system_prompt(tools_enabled=tools, citation_example=False)
    assert prompt == _baseline(tools)


@pytest.mark.parametrize("tools", [False, True])
def test_flag_on_adds_the_example_and_nothing_else(tools):
    prompt = harness.system_prompt(tools_enabled=tools, citation_example=True)
    assert prompt == f"{_baseline(tools)}\n\n{harness.CITATION_EXAMPLE_BLOCK}"


def test_the_example_is_one_short_answer_with_markers_and_sources():
    answer = harness.CITATION_EXAMPLE_ANSWER
    assert "Sources" in answer.splitlines()
    assert "[1]" in answer and "[2]" in answer
    assert len(answer.split()) <= 80


def test_the_example_parses_into_the_entries_it_shows():
    parsed = parse_answer(harness.CITATION_EXAMPLE_ANSWER)
    assert parsed.has_sources
    assert body_markers(parsed.body) == {1, 2}
    code, commit = parsed.sources
    assert (code.kind, code.marker) == ("code", 1)
    assert (code.path, code.start_line, code.end_line, code.commit) == (
        "example/client.py", 10, 24, "1a2b3c4")
    assert (commit.kind, commit.marker) == ("commit", 2)
    assert (commit.commit, commit.subject, commit.author, commit.date) == (
        "5d6e7f8", "retry on upstream timeout", "Sam Lee", "2025-01-10")
    assert all(entry.kind != "invalid" for entry in parsed.sources)


def test_the_example_names_no_file_in_this_repository():
    parsed = parse_answer(harness.CITATION_EXAMPLE_ANSWER)
    for entry in parsed.sources:
        if entry.kind == "code":
            assert entry.path.startswith("example/")
            assert not (REPO_ROOT / entry.path).exists()


# --- the setting (Article VIII.1, VIII.4) -----------------------------------------------------


def test_the_default_is_off():
    assert online_config.PromptConfig().citation_example is False
    assert load_online_config(None).prompt.citation_example is False


@pytest.mark.parametrize("loader", LOADERS)
def test_the_flag_loads_from_the_file(tmp_path, loader):
    path = write(tmp_path / "codecompass.toml", "[prompt]\ncitation_example = true\n")
    assert loader(path).prompt.citation_example is True


def test_the_flag_layers_like_other_config(tmp_path):
    base = write(tmp_path / "base.toml", "[prompt]\ncitation_example = true\n")
    override = write(tmp_path / "override.toml", "[prompt]\ncitation_example = false\n")
    assert load_online_config_layers([base, override]).prompt.citation_example is False
    assert load_online_config_layers([override, base]).prompt.citation_example is True
    assert load_online_config_layers([base]).prompt.citation_example is True


@pytest.mark.parametrize("loader", LOADERS)
@pytest.mark.parametrize("value", ['"yes"', '"false"', "1", "0"])
def test_a_non_boolean_is_rejected(tmp_path, loader, value):
    path = write(tmp_path / "codecompass.toml", f"[prompt]\ncitation_example = {value}\n")
    with pytest.raises(ValueError, match="prompt.citation_example must be a bool"):
        loader(path)


def test_the_dataclass_rejects_a_non_boolean_too():
    with pytest.raises(ValueError, match="prompt.citation_example must be a bool"):
        online_config.PromptConfig(citation_example=1)


# --- ask(): the prompt sent and the audit log (Article V.4, VII.3) ----------------------------


@pytest.mark.parametrize("flag", [False, True])
def test_ask_sends_the_prompt_for_the_flag_and_logs_it(tmp_path, flag):
    repo = build_history_repo(tmp_path / "repo")
    gen = CitingGenerator()
    cfg = dataclasses.replace(config(tmp_path), prompt=online_config.PromptConfig(
        citation_example=flag))
    result = online.ask(repo.path, "Why does authenticate retry?", config=cfg,
                        index_dir=tmp_path / "idx", **stubs(gen))
    sent = gen.calls[0][0]
    assert sent["role"] == "system"
    assert sent["content"] == harness.system_prompt(tools_enabled=True, citation_example=flag)
    assert result.audit_log["prompt"]["citation_example"] is flag
