"""Context assembly: retrieved chunks as plain text with metadata (Article IV.4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """A retrieved chunk as the generator may see it: text and metadata, no vector."""
    chunk_id: str
    text: str
    path: str
    start_line: int
    end_line: int
    language: str
    commit_sha: str

    @classmethod
    def from_record(cls, chunk_id: str, record: dict) -> RetrievedChunk:
        meta = record["metadata"]
        return cls(
            chunk_id=chunk_id, text=record["text"], path=meta["file_path"],
            start_line=meta["start_line"], end_line=meta["end_line"],
            language=meta["language"], commit_sha=meta["commit_sha"],
        )


def citation_label(chunk: RetrievedChunk) -> str:
    """The chunk in the fixed Sources code-citation form (Article VI.4)."""
    return (f"{chunk.path}, lines {chunk.start_line}-{chunk.end_line} "
            f"(indexed at {chunk.commit_sha[:7]})")


def format_chunk(chunk: RetrievedChunk) -> str:
    """Header the model can copy as a citation, then the chunk text (Plan D3)."""
    return f"--- {citation_label(chunk)} | {chunk.language} ---\n{chunk.text}"


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(format_chunk(c) for c in chunks)
