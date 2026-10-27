"""llama-server health check and launch command (Article VIII.2).

The server is started by hand in Sprint 2 (spec C9; see MODEL-SETUP.md), so
this is the one documented place for its command line and for checking that
what is running can serve the active profile.
"""

from __future__ import annotations

from codecompass.online.generator.http import request_json
from codecompass.online.generator.protocol import GeneratorError, ServerMismatchError


def health_check(server_url: str, profile, *, timeout: float) -> bool:
    """True when the server is up and matches *profile* (Plan D13 items 5, 8).

    False when it cannot be reached or is still loading. A server that is up
    but cannot serve the profile raises ServerMismatchError (AC-5.12).
    """
    base = server_url.rstrip("/")
    try:
        request_json(f"{base}/health", timeout=timeout)
        props = request_json(f"{base}/props", timeout=timeout)
    except GeneratorError:
        return False
    n_ctx = props.get("default_generation_settings", {}).get("n_ctx", 0)
    if n_ctx < profile.context_window:
        raise ServerMismatchError(
            f"llama-server context is {n_ctx} tokens per slot, but profile "
            f"{profile.model_id!r} needs {profile.context_window}; restart it with "
            f"-c {profile.context_window}")
    model_path = props.get("model_path", "")
    if profile.gguf_file and not model_path.endswith(profile.gguf_file):
        raise ServerMismatchError(
            f"llama-server has {model_path!r} loaded, but profile "
            f"{profile.model_id!r} pins {profile.gguf_file!r}")
    return True


def launch_command(profile, model_path: str, *, port: int) -> list[str]:
    """The llama-server command line for *profile*, bound to localhost."""
    return ["llama-server", "-m", model_path, "--host", "127.0.0.1",
            "--port", str(port), "-c", str(profile.context_window),
            *profile.server_args]
