"""Minimal terminal UI (Spec 004): `codecompass` prompt loop over ask()."""

from __future__ import annotations

PROMPT = "> "
STATUS = "Thinking…"
CLEAR_LINE = "\r\x1b[K"
EXIT_COMMANDS = ("/exit", "/quit")


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


def main(argv=None, *, stdin=None, stdout=None, stderr=None) -> int:
    """`codecompass [REPO]`: start an interactive session (Spec 004)."""
    raise NotImplementedError
