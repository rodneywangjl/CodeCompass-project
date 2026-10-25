"""Verifier tools: git blame and git log, read-only and validated (Article V.2)."""

from __future__ import annotations

import posixpath
import re
import subprocess

_RANGE = re.compile(r"(\d+)(?:-(\d+))?")


class ToolArgumentError(ValueError):
    """A tool argument failed validation; the message is shown to the model."""


def _git(repo, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, shell=False, timeout=timeout)


def validate_path(repo, commit: str, path) -> str:
    """Normalised repo-relative path of a file that exists at *commit* (Plan D6).

    Existence in the git tree is the real check: it rules out anything outside
    the repository. Commands pass ``--`` before the path and never use a
    shell, so no character blacklist is needed.
    """
    if not isinstance(path, str) or not path.strip():
        raise ToolArgumentError("path is required")
    norm = posixpath.normpath(path)
    if posixpath.isabs(norm) or norm.startswith("-"):
        raise ToolArgumentError(f"path must be repo-relative: {path!r}")
    if ".." in norm.split("/"):
        raise ToolArgumentError(f"path must stay inside the repository: {path!r}")
    if _git(repo, "cat-file", "-t", f"{commit}:{norm}").stdout.strip() != "blob":
        raise ToolArgumentError(f"no such file at the indexed commit: {path!r}")
    return norm


def validate_lines(spec, line_count: int) -> tuple[int, int]:
    """``N`` or ``N-M`` with 1 <= N <= M <= line_count."""
    m = _RANGE.fullmatch(str(spec))
    if m is None:
        raise ToolArgumentError(f"lines must look like 42 or 42-58: {spec!r}")
    start = int(m.group(1))
    end = int(m.group(2) or start)
    if not 1 <= start <= end <= line_count:
        raise ToolArgumentError(
            f"lines {spec!r} out of range: the file has {line_count} lines")
    return start, end


def validate_n(n, limit: int) -> int:
    """Number of commits for git log, 1..limit."""
    if isinstance(n, bool) or not isinstance(n, (int, str)) or not str(n).isdigit():
        raise ToolArgumentError(f"n must be a whole number: {n!r}")
    value = int(n)
    if not 1 <= value <= limit:
        raise ToolArgumentError(f"n must be between 1 and {limit}: {n!r}")
    return value
