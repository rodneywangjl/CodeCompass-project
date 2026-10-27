"""T7.3 health check tests (tests-first, mocked HTTP).

Contract under test (Spec AC-5.10, AC-5.12; Plan D13 items 5 and 8):
  - generator.server.health_check(server_url, profile, timeout) -> bool:
    True when /health answers 200 and /props matches the profile; False when
    the server cannot be reached or is still loading; protocol.ServerMismatchError
    when its context is smaller than the profile's or another model is loaded
  - LlamaServerGenerator.generate refuses to run when the check fails
  - generator.server.launch_command(profile, model_path, port) builds the one
    documented llama-server command line (Article VIII.2)
"""

from urllib.error import URLError

import pytest

from codecompass.online.config import ModelProfile
from codecompass.online.generator import http, llama, protocol, server
from tests.support.fake_http import FakeServer

URL = "http://127.0.0.1:8080"


def profile():
    return ModelProfile(model_id="m", context_window=8192, gguf_file="model.gguf",
                        server_args=("-np", "1"))


def check(monkeypatch, fake, prof=None):
    monkeypatch.setattr(http, "urlopen", fake)
    return server.health_check(URL, prof or profile(), timeout=5)


def test_healthy_server_passes(monkeypatch):
    assert check(monkeypatch, FakeServer(n_ctx=8192)) is True


def test_unreachable_or_loading_server_fails(monkeypatch):
    assert check(monkeypatch, FakeServer(error=URLError("refused"))) is False
    assert check(monkeypatch, FakeServer(healthy=False)) is False


def test_too_small_context_fails_loudly(monkeypatch):
    with pytest.raises(protocol.ServerMismatchError, match="8192"):
        check(monkeypatch, FakeServer(n_ctx=4096))


def test_wrong_model_fails_loudly(monkeypatch):
    with pytest.raises(protocol.ServerMismatchError, match="model.gguf"):
        check(monkeypatch, FakeServer(model_path="/models/other.gguf"))


def test_unpinned_profile_accepts_any_model(monkeypatch):
    unpinned = ModelProfile(model_id="m", context_window=8192)
    assert check(monkeypatch, FakeServer(model_path="/x/other.gguf"), unpinned) is True


def test_generator_refuses_to_generate_when_unhealthy(monkeypatch):
    fake = FakeServer(healthy=False)
    monkeypatch.setattr(http, "urlopen", fake)
    gen = llama.LlamaServerGenerator(profile(), server_url=URL, timeout_seconds=5)
    with pytest.raises(protocol.GeneratorError, match="not ready"):
        gen.generate([{"role": "user", "content": "q"}])
    assert fake.bodies("/v1/chat/completions") == []


def test_generator_checks_health_once(monkeypatch):
    fake = FakeServer(n_ctx=8192)
    monkeypatch.setattr(http, "urlopen", fake)
    gen = llama.LlamaServerGenerator(profile(), server_url=URL, timeout_seconds=5)
    gen.generate([{"role": "user", "content": "q"}])
    gen.generate([{"role": "user", "content": "q"}])
    assert sum(r["url"].endswith("/health") for r in fake.requests) == 1


def test_launch_command():
    cmd = server.launch_command(profile(), "/models/model.gguf", port=8080)
    assert cmd[:3] == ["llama-server", "-m", "/models/model.gguf"]
    joined = " ".join(cmd)
    assert "--host 127.0.0.1" in joined and "--port 8080" in joined
    assert "-c 8192" in joined and joined.endswith("-np 1")
