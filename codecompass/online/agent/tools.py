"""Agent tools: git blame, git log, open_file, search_again; read-only, validated (V.2)."""

from __future__ import annotations

import posixpath
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from codecompass.online.context import RetrievedChunk, format_chunk, format_context

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
    """Rendered text for the model plus the evidence it carries (Plan D7, D18).

    commits: parsed commit records (git tools). chunks: code the model was shown
    (open_file, search_again), so the citation checker can verify it (VI.4).
    """
    text: str
    commits: tuple[CommitRecord, ...] = ()
    error: bool = False
    chunks: tuple[RetrievedChunk, ...] = ()


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


def git_log(repo, commit: str, path, n, *, limit: int, timeout: float) -> ToolOutput:
    """Commits touching *path* up to *commit*, newest first (Plan D7)."""
    path = validate_path(repo, commit, path)
    count = validate_n(n, limit)
    stdout, error = _run(
        repo, ["log", "--format=%H%x1f%an%x1f%ad%x1f%s", "--date=short",
               "-n", str(count), commit, "--", path], "git log", timeout)
    if error:
        return error
    records = tuple(CommitRecord(*line.split("\x1f", 3))
                    for line in stdout.splitlines() if line)
    if not records:
        return ToolOutput(text=f"no commits found for {path}")
    return ToolOutput(text="\n".join(_render(r) for r in records), commits=records)


_LANGUAGES = {".py": "python", ".js": "javascript", ".jsx": "javascript",
              ".ts": "typescript", ".java": "java"}


def _language(path: str) -> str:
    return _LANGUAGES.get(posixpath.splitext(path)[1].lower(), "text")


def _file_lines(repo, commit: str, path: str) -> list[str]:
    """The file's lines at *commit*, read from git (never the working tree)."""
    proc = subprocess.run(["git", "cat-file", "-p", f"{commit}:{path}"], cwd=repo,
                          capture_output=True, shell=False, check=False)
    return proc.stdout.decode("utf-8", errors="replace").splitlines()


def _outline(commit: str, path: str, entries) -> ToolOutput:
    """Indexed symbols with line ranges; not code, so nothing citable (Plan D18)."""
    if not entries:
        return ToolOutput(text=(
            f"No outline available for {path} at {commit[:7]}. Ask for a line range "
            f'instead, e.g. open_file(path="{path}", lines="1-60").'))
    rows = "\n".join(f"  {name}  lines {start}-{end}" for name, start, end in entries)
    return ToolOutput(text=(f"Outline of {path} (indexed at {commit[:7]}):\n{rows}\n"
                            f'Read code with open_file(path="{path}", lines="X-Y").'))


def open_file(repo, commit: str, path, lines=None, *, max_tokens: int, count_tokens,
              symbols=None) -> ToolOutput:
    """Lines of *path* at *commit* as a citable chunk, or an outline (Plan D18).

    A range that does not fit *max_tokens* is cut to whole lines from its start,
    with a marker saying how to continue; the chunk covers only the lines shown.
    """
    path = validate_path(repo, commit, path)
    if lines is None:
        return _outline(commit, path, symbols(path) if symbols else [])
    text_lines = _file_lines(repo, commit, path)
    start, end = validate_lines(lines, len(text_lines))

    def shown(last: int) -> tuple[RetrievedChunk, str]:
        chunk = RetrievedChunk(
            chunk_id=f"open_file:{path}:{start}-{last}",
            text="\n".join(text_lines[start - 1:last]), path=path, start_line=start,
            end_line=last, language=_language(path), commit_sha=commit)
        body = format_chunk(chunk)
        if last < end:
            body += (f"\n[showing lines {start}-{last}; "
                     f"ask for lines {last + 1}-{end} to continue]")
        return chunk, body

    best = None
    for last in range(start, end + 1):
        chunk, body = shown(last)
        if count_tokens(body) > max_tokens:
            break
        best = (chunk, body)
    if best is None:
        return ToolOutput(text=(f"error: line {start} of {path} alone does not fit the "
                                "tool output limit"), error=True)
    return ToolOutput(text=best[1], chunks=(best[0],))


MAX_QUERY_CHARS = 200


