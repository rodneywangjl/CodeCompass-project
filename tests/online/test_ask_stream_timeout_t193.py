"""T19.3 ask does not time out on slow machines (tests first, mocked HTTP).

Contract under test (Spec 004 AC-2.5 as amended by T19.3; Article VIII.1, VIII.2):
  - generate(messages) with no on_text streams too: the request has "stream": true,
    and the joined pieces are returned
  - the joined text equals what the non-streaming reply was
  - timeout_seconds bounds each wait (before the first piece and between pieces),
    not the whole answer: a long answer whose pieces each arrive in time succeeds
  - the readiness check (the first contact with the server) uses
    [generator] connect_timeout_seconds, so a server that never answers fails in
    that many seconds with GeneratorError (the existing "not ready" message)
  - a stream that stops mid-answer still raises GeneratorError
  - a server that refuses streaming falls back to one normal call (no "stream")
  - [generator] connect_timeout_seconds loads, layers and rejects bad values
"""

import io
from urllib.error import HTTPError, URLError

import pytest

from codecompass.online.config import (
    GeneratorConfig, ModelProfile, load_online_config, load_online_config_layers)
from codecompass.online.generator import http, llama, protocol
from tests.support.fake_http import FakeServer

URL = "http://127.0.0.1:8080"
MESSAGES = [{"role": "system", "content": "rules"}, {"role": "user", "content": "q"}]


def make(monkeypatch, server, connect=None):
    monkeypatch.setattr(http, "urlopen", server)
    profile = ModelProfile(model_id="m", temperature=0.2, max_tokens=512, seed=7,
                           stop_tokens=("<|im_end|>",), cache_prompt=False)
    extra = {} if connect is None else {"connect_timeout_seconds": connect}
    return llama.LlamaServerGenerator(profile, server_url=URL, timeout_seconds=9, **extra)


def chat(server):
    return server.bodies("/v1/chat/completions")


def test_no_callback_streams_and_returns_the_full_text(monkeypatch):
    server = FakeServer(stream=["The ", "answer", " is 42."])
    assert make(monkeypatch, server).generate(MESSAGES) == "The answer is 42."
    (body,) = chat(server)
    assert body["stream"] is True


def test_joined_text_equals_the_non_streaming_reply(monkeypatch):
    streamed = make(monkeypatch, FakeServer(stream=["Hello", " there,", " friend."]))
    plain = make(monkeypatch, FakeServer(reply="Hello there, friend."))
    assert streamed.generate(MESSAGES) == plain.generate(MESSAGES) == "Hello there, friend."


def test_a_long_answer_whose_pieces_each_arrive_in_time_succeeds(monkeypatch):
    # 60 pieces: the total is longer than timeout_seconds (9); no whole-answer cap applies.
    server = FakeServer(stream=["w "] * 60)
    assert make(monkeypatch, server).generate(MESSAGES) == "w " * 60
    (chat_request,) = [r for r in server.requests if r["url"].endswith("/v1/chat/completions")]
    assert chat_request["timeout"] == 9  # the bound on each wait, not on the answer


def test_a_server_that_never_answers_fails_within_the_connect_timeout(monkeypatch):
    server = FakeServer(error=URLError(TimeoutError("timed out")))
    gen = make(monkeypatch, server, connect=3)
    with pytest.raises(protocol.GeneratorError, match="not ready"):
        gen.generate(MESSAGES)
    probe = server.requests[0]
    assert probe["url"].endswith("/health") and probe["timeout"] == 3
    assert chat(server) == []


def test_a_stream_that_stops_mid_answer_is_an_error(monkeypatch):
    server = FakeServer(stream=["one ", "two ", "three"], drop_after=2)
    with pytest.raises(protocol.GeneratorError, match="stream ended"):
        make(monkeypatch, server).generate(MESSAGES)


def test_a_refused_stream_falls_back_to_one_normal_call(monkeypatch):
    refusal = HTTPError("http://x", 400, "no streaming", {}, io.BytesIO(b"{}"))
    server = FakeServer(reply="fallback text", stream_open_error=refusal)
    assert make(monkeypatch, server).generate(MESSAGES) == "fallback text"
    first, second = chat(server)
    assert first["stream"] is True and "stream" not in second


def test_connect_timeout_has_a_default_and_loads_from_toml(tmp_path):
    assert GeneratorConfig().connect_timeout_seconds == 5
    f = tmp_path / "codecompass.toml"
    f.write_text("[generator]\nconnect_timeout_seconds = 2\n")
    assert load_online_config(f).generator.connect_timeout_seconds == 2


def test_connect_timeout_layers_like_the_other_generator_settings(tmp_path):
    base, override = tmp_path / "base.toml", tmp_path / "user.toml"
    base.write_text("[generator]\nconnect_timeout_seconds = 2\n")
    override.write_text("[generator]\nconnect_timeout_seconds = 3\n")
    assert load_online_config_layers([base, override]).generator.connect_timeout_seconds == 3
    assert load_online_config_layers([base]).generator.connect_timeout_seconds == 2


@pytest.mark.parametrize("bad", ["0", "-1", '"5"', "true"])
def test_bad_connect_timeout_is_rejected(tmp_path, bad):
    f = tmp_path / "codecompass.toml"
    f.write_text(f"[generator]\nconnect_timeout_seconds = {bad}\n")
    with pytest.raises(ValueError, match="connect_timeout_seconds"):
        load_online_config(f)
