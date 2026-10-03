"""Public offline-pipeline API (Article II.2).

Only these names are exported to the online pipeline. `ensure_current` is the
single write-capable entry point; everything else is read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .git_source import GitSource
from .meta import read_meta
from .orchestrator import index_path_for

__all__ = ["ensure_current", "status", "open_index", "check_consistency"]


@dataclass(frozen=True)
class IndexStatus:
    state: str  # empty | current | stale
    indexed_commit: str | None
    head_commit: str
    schema_version: int | None = None
    embedder_model: str | None = None
    embedder_revision: str | None = None
    embedder_dimension: int | None = None
    last_run_at: str | None = None
    config_fingerprint: str | None = None


def _base_dir(config, index_dir):
    return Path(index_dir) if index_dir is not None else Path(config.index.dir)


def status(repo_path, *, config, index_dir=None) -> IndexStatus:
    """Read-only index state: empty, current, or stale (AC-5.2). Makes no writes."""
    src = GitSource(repo_path)
    head = src.head_sha()
    meta_path = index_path_for(repo_path, _base_dir(config, index_dir)) / "meta.json"
    if not meta_path.exists():
        return IndexStatus(state="empty", indexed_commit=None, head_commit=head)
    meta = read_meta(meta_path.parent)
    state = "current" if meta.indexed_commit == head else "stale"
    return IndexStatus(
        state=state, indexed_commit=meta.indexed_commit, head_commit=head,
        schema_version=meta.schema_version, embedder_model=meta.embedder.model,
        embedder_revision=meta.embedder.revision,
        embedder_dimension=meta.embedder.dimension,
        last_run_at=meta.last_run_at,
        config_fingerprint=meta.config_fingerprint,
    )
