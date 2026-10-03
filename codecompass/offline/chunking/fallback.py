"""Line-window fallback chunker (AC-3.4, AC-3.5)."""

from __future__ import annotations

from .ids import chunk_id
from .sizing import SizePolicy, classify_size, count_tokens
from codecompass.offline.models import Chunk, ChunkMode


def _language_for(path: str) -> str:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return "unknown"


def chunk(path: str, content: str, commit_sha: str, *,
          language: str | None = None,
          policy: SizePolicy | None = None,
          tokenizer=None) -> tuple[list[Chunk], ChunkMode]:
    """Chunk by line windows near the target size, preferring blank breaks."""
    policy = policy or SizePolicy()
    tokenizer = tokenizer or (lambda s: s.split())
    language = language or _language_for(path)
    if content == "":
        return [], ChunkMode.FALLBACK
    # Keep lines raw (including any \r) so text == file content at [start, end].
    lines = content.split("\n")
    # Drop the artifact after a trailing newline so ranges stay accurate.
    if lines and lines[-1] == "" and content.endswith("\n"):
        lines.pop()
    chunks: list[Chunk] = []
    occurrence = 0

    def take(start: int, end: int, text: str | None = None):
        nonlocal occurrence
        text = "\n".join(lines[start - 1:end]) if text is None else text
        chunks.append(Chunk(
            id=chunk_id(path, None, occurrence, text),
            text=text, path=path, start_line=start, end_line=end,
            language=language, symbol=None, commit_sha=commit_sha,
        ))
        occurrence += 1

    def tokens_of(start: int, end: int) -> int:
        return count_tokens("\n".join(lines[start - 1:end]), tokenizer)

    cur = 1
    total = len(lines)
    while cur <= total:
        nxt = cur
        while nxt <= total:
            state = classify_size(tokens_of(cur, nxt), policy)
            if state == "fits":
                nxt += 1
            elif state == "over_target":
                break_at = max(nxt - 1, cur)
                for back in range(nxt - 1, cur - 1, -1):
                    if lines[back - 1].strip() == "":
                        break_at = back
                        break
                nxt = break_at
                break
            else:  # over_hard_max: force a cut at a line boundary
                break
        if nxt == cur:
            nxt = cur  # single line at/over hard max: split the line itself
            words = tokenizer(lines[cur - 1])
            if len(words) > policy.hard_max_tokens:
                budget = policy.hard_max_tokens
                pieces = [" ".join(words[i:i + budget])
                          for i in range(0, len(words), budget)]
                for piece in pieces:
                    take(cur, cur, piece)
                cur += 1
                continue
        take(cur, nxt)
        cur = nxt + 1
    return chunks, ChunkMode.FALLBACK
