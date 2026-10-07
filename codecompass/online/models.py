"""Core data models for the online query pipeline (Plan §4, §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceEntry:
    """A citation source entry parsed from the answer's Sources section."""
    kind: str  # "code" or "commit"
    marker: int
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    commit: str | None = None
    subject: str | None = None
    author: str | None = None
    date: str | None = None
    verified: bool = False


@dataclass(frozen=True)
class ToolCall:
    """A parsed tool-call request from the generator."""
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """The executed output of a tool call."""
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    output: str = ""
    cache_hit: bool = False


@dataclass(frozen=True)
class CitationResult:
    """The outcome of deterministic citation verification (Article VI)."""
    outcome: str  # "F" (cited) or "G" (flagged)
    sources: list[SourceEntry] = field(default_factory=list)
    unverified: list[int] = field(default_factory=list)
    answer_text: str = ""
    banner: str | None = None


@dataclass(frozen=True)
class QueryResult:
    """The structured result returned by the public ask() API (AC-9.1)."""
    answer: str
    sources: list[SourceEntry] = field(default_factory=list)
    citation_outcome: str = "F"  # "F" or "G"
    stale_index: bool = False
    stale_message: str = ""
    audit_log: dict[str, Any] = field(default_factory=dict)
