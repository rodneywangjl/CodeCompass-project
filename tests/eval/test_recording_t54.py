"""T5.4 recording generator tests (tests-first).

Contract under test (Spec AC-8.2, §13 C8; Plan 003 §3.4):
  - codecompass.eval.recording.RecordingGenerator(inner) implements
    generate(messages, *, on_text=None) and count_tokens(text) by passing them to inner;
    on_text is passed only when it is given (the harness calls generate(messages) too)
  - .calls is a list of {"messages": <deep copy of the messages>, "output": <text>}, in order
  - ask(..., generator=RecordingGenerator(stub)) gives the same answer and outcome as
    ask(..., generator=stub); no Spec 002 code changes
"""

from __future__ import annotations

import pytest

import codecompass.online as online
from codecompass.eval.recording import RecordingGenerator
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_LOG, StubGenerator

MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "question?"}]


# -- pass-through ---------------------------------------------------------------------


def test_generate_returns_what_the_inner_generator_returns():
    rec = RecordingGenerator(StubGenerator(["the answer"]))
    assert rec.generate(MESSAGES) == "the answer"


def test_count_tokens_passes_through():
    inner = StubGenerator(["x"])
    rec = RecordingGenerator(inner)
    assert rec.count_tokens("one two three") == inner.count_tokens("one two three") == 3


def test_on_text_is_passed_through_when_given():
    inner = StubGenerator(["streamed reply"], piece_size=3)
    pieces = []
    RecordingGenerator(inner).generate(MESSAGES, on_text=pieces.append)
    assert inner.streamed == [True]
    assert "".join(pieces) == "streamed reply"


def test_on_text_is_not_passed_when_not_given():
    inner = StubGenerator(["plain reply"])
    RecordingGenerator(inner).generate(MESSAGES)
    assert inner.streamed == [False]


def test_inner_errors_propagate_unchanged():
    class Failing:
        def generate(self, messages, *, on_text=None):
            raise TimeoutError("llama-server went silent")

        def count_tokens(self, text):
            return 0

    with pytest.raises(TimeoutError, match="went silent"):
        RecordingGenerator(Failing()).generate(MESSAGES)


# -- recording ------------------------------------------------------------------------


def test_each_call_is_recorded_in_order():
    rec = RecordingGenerator(StubGenerator(["first", "second"]))
    rec.generate(MESSAGES)
    rec.generate(MESSAGES + [{"role": "assistant", "content": "first"}])
    assert [c["output"] for c in rec.calls] == ["first", "second"]
    assert [len(c["messages"]) for c in rec.calls] == [2, 3]
    assert set(rec.calls[0]) == {"messages", "output"}


def test_recorded_messages_are_a_copy():
    """The harness appends to its message list; the record must keep what was sent."""
    rec = RecordingGenerator(StubGenerator(["ok"]))
    sent = [dict(m) for m in MESSAGES]
    rec.generate(sent)
    sent.append({"role": "user", "content": "later"})
    sent[1]["content"] = "changed"
    assert rec.calls[0]["messages"] == MESSAGES


def test_a_new_wrapper_starts_empty():
    assert RecordingGenerator(StubGenerator(["x"])).calls == []


# -- with ask() on the fixture repo (AC-8.2: no Spec 002 change) ---------------------


def _ask(tmp_path, generator, mode="rag_tools"):
    repo = build_history_repo(tmp_path / "repo")
    kit = stubs(generator)
    return online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path, mode),
                      profile="dev", index_dir=tmp_path / "idx", **kit)


def test_ask_gives_the_same_result_with_and_without_the_wrapper(tmp_path):
    plain = _ask(tmp_path / "a", CitingGenerator())
    rec = RecordingGenerator(CitingGenerator())
    wrapped = _ask(tmp_path / "b", rec)
    assert wrapped.answer == plain.answer
    assert wrapped.citation_outcome == plain.citation_outcome == "F"
    assert [s.verified for s in wrapped.sources] == [s.verified for s in plain.sources]


def test_ask_records_the_context_and_the_raw_answer(tmp_path):
    rec = RecordingGenerator(CitingGenerator())
    _ask(tmp_path, rec)
    assert len(rec.calls) == 1
    sent = "\n".join(m["content"] for m in rec.calls[0]["messages"])
    assert "Why does authenticate retry?" in sent
    assert "--- " in sent  # a retrieved chunk header reached the model
    assert rec.calls[-1]["output"].startswith("Login retries on timeout [1].")
    assert "Sources" in rec.calls[-1]["output"]


def test_ask_records_every_round_including_the_tool_result(tmp_path):
    rec = RecordingGenerator(CitingGenerator(before=[TOOL_CALL_LOG]))
    result = _ask(tmp_path, rec)
    assert len(rec.calls) == 2
    assert rec.calls[0]["output"] == TOOL_CALL_LOG
    assert len(rec.calls[1]["messages"]) > len(rec.calls[0]["messages"])
    assert len(result.audit_log["tool_calls"]) == 1
