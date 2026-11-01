"""Fake urlopen for generator tests: the required suite blocks real sockets."""

from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import HTTPError


class FakeServer:
    """Answers llama-server endpoints from a dict and records every request."""

    def __init__(self, n_ctx=32768, model_path="/models/model.gguf", healthy=True,
                 reply="hello", error=None, stream=None, stream_raw=None, drop_after=None,
                 stream_open_error=None, stream_error=None):
        """stream: text deltas (str) or raw event dicts, answered as server-sent events to
        a request with "stream": true. With none of stream / stream_raw / stream_open_error
        the server ignores "stream" and answers with the normal JSON reply.
        stream_raw: hand-written SSE bytes. drop_after: end the stream, with no
        [DONE], after that many events. stream_open_error: raised for a streaming
        request only. stream_error: raised for a streaming chat request only (a
        connection lost after the readiness check passed)."""
        self.requests: list[dict] = []
        self.n_ctx, self.model_path, self.healthy = n_ctx, model_path, healthy
        self.reply, self.error = reply, error
        self.stream, self.stream_raw, self.drop_after = stream, stream_raw, drop_after
        self.stream_open_error, self.stream_error = stream_open_error, stream_error

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
        if path == "/v1/chat/completions" and body.get("stream"):
            if self.stream_error is not None:
                raise self.stream_error
            if self.stream_open_error is not None:
                raise self.stream_open_error
            if self.stream_raw is not None:
                return _Stream(self.stream_raw)
            if self.stream is not None:
                return _Stream(self._events())
        if path == "/v1/chat/completions":
            return _Response({"choices": [{"message": {"role": "assistant",
                                                       "content": self.reply}}]})
        raise AssertionError(f"unexpected path {path}")

    def _events(self) -> bytes:
        events = [e if isinstance(e, dict) else {"choices": [{"delta": {"content": e}}]}
                  for e in self.stream]
        out = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n"
                       for e in events[:self.drop_after])
        return out if self.drop_after is not None else out + b"data: [DONE]\n\n"

    def bodies(self, path):
        return [r["body"] for r in self.requests if r["url"].endswith(path)]


class _Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = 200
        self.headers = _headers("application/json")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _Stream(io.BytesIO):
    """A text/event-stream response: iterating it yields the lines, as urlopen's does."""

    def __init__(self, data: bytes):
        super().__init__(data)
        self.status = 200
        self.headers = _headers("text/event-stream")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _headers(content_type: str) -> Message:
    message = Message()
    message["Content-Type"] = content_type
    return message
