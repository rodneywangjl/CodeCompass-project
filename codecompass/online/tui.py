"""Minimal terminal UI (Spec 004): `codecompass` prompt loop over ask()."""

from __future__ import annotations


def run_session(answer, *, stdin, stdout, stderr) -> int:
    """Read questions from *stdin*, print ``answer(question)`` to *stdout*."""
    raise NotImplementedError
