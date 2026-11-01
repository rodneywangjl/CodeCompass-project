"""Minimal terminal UI (Spec 004): `codecompass` prompt loop over ask()."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

PROMPT = "> "
STATUS = "Thinking…"
CLEAR_LINE = "\r\x1b[K"
EXIT_COMMANDS = ("/exit", "/quit")
CONFIG_NAME = "codecompass.toml"
DEFAULT_PORT = 8080  # llama-server port when the configured URL names none


def _say(stream, text: str) -> None:
    stream.write(text)
    stream.flush()


def run_session(answer, *, stdin, stdout, stderr) -> int:
    """Read questions from *stdin*, print ``answer(question)`` to *stdout* (Spec 004).

    Only answers go to stdout. The prompt, status line, hints and errors go to
    stderr, and only when both streams are terminals (AC-1.5, AC-1.11).
    Returns 0 on /exit, /quit or end of input; nothing a question does ends
    the session (AC-1.7, AC-1.8).
    """
    prompting = stdin.isatty() and stderr.isatty()
    status = stderr.isatty()
    while True:
        if prompting:
            _say(stderr, PROMPT)
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            _say(stderr, "\n(type /exit or press Ctrl-D to quit)\n")
            continue
        if line == "":  # end of input
            if prompting:
                _say(stderr, "\n")
            return 0
        question = line.strip()
        if not question:
            continue
        if question in EXIT_COMMANDS:
            return 0
        if status:
            _say(stderr, STATUS)
        try:
            text = answer(question)
        except KeyboardInterrupt:
            _clear(stderr, status)
            _say(stderr, "Interrupted.\n")
            continue
        except Exception as exc:  # noqa: BLE001 (one failed question must not end the session)
            _clear(stderr, status)
            _say(stderr, f"error: {str(exc) or type(exc).__name__}\n")
            continue
        _clear(stderr, status)
        _say(stdout, text if text.endswith("\n") else text + "\n")


def _clear(stderr, status: bool) -> None:
    if status:
        _say(stderr, CLEAR_LINE)


def _repo_root(path) -> Path:
    """The git repository root containing *path* (AC-1.1)."""
    p = Path(path).expanduser()
    if not p.exists():
        raise ValueError(f"path does not exist: {p}")
    if p.is_file():
        p = p.parent
    try:
        run = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
    except FileNotFoundError:
        raise ValueError("git is not installed or not on PATH") from None
    if run.returncode != 0:
        raise ValueError(f"{p} is not a git repository")
    return Path(run.stdout.strip())


def _find_config(root: Path, explicit: str | None) -> Path | None:
    """--config, else <root>/codecompass.toml, else the user-level file (AC-1.13)."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError(f"config file not found: {path}")
        return path
    user_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    for path in (root / CONFIG_NAME, user_dir / "codecompass" / CONFIG_NAME):
        if path.is_file():
            return path
    return None


def _start_command(profile, server_url: str) -> str:
    from codecompass.online.generator.server import launch_command
    model = f"/path/to/{profile.gguf_file or '<model>.gguf'}"
    port = urlsplit(server_url).port or DEFAULT_PORT
    return shlex.join(launch_command(profile, model, port=port))


def _check_generator(generator, profile, server_url: str, stderr) -> None:
    """Warn (never fail) when the generator is down or does not match the profile (AC-1.10)."""
    try:
        if generator.health_check():
            return
        message = (f"llama-server is not reachable at {server_url}. Start it with:\n"
                   f"  {_start_command(profile, server_url)}")
    except Exception as exc:  # noqa: BLE001 (a mismatched server explains itself)
        message = str(exc) or type(exc).__name__
    _say(stderr, f"warning: {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codecompass",
        description="Ask questions about a git repository, answered with checked citations.")
    parser.add_argument("repo", nargs="?", default=".",
                        help="path inside the git repository (default: current directory)")
    parser.add_argument("--profile", help="generator profile (default: GENERATOR_PROFILE "
                                          "or the config default)")
    parser.add_argument("--config", help="codecompass.toml (default: <repo root>/"
                                         "codecompass.toml, then ~/.config/codecompass/)")
    parser.add_argument("--index-dir", help="override the index directory")
    return parser


def main(argv=None, *, stdin=None, stdout=None, stderr=None) -> int:
    """`codecompass [REPO]`: start an interactive session (Spec 004)."""
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    args = _parser().parse_args(argv)
    try:
        root = _repo_root(args.repo)
        config_path = _find_config(root, args.config)
        # heavy model libraries are not imported here: they load on the first question
        import codecompass.online as online
        from codecompass.online.config import load_online_config
        from codecompass.online.generator.llama import LlamaServerGenerator
        from codecompass.online.generator.profiles import resolve_profile
        config = load_online_config(config_path)
        name, profile = resolve_profile(config, args.profile)
        generator = LlamaServerGenerator(profile, server_url=config.generator.server_url,
                                         timeout_seconds=config.generator.timeout_seconds)
    except Exception as exc:  # noqa: BLE001 (startup problems are reported, not traced)
        _say(stderr, f"error: {exc}\n")
        return 1
    if stdin.isatty() and stderr.isatty():
        _say(stderr, f"codecompass: repo: {root}\n"
                     f"codecompass: profile {name} ({profile.model_id})\n"
                     f"codecompass: config: {config_path or 'built-in defaults'}\n"
                     "Type a question. /exit or Ctrl-D to quit.\n")
    _check_generator(generator, profile, config.generator.server_url, stderr)

    def answer(question: str) -> str:
        return online.ask(root, question, config=config, profile=name,
                          index_dir=args.index_dir, generator=generator).answer

    return run_session(answer, stdin=stdin, stdout=stdout, stderr=stderr)
