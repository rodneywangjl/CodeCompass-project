"""T7.4 localhost binding tests (tests-first).

Contract under test (Spec AC-5.5; Article VIII.2):
  - the default server URL is http://127.0.0.1:<port>
  - LlamaServerGenerator accepts a non-localhost URL but logs a warning
"""

import logging

from codecompass.online.config import OnlineConfig, ModelProfile
from codecompass.online.generator import llama

PROFILE = ModelProfile(model_id="m")


def test_default_url_is_localhost():
    assert OnlineConfig().generator.server_url.startswith("http://127.0.0.1:")


def test_remote_url_is_accepted_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        llama.LlamaServerGenerator(PROFILE, server_url="http://10.0.0.5:8080",
                                   timeout_seconds=5)
    assert any("not localhost" in r.getMessage() for r in caplog.records)


def test_localhost_urls_do_not_warn(caplog):
    with caplog.at_level(logging.WARNING):
        for url in ("http://127.0.0.1:8080", "http://localhost:8080"):
            llama.LlamaServerGenerator(PROFILE, server_url=url, timeout_seconds=5)
    assert not caplog.records