def validate_query(query) -> str:
    """A non-empty search query of at most MAX_QUERY_CHARS characters (V.2)."""
    if not isinstance(query, str) or not query.strip():
        raise ToolArgumentError("query must be a non-empty string")
    if len(query) > MAX_QUERY_CHARS:
        raise ToolArgumentError(
            f"query must be at most {MAX_QUERY_CHARS} characters, got {len(query)}")
    return query.strip()


def search_again(handles, query, *, seen, reranker, config, max_tokens: int,
                 count_tokens) -> ToolOutput:
    """New chunks for a model-written query, re-ranked, within the cap (Plan D18).

    Uses the same hybrid retrieval and re-ranker as the first search (Article IV),
    skips chunk ids in *seen*, and keeps chunks in re-rank order while they fit.
    """
    from codecompass.online.retrieval.hybrid import retrieve
    from codecompass.online.retrieval.reranker import rerank_chunks

    query = validate_query(query)
    ids = [cid for cid, _ in retrieve(handles, query, config=config) if cid not in seen]
    records = handles.vector.records_for_ids(ids) if ids else {}
    chunks = [RetrievedChunk.from_record(cid, records[cid]) for cid in ids if cid in records]
    if not chunks:
        return ToolOutput(text=(f"Nothing new found for {query!r}: every match is already "
                                "in the context above."))
    ranked = [chunk for chunk, _ in rerank_chunks(reranker, query, chunks, len(chunks))]
    kept: list[RetrievedChunk] = []
    for chunk in ranked:
        if count_tokens(format_context(kept + [chunk])) > max_tokens:
            break
        kept.append(chunk)
    if not kept:
        best = ranked[0]
        return ToolOutput(text=(
            f"The best new match, {best.path} lines {best.start_line}-{best.end_line}, "
            "is too large to show here. Read part of it with "
            f'open_file(path="{best.path}", lines="{best.start_line}-{best.end_line}").'))
    return ToolOutput(text=format_context(kept), chunks=tuple(kept))


# The dispatch table is the allow list (Article V.2): config cannot widen it.
_PARAMS = {"git_blame": {"path", "lines"}, "git_log": {"path", "n"}}
ALLOWED_TOOLS = tuple(_PARAMS)


def execute(repo, commit: str, call, *, settings) -> ToolOutput:
    """Run one allow-listed tool call; bad model input becomes an error output."""
    if call.tool not in _PARAMS:
        return ToolOutput(
            text=f"error: tool {call.tool!r} is not allowed; "
                 f"available tools: {', '.join(ALLOWED_TOOLS)}",
            error=True)
    if call.tool not in settings.allowed_tools:
        return ToolOutput(
            text=f"error: tool {call.tool!r} is switched off in configuration; "
                 f"available tools: {', '.join(settings.allowed_tools) or 'none'}",
            error=True)
    unexpected = sorted(set(call.args) - _PARAMS[call.tool])
    if unexpected:
        return ToolOutput(
            text=f"error: unexpected argument(s) for {call.tool}: {', '.join(unexpected)}",
            error=True)
    args = call.args
    try:
        if call.tool == "git_blame":
            return git_blame(repo, commit, args.get("path"), args.get("lines"),
                             timeout=settings.git_blame_timeout)
        return git_log(repo, commit, args.get("path"),
                       args.get("n", settings.git_log_limit),
                       limit=settings.git_log_limit, timeout=settings.git_log_timeout)
    except ToolArgumentError as exc:
        return ToolOutput(text=f"error: {exc}", error=True)


def cap_output(output: ToolOutput, max_tokens: int, count_tokens) -> ToolOutput:
    """Keep whole lines within *max_tokens* and mark the cut (Plan D4).

    Commits whose line was cut are dropped, so only what the model saw is
    citable.
    """
    if count_tokens(output.text) <= max_tokens:
        return output
    lines = output.text.splitlines()
    kept: list[str] = []
    used = count_tokens(f"[output truncated: {len(lines)} more lines]")
    for line in lines:
        cost = count_tokens(line)
        if used + cost > max_tokens:
            break
        kept.append(line)
        used += cost
    marker = f"[output truncated: {len(lines) - len(kept)} more lines]"
    text = "\n".join(kept + [marker])
    commits = tuple(c for c in output.commits if c.sha[:7] in text)
    # A cut code block no longer matches its chunk, so it is not citable (VI.4).
    return ToolOutput(text=text, commits=commits, error=output.error)
