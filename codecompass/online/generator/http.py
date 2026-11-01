"""JSON over local HTTP for llama-server (Article VIII.2)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from codecompass.online.generator.protocol import GeneratorError, StreamRefused


def request_json(url: str, payload: dict | None = None, *, timeout: float) -> dict:
    """GET (no payload) or POST JSON; raise GeneratorError with a clear reason."""
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, method="GET" if data is None else "POST",
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise GeneratorError(f"llama-server returned HTTP {exc.code} for {url}") from exc
    except (TimeoutError, URLError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, TimeoutError):
            raise GeneratorError(f"llama-server timed out after {timeout:g}s: {url}") from exc
        raise GeneratorError(f"could not reach llama-server at {url}: {reason}") from exc


def post_stream(url: str, payload: dict, *, timeout: float) -> Iterator[dict]:
    """POST *payload* and yield the server-sent events as dicts until ``[DONE]``.

    A server that ignores "stream" answers with plain JSON; that one reply is
    yielded as a single event. An HTTP error on opening raises StreamRefused so the
    caller can retry without streaming; a stream that ends before ``[DONE]`` raises
    GeneratorError.
    """
    request = Request(url, data=json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        raise StreamRefused(f"llama-server returned HTTP {exc.code} for {url}") from exc
    except (TimeoutError, URLError) as exc:
        raise _unreachable(exc, url, timeout) from exc
    with response:
        if "text/event-stream" not in response.headers.get("Content-Type", ""):
            yield json.loads(response.read())
            return
        try:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):  # blank lines, ": comments", "event:" ...
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                yield json.loads(data)
        except (TimeoutError, OSError, HTTPException) as exc:
            raise _unreachable(exc, url, timeout) from exc
    raise GeneratorError(f"llama-server stream ended before its [DONE] marker: {url}")


def _unreachable(exc: Exception, url: str, timeout: float) -> GeneratorError:
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, TimeoutError):
        return GeneratorError(f"llama-server timed out after {timeout:g}s: {url}")
    return GeneratorError(f"could not reach llama-server at {url}: {reason}")
