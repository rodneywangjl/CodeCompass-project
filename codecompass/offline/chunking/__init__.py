"""Chunking dispatcher: tree-sitter when a grammar exists, fallback otherwise."""

from __future__ import annotations

from . import fallback, treesitter
from .registry import language_for_path


def chunk_file(path: str, content: str, commit_sha: str, *,
               policy=None, tokenizer=None):
    """Chunk one file, never failing the run (AC-3.4, AC-3.5)."""
    if language_for_path(path) is None:
        return fallback.chunk(path, content, commit_sha,
                              policy=policy, tokenizer=tokenizer)
    if content == "":
        from codecompass.offline.models import ChunkMode
        return [], ChunkMode.STRUCTURED
    try:
        chunks, mode = treesitter.chunk(path, content, commit_sha,
                                        policy=policy, tokenizer=tokenizer)
    except Exception:
        return fallback.chunk(path, content, commit_sha,
                              policy=policy, tokenizer=tokenizer)
    if mode is treesitter.ChunkMode.FALLBACK or not chunks:
        if not chunks:
            return fallback.chunk(path, content, commit_sha,
                                  policy=policy, tokenizer=tokenizer)
        return chunks, mode
    return chunks, mode
