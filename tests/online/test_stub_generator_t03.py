"""T0.3 stub generator tests (tests-first).

Contract under test (Tasks 002 T0.3, Plan §4, D4, D5):
  - tests.support.stub_generator.StubGenerator(responses)
  - generate(messages) returns the configured responses in order; once they
    run out it keeps returning the last one (so "always requests tools" is
    one response)
  - every call's messages are recorded in .calls
  - count_tokens(text) counts whitespace-separated tokens, deterministically
  - canned responses: a tool-call request, a malformed tool call, an answer
    with no Sources section, and answer_citing() for valid or invalid
    citations in the fixed Sources format (Article VI.4)
"""

import re

import pytest

from tests.support import stub_generator as sg

MSGS = [{"role": "user", "content": "q"}]


def test_returns_configured_response():
    gen = sg.StubGenerator(["hello"])
    assert gen.generate(MSGS) == "hello"


def test_responses_in_order_then_last_repeats():
    gen = sg.StubGenerator(["a", "b"])
    assert [gen.generate(MSGS) for _ in range(4)] == ["a", "b", "b", "b"]


def test_records_messages_of_each_call():
    gen = sg.StubGenerator(["a", "b"])
    gen.generate(MSGS)
    second = MSGS + [{"role": "assistant", "content": "a"}]
    gen.generate(second)
    assert gen.calls == [MSGS, second]


def test_calls_are_snapshots_not_live_references():
    gen = sg.StubGenerator(["a"])
    msgs = list(MSGS)
    gen.generate(msgs)
    msgs.append({"role": "user", "content": "later"})
    assert gen.calls == [MSGS]


def test_empty_responses_rejected():
    with pytest.raises(ValueError):
        sg.StubGenerator([])


def test_count_tokens_is_whitespace_tokens():
    gen = sg.StubGenerator(["x"])
    assert gen.count_tokens("def foo(a, b):\n    return a") == 5
    assert gen.count_tokens("") == 0
    assert gen.count_tokens("one two") == gen.count_tokens("one   two")


def test_canned_tool_call_uses_plan_format():
    assert re.fullmatch(r"<tool>git_\w+\(.*\)</tool>", sg.TOOL_CALL_BLAME.strip())
    assert "<tool>" in sg.MALFORMED_TOOL_CALL
    assert "</tool>" not in sg.MALFORMED_TOOL_CALL


def test_answer_without_sources_has_no_sources_section():
    assert "Sources" not in sg.ANSWER_NO_SOURCES


def test_answer_citing_uses_fixed_sources_format():
    text = sg.answer_citing("src/auth.py", 1, 12, "a1b2c3d4e5f6")
    assert "[1]" in text.split("Sources")[0]
    assert "[1] src/auth.py, lines 1-12 (indexed at a1b2c3d)" in text
