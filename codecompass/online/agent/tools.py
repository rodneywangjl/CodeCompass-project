"""Verifier tools: git blame and git log, read-only and validated (Article V.2)."""

from __future__ import annotations

import posixpath
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_RANGE = re.compile(r"(\d+)(?:-(\d+))?")
_BLAME_HEADER = re.compile(r"([0-9a-f]{40}) \d+ (\d+)(?: \d+)?")


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


@dataclass(frozen=True)
class CommitRecord:
    """One commit as reported by a tool; the source of harness-copied metadata."""
    sha: str
    author: str
    date: str
    subject: str


@dataclass(frozen=True)
class ToolOutput:
    """Rendered text for the model plus the parsed commits it mentions (Plan D7)."""
    text: str
    commits: tuple[CommitRecord, ...] = ()
    error: bool = False


def _render(record: CommitRecord, suffix: str = "") -> str:
    line = f'{record.sha[:7]} {record.date} {record.author} "{record.subject}"'
    return f"{line} {suffix}" if suffix else line


def _ranges(numbers: list[int]) -> str:
    spans: list[list[int]] = []
    for n in sorted(numbers):
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def _author_date(seconds: str, tz: str) -> str:
    sign = -1 if tz.startswith("-") else 1
    offset = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])) * sign
    return datetime.fromtimestamp(int(seconds), timezone(offset)).strftime("%Y-%m-%d")


def _line_count(repo, commit: str, path: str) -> int:
    return len(_git(repo, "cat-file", "-p", f"{commit}:{path}").stdout.splitlines())


def _run(repo, args: list[str], name: str, timeout: float):
    """Run a git command; return (stdout, None) or (None, error ToolOutput)."""
    try:
        proc = _git(repo, *args, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, ToolOutput(text=f"error: {name} timed out after {timeout}s",
                                error=True)
    if proc.returncode != 0:
        return None, ToolOutput(text=f"error: {name} failed: {proc.stderr.strip()}",
                                error=True)
    return proc.stdout, None


def git_blame(repo, commit: str, path, lines=None, *, timeout: float) -> ToolOutput:
    """Blame *path* at *commit* (the indexed commit, Plan D7)."""
    path = validate_path(repo, commit, path)
    args = ["blame", "--porcelain"]
    if lines is not None:
        start, end = validate_lines(lines, _line_count(repo, commit, path))
        args += ["-L", f"{start},{end}"]
    stdout, error = _run(repo, args + [commit, "--", path], "git blame", timeout)
    if error:
        return error
    info: dict[str, dict[str, str]] = {}
    owned: dict[str, list[int]] = {}
    sha = None
    for line in stdout.splitlines():
        header = _BLAME_HEADER.fullmatch(line)
        if header:
            sha = header.group(1)
            info.setdefault(sha, {})
            owned.setdefault(sha, []).append(int(header.group(2)))
        elif sha and not line.startswith("\t"):
            key, _, value = line.partition(" ")
            info[sha].setdefault(key, value)
    records = tuple(
        CommitRecord(sha=s, author=info[s]["author"],
                     date=_author_date(info[s]["author-time"], info[s]["author-tz"]),
                     subject=info[s]["summary"])
        for s in owned)
    text = "\n".join(_render(r, "lines " + _ranges(owned[r.sha])) for r in records)
    return ToolOutput(text=text, commits=records)
