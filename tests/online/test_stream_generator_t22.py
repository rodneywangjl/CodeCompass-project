"""T2.2 (Spec 004) streaming in the generator wrapper: tests first, mocked HTTP.

Contract under test (Spec 004 AC-2.5; Article VIII.2, streaming only in the wrapper):
  generate(messages, *, on_text=None) -> str
  - with on_text, the chat request carries "stream": true (every other field as
    without it); each text delta reaches on_text in order and the full text is
    returned; events with no text are skipped
  - without on_text the request and result are exactly as before
  - a server that ignores "stream", or refuses it with an HTTP error, falls back to
    one normal call and on_text receives the whole text once
  - a stream that ends without its [DONE] marker, a refused connection and a
    timeout each raise GeneratorError with a clear message
  - the readiness check still runs first
"""

import io
from urllib.error import HTTPError, URLError

import pytest

from codecompass.online.config import ModelProfile
from codecompass.online.generator import http, llama, protocol
from tests.support.fake_http import FakeServer

MESSAGES = [{"role": "system", "content": "rules"}, {"role": "user", "content": "q"}]


def make(monkeypatch, server):
    monkeypatch.setattr(http, "urlopen", server)
    profile = ModelProfile(model_id="m", temperature=0.2, max_tokens=512, seed=7,
                           stop_tokens=("<|im_end|>",), cache_prompt=False)
    return llama.LlamaServerGenerator(profile, server_url="http://127.0.0.1:8080",
                                      timeout_seconds=9)


def stream(monkeypatch, server):
    """Generate with a recording callback; return (text, pieces the callback saw)."""
    seen = []
    text = make(monkeypatch, server).generate(MESSAGES, on_text=seen.append)
    return text, seen


def chat(server):
    return server.bodies("/v1/chat/completions")


def test_a_callback_makes_the_request_stream_and_changes_nothing_else(monkeypatch):
    plain, streamed = FakeServer(reply="x"), FakeServer(stream=["x"])
    make(monkeypatch, plain).generate(MESSAGES)
    stream(monkeypatch, streamed)
    (a,), (b,) = chat(plain), chat(streamed)
    assert b.pop("stream") is True and "stream" not in a
    assert a == b  # messages, temperature, max_tokens, stop, seed, cache_prompt


def test_each_delta_reaches_the_callback_in_order_and_the_full_text_is_returned(monkeypatch):
    text, seen = stream(monkeypatch, FakeServer(stream=["The ", "answer", " is", " 42."]))
    assert seen == ["The ", "answer", " is", " 42."]
    assert text == "The answer is 42."


def test_events_without_text_are_skipped(monkeypatch):
    events = [{"choices": [{"delta": {"role": "assistant"}}]},
              {"choices": [{"delta": {"content": ""}}]},
              {"choices": [{"delta": {"content": None}}]},
              {"choices": []},
              "Hi",
              {"choices": [{"delta": {}, "finish_reason": "stop"}]}]
    text, seen = stream(monkeypatch, FakeServer(stream=events))
    assert seen == ["Hi"] and text == "Hi"


def test_server_sent_event_framing_is_tolerated(monkeypatch):
    raw = (b": keep-alive\n\n"
           b'data:{"choices":[{"delta":{"content":"a"}}]}\r\n\r\n'  # no space, CRLF
           b"\n"
           b'data: {"choices":[{"delta":{"content":"\xc3\xa9\xe2\x86\x92"}}]}\n\n'
           b"event: ignored\n"
           b"data: [DONE]\n\n")
    text, seen = stream(monkeypatch, FakeServer(stream_raw=raw))
    assert seen == ["a", "é→"] and text == "aé→"


def test_without_a_callback_the_request_and_result_are_unchanged(monkeypatch):
    server = FakeServer(reply="plain", stream=["never", "used"])
    assert make(monkeypatch, server).generate(MESSAGES) == "plain"
    (body,) = chat(server)
    assert "stream" not in body


def test_the_readiness_check_still_runs_before_the_stream(monkeypatch):
    server = FakeServer(healthy=False, stream=["x"])
    seen = []
    with pytest.raises(protocol.GeneratorError, match="not ready"):
        make(monkeypatch, server).generate(MESSAGES, on_text=seen.append)
    assert seen == [] and chat(server) == []


def test_a_server_that_ignores_stream_falls_back_to_the_whole_reply(monkeypatch):
    server = FakeServer(reply="the whole reply")  # answers a streaming request with JSON
    text, seen = stream(monkeypatch, server)
    assert text == "the whole reply" and seen == ["the whole reply"]


def test_an_http_error_opening_the_stream_falls_back_to_a_normal_call(monkeypatch):
    refusal = HTTPError("http://x", 400, "no streaming", {}, io.BytesIO(b"{}"))
    server = FakeServer(reply="fallback text", stream_open_error=refusal)
    text, seen = stream(monkeypatch, server)
    assert text == "fallback text" and seen == ["fallback text"]
    first, second = chat(server)
    assert first["stream"] is True and "stream" not in second


def test_a_stream_that_ends_without_done_is_an_error_after_the_text_it_sent(monkeypatch):
    server = FakeServer(stream=["one ", "two ", "three"], drop_after=2)
    seen = []
    with pytest.raises(protocol.GeneratorError, match="stream ended"):
        make(monkeypatch, server).generate(MESSAGES, on_text=seen.append)
    assert seen == ["one ", "two "]


def test_a_connection_lost_while_streaming_is_clear(monkeypatch):
    gen = make(monkeypatch, FakeServer(stream_error=URLError("Connection refused")))
    with pytest.raises(protocol.GeneratorError, match="could not reach llama-server"):
        gen.generate(MESSAGES, on_text=lambda t: None)


@pytest.mark.parametrize("error", [TimeoutError(), URLError(TimeoutError())])
def test_a_timeout_while_streaming_is_clear(monkeypatch, error):
    gen = make(monkeypatch, FakeServer(stream_error=error))
    with pytest.raises(protocol.GeneratorError, match="timed out after 9s"):
        gen.generate(MESSAGES, on_text=lambda t: None)
