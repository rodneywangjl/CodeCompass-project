"""Core data models: Chunk, ChangeSet, IndexMeta, RunReport (AC-3.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 1


class ChunkMode(Enum):
    STRUCTURED = "structured"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    path: str  # repo-relative, forward slashes
    start_line: int
    end_line: int
    language: str
    symbol: str | None
    commit_sha: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("chunk id is required")
        if not self.path or self.path.startswith("/") or "\\" in self.path:
            raise ValueError(f"chunk path must be repo-relative with forward slashes: {self.path!r}")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError(f"invalid chunk line range: {self.start_line}-{self.end_line}")
        if not self.language:
            raise ValueError("chunk language is required")
        if not self.commit_sha:
            raise ValueError("chunk commit_sha is required")


@dataclass(frozen=True)
class ChangeSet:
    added: list = field(default_factory=list)
    modified: list = field(default_factory=list)
    deleted: list = field(default_factory=list)


@dataclass(frozen=True)
class EmbedderIdentity:
    model: str
    revision: str
    dimension: int


@dataclass(frozen=True)
class IndexMeta:
    schema_version: int
    embedder: EmbedderIdentity
    indexed_commit: str | None
    last_run_at: str | None = None
    config_fingerprint: str = ""
    in_progress: dict | None = None


@dataclass(frozen=True)
class RunReport:
    mode: str  # full | incremental | up-to-date | rebuild
    to_commit: str | None = None
    from_commit: str | None = None
    note: str = ""  # why this mode (e.g. rebuild reason)
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0
    files_skipped: int = 0
    skipped_by_rule: dict = field(default_factory=dict)
    files_fallback: int = 0
    files_non_code: int = 0
    chunks_added: int = 0
    chunks_removed: int = 0
    embedder_model: str = ""
    embedder_revision: str = ""
    schema_version: int = SCHEMA_VERSION
    elapsed_seconds: float = 0.0
    timings: dict = field(default_factory=dict)
