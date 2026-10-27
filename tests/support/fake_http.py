"""Fake urlopen for generator tests: the required suite blocks real sockets."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError


class FakeServer:
    """Answers llama-server endpoints from a dict and records every request."""

    def __init__(self, n_ctx=32768, model_path="/models/model.gguf", healthy=True,
                 reply="hello", error=None):
        self.requests: list[dict] = []
        self.n_ctx, self.model_path, self.healthy = n_ctx, model_path, healthy
        self.reply, self.error = reply, error

    def __call__(self, request, timeout=None):
        url = request.full_url
        body = json.loads(request.data) if request.data else None
        self.requests.append({"url": url, "method": request.get_method(),
                              "body": body, "timeout": timeout,
                              "headers": dict(request.header_items())})
        if self.error is not None:
            raise self.error
        path = "/" + url.split("/", 3)[3]
        if path == "/health":
            if not self.healthy:
                raise HTTPError(url, 503, "loading", {}, io.BytesIO(b"{}"))
            return _Response({"status": "ok"})
        if path == "/props":
            return _Response({"default_generation_settings": {"n_ctx": self.n_ctx},
                              "model_path": self.model_path})
        if path == "/tokenize":
            return _Response({"tokens": list(range(len(body["content"].split())))})
        if path == "/v1/chat/completions":
            return _Response({"choices": [{"message": {"role": "assistant",
                                                       "content": self.reply}}]})
        raise AssertionError(f"unexpected path {path}")

    def bodies(self, path):
        return [r["body"] for r in self.requests if r["url"].endswith(path)]


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
