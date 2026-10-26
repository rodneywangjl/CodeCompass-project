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


def _tool_reserve(tools) -> int:
    return tools.max_verifier_rounds * tools.max_tool_output_tokens


def chunk_budget(profile, tools, prefix_tokens: int) -> int:
    """Tokens left for chunks once the answer, prompt and tool rounds are reserved (Plan D4)."""
    return (profile.context_window - profile.max_tokens - prefix_tokens
            - _tool_reserve(tools))


def fit_chunks(chunks: list[RetrievedChunk], budget: int, count_tokens) -> list[RetrievedChunk]:
    """Chunks in order while each formatted block fits; the first misfit ends it."""
    kept: list[RetrievedChunk] = []
    used = 0
    for chunk in chunks:
        cost = count_tokens(format_chunk(chunk))
        if used + cost > budget:
            break
        kept.append(chunk)
        used += cost
    return kept


def check_round_reserve(profile, tools, system_tokens: int) -> None:
    """Fail loudly when the configured tool rounds leave no room for chunks."""
    room = profile.context_window - profile.max_tokens - system_tokens - _tool_reserve(tools)
    if room <= 0:
        raise ValueError(
            f"tools.max_verifier_rounds={tools.max_verifier_rounds} reserves "
            f"{_tool_reserve(tools)} tokens for tool results, leaving no room for "
            f"retrieved code in a {profile.context_window}-token context window "
            "(Article V.1)")
