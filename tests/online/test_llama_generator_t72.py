"""T7.2 LlamaServerGenerator tests (tests-first, mocked HTTP).

Contract under test (Spec AC-5.3, AC-5.4, AC-5.6, FR-12; Plan D13):
  - generator.llama.LlamaServerGenerator(profile, *, server_url, timeout_seconds)
  - generate(messages) POSTs JSON to /v1/chat/completions with the messages
    and the profile's temperature, max_tokens, stop, seed and cache_prompt,
    and returns the assistant content
  - count_tokens(text) POSTs {"content": text} to /tokenize -> len(tokens)
  - a connection error or timeout raises protocol.GeneratorError with a clear message
  - all HTTP goes through generator.http (patched here: sockets are blocked)
"""

from urllib.error import URLError

import pytest

from codecompass.online.config import ModelProfile
from codecompass.online.generator import http, llama, protocol
from tests.support.fake_http import FakeServer


def profile():
    return ModelProfile(model_id="m", temperature=0.2, max_tokens=512, seed=7,
                        stop_tokens=("<|im_end|>",), cache_prompt=False)


MESSAGES = [{"role": "system", "content": "rules"}, {"role": "user", "content": "q"}]


def make(monkeypatch, server):
    monkeypatch.setattr(http, "urlopen", server)
    return llama.LlamaServerGenerator(profile(), server_url="http://127.0.0.1:8080",
                                      timeout_seconds=9)


def test_generate_posts_chat_completion_and_returns_content(monkeypatch):
    server = FakeServer(reply="the answer")
    assert make(monkeypatch, server).generate(MESSAGES) == "the answer"
    (body,) = server.bodies("/v1/chat/completions")
    assert body["messages"] == MESSAGES
    assert body["temperature"] == 0.2 and body["max_tokens"] == 512
    assert body["stop"] == ["<|im_end|>"] and body["seed"] == 7
    assert body["cache_prompt"] is False
    chat = [r for r in server.requests if r["url"].endswith("/v1/chat/completions")][0]
    assert chat["method"] == "POST" and chat["timeout"] == 9
    assert chat["headers"]["Content-type"] == "application/json"


def test_count_tokens_uses_tokenize(monkeypatch):
    server = FakeServer()
    assert make(monkeypatch, server).count_tokens("a b c") == 3
    assert server.bodies("/tokenize") == [{"content": "a b c"}]


def test_connection_error_is_clear(monkeypatch):
    gen = make(monkeypatch, FakeServer(error=URLError("Connection refused")))
    with pytest.raises(protocol.GeneratorError, match="could not reach llama-server"):
        gen.count_tokens("x")


@pytest.mark.parametrize("error", [TimeoutError(), URLError(TimeoutError())])
def test_timeout_is_clear(monkeypatch, error):
    gen = make(monkeypatch, FakeServer(error=error))
    with pytest.raises(protocol.GeneratorError, match="timed out after 9s"):
        gen.count_tokens("x")
