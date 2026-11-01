"""T2.3 (Spec 004) the draft through the harness and ask(): tests first.

Contract under test (Spec 004 AC-2.3, AC-2.5, AC-2.6):
  run_agent(..., on_draft=None) and ask(..., on_draft=None)
  - on_draft(text) receives the model's text as it is written, round by round
  - text from a "<tool>" tag onwards is never forwarded, even when the tag arrives
    split across pieces; text before the tag is
  - the final answer-only call after the round limit is streamed like any answer
  - with on_draft=None no generator call is given a callback and every result, audit
    log field and citation outcome is the same as without the feature
  - ask() still prints nothing, and TimedGenerator forwards the callback and still times
"""

import pytest

import codecompass.online as online
from codecompass.online.agent.harness import run_agent
from codecompass.online.config import ModelProfile, ToolsConfig
from codecompass.online.logging import TimedGenerator, new_log
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.online.harness_support import ANSWER, CHUNKS, FakeTools
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import (
    MALFORMED_TOOL_CALL, TOOL_CALL_BLAME, TOOL_CALL_LOG, StubGenerator)

QUESTION = "Why does authenticate retry?"


def drafted(responses, *, max_rounds=3, piece_size=4):
    """Run the agent with a streaming stub; return (text shown as draft, generator, run)."""
    pieces = []
    gen = StubGenerator(responses, piece_size=piece_size)
    run = run_agent(gen, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=max_rounds,
                    on_draft=pieces.append)
    return "".join(pieces), gen, run


# --- the harness -------------------------------------------------------------------------


def test_an_answer_round_is_streamed_as_it_is_written():
    pieces = []
    gen = StubGenerator([ANSWER], piece_size=5)
    run_agent(gen, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3,
              on_draft=pieces.append)
    assert "".join(pieces) == ANSWER
    assert len(pieces) > 1  # as it is written, not all at once


def test_a_tool_request_is_not_shown_and_the_answer_after_it_is():
    shown, gen, run = drafted([TOOL_CALL_LOG, ANSWER])
    assert shown == ANSWER
    assert run.generator_calls == 2 and len(run.rounds) == 1  # the tool did run


def test_text_before_a_tool_tag_is_shown_and_the_tag_onwards_is_not():
    shown, _, _ = drafted(["Let me look at the history. " + TOOL_CALL_LOG, ANSWER])
    assert shown == "Let me look at the history. " + ANSWER


def test_a_tag_split_across_pieces_never_leaks():
    shown, _, _ = drafted([TOOL_CALL_LOG, TOOL_CALL_BLAME, ANSWER], piece_size=1)
    assert "<tool" not in shown and "git_log" not in shown
    assert shown == ANSWER


def test_text_that_only_looks_like_a_tag_is_shown_in_full():
    text = "Compare a <b and <to be done, then <tool"  # ends on a would-be tag
    shown, _, _ = drafted([text], piece_size=1)
    assert shown == text


def test_the_final_answer_only_call_after_the_round_limit_is_streamed():
    shown, gen, run = drafted([TOOL_CALL_LOG, TOOL_CALL_BLAME, ANSWER], max_rounds=1)
    assert run.round_limit_hit and shown == ANSWER


def test_a_malformed_tool_call_is_not_shown():
    shown, _, _ = drafted([MALFORMED_TOOL_CALL, ANSWER])
    assert shown == ANSWER


def test_without_on_draft_no_generator_call_gets_a_callback_and_the_run_is_the_same():
    plain_gen = StubGenerator([TOOL_CALL_LOG, ANSWER])
    plain = run_agent(plain_gen, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3)
    assert plain_gen.streamed == [False, False]
    _, _, with_draft = drafted([TOOL_CALL_LOG, ANSWER])
    assert (plain.answer, plain.rounds, plain.generator_calls) == (
        with_draft.answer, with_draft.rounds, with_draft.generator_calls)


# --- ask() -------------------------------------------------------------------------------


class StreamingCiting(CitingGenerator):
    """CitingGenerator that also streams the text it returns."""

    def generate(self, messages, *, on_text=None):
        text = super().generate(messages)
        for i in range(0, len(text), 6):
            if on_text:
                on_text(text[i:i + 6])
        return text


def ask(tmp_path, repo, on_draft=None, generator=None, mode="rag_tools"):
    kit = stubs(generator or StreamingCiting())
    return online.ask(repo.path, QUESTION, config=config(tmp_path, mode=mode),
                      index_dir=tmp_path / "idx", on_draft=on_draft, **kit)


def test_ask_streams_the_draft_and_still_returns_the_checked_answer(tmp_path, capsys):
    repo = build_history_repo(tmp_path / "repo")
    pieces = []
    result = ask(tmp_path, repo, on_draft=pieces.append)
    draft = "".join(pieces)
    assert draft.startswith("Login retries on timeout [1].")
    assert "Sources" in draft
    assert result.citation_outcome == "F" and [s.verified for s in result.sources] == [True]
    assert result.answer.startswith("Login retries on timeout [1].")
    assert capsys.readouterr().out == ""  # ask() prints nothing (AC-9.2)


def test_the_result_and_audit_log_are_the_same_with_and_without_a_draft(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    plain = ask(tmp_path, repo)
    drafted_result = ask(tmp_path, repo, on_draft=lambda text: None)
    assert (plain.answer, plain.citation_outcome, plain.stale_index) == (
        drafted_result.answer, drafted_result.citation_outcome, drafted_result.stale_index)
    assert plain.sources == drafted_result.sources
    a, b = plain.audit_log, drafted_result.audit_log
    assert set(a) == set(b) and set(a["timings"]) == set(b["timings"])
    for key in ("question", "retrieved", "tool_calls", "generator_calls", "citation",
                "round_limit_hit", "mode", "profile"):
        assert a.get(key) == b.get(key), key


def test_a_tool_round_in_ask_is_not_drafted(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    pieces = []
    result = ask(tmp_path, repo, on_draft=pieces.append,
                 generator=StreamingCiting(before=[TOOL_CALL_LOG]))
    assert "<tool" not in "".join(pieces)
    assert len(result.audit_log["tool_calls"]) == 1  # the tool ran


def test_the_no_retrieval_mode_streams_too(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    pieces = []
    gen = StubGenerator(["I could not find enough evidence."], piece_size=5)
    ask(tmp_path, repo, on_draft=pieces.append, generator=gen, mode="no_retrieval")
    assert "".join(pieces) == "I could not find enough evidence."
    assert len(pieces) > 1


def test_the_timing_wrapper_forwards_the_callback_and_still_times():
    log = new_log("q", profile_name="dev", profile=ModelProfile(model_id="m"),
                  mode="rag_tools", tools=ToolsConfig())
    inner = StubGenerator(["abcdefgh"], piece_size=3)
    seen = []
    timed = TimedGenerator(inner, log)
    assert timed.generate([{"role": "user", "content": "q"}], on_text=seen.append) == "abcdefgh"
    assert seen == ["abc", "def", "gh"] and "generation" in log["timings"]
    timed.generate([{"role": "user", "content": "q"}])
    assert inner.streamed == [True, False]  # no callback unless one was given


@pytest.mark.parametrize("responses", [[ANSWER], [TOOL_CALL_LOG, ANSWER]])
def test_the_citation_outcome_does_not_depend_on_streaming(responses):
    plain = StubGenerator(responses)
    run_agent(plain, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3)
    streamed = StubGenerator(responses)
    run_agent(streamed, QUESTION, CHUNKS, run_tool=FakeTools(), max_rounds=3,
              on_draft=lambda text: None)
    assert plain.calls == streamed.calls  # the model saw exactly the same messages
