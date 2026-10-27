"""llama-server chat client (Article VIII.2, Plan D13).

The only module that talks to llama-server. Chat templating is done by the
server from the GGUF's template; this wrapper owns the request and response
format, stop tokens and generation parameters.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from codecompass.online.generator.http import request_json
from codecompass.online.generator.protocol import GeneratorError
from codecompass.online.generator.server import health_check

_LOG = logging.getLogger(__name__)
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LlamaServerGenerator:
    """Generator backed by a running llama-server (OpenAI-compatible endpoint)."""

    def __init__(self, profile, *, server_url: str, timeout_seconds: float) -> None:
        self.profile = profile
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout_seconds
        self._ready = False
        if urlsplit(self.server_url).hostname not in _LOCAL_HOSTS:
            _LOG.warning("llama-server URL %s is not localhost; Article VIII.2 "
                         "expects 127.0.0.1 unless a deployment spec says otherwise",
                         self.server_url)

    def _post(self, path: str, payload: dict) -> dict:
        return request_json(self.server_url + path, payload, timeout=self.timeout)

    def health_check(self) -> bool:
        return health_check(self.server_url, self.profile, timeout=self.timeout)

    def generate(self, messages: list[dict]) -> str:
        if not self._ready:
            if not self.health_check():
                raise GeneratorError(
                    f"llama-server at {self.server_url} is not ready; start it as "
                    "described in MODEL-SETUP.md")
            self._ready = True
        p = self.profile
        data = self._post("/v1/chat/completions", {
            "messages": messages, "temperature": p.temperature,
            "max_tokens": p.max_tokens, "stop": list(p.stop_tokens),
            "seed": p.seed, "cache_prompt": p.cache_prompt,
        })
        return data["choices"][0]["message"]["content"]

    def count_tokens(self, text: str) -> int:
        return len(self._post("/tokenize", {"content": text})["tokens"])
