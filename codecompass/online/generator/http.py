"""JSON over local HTTP for llama-server (Article VIII.2)."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from codecompass.online.generator.protocol import GeneratorError


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
