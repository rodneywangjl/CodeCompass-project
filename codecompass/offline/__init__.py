"""Public offline-pipeline API (Article II.2).

Only these names are exported to the online pipeline. `ensure_current` is the
single write-capable entry point; everything else is read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .git_source import GitSource
from .lock import LockTimeout
from .meta import (
    EmbedderIdentity,
    check_compatible,
    config_fingerprint,
    index_path_for,
    read_meta,
)
__all__ = ["ensure_current", "status", "open_index", "check_consistency"]


def __getattr__(name: str):
    """Lazily re-export the consistency check without importing stores (O1)."""
    if name == "check_consistency":
        from .stores.consistency import check_consistency
        return check_consistency
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True)
class EnsureResult:
    ok: bool
    status: str  # current | failed | locked
    report: object = None
    message: str = ""


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


def ensure_current(repo_path, *, config, index_dir=None, embedder=None,
                   embedder_factory=None) -> EnsureResult:
    """Online pipeline's single write-capable entry (AC-5.6, Article II.2).

    Fast path (O1): when the index is already current, compare commits only:
    no lock, no source reads, no store/model imports, no writes. Otherwise run
    an incremental update. Never blocks indefinitely: lock waits time out.
    """
    from .models import RunReport
    src = GitSource(repo_path)
    head = src.head_sha()
    idx = index_path_for(repo_path, _base_dir(config, index_dir))
    meta_path = idx / "meta.json"
    if meta_path.exists():
        meta = read_meta(idx)
        if (meta.indexed_commit == head and meta.in_progress is None
                and meta.config_fingerprint == config_fingerprint(config)):
            return EnsureResult(
                ok=True, status="current",
                report=RunReport(mode="up-to-date", from_commit=head,
                                 to_commit=head))
    from .orchestrator import run  # heavy imports only on the stale path
    if embedder is None and embedder_factory is None:
        def embedder_factory():  # the configured embedder, as open_index uses
            from . import embedding
            return embedding.CodeEmbedder(config.embedder)
    try:
        report = run(repo_path, config=config, index_dir=index_dir,
                     embedder=embedder, embedder_factory=embedder_factory)
    except LockTimeout as e:
        return EnsureResult(ok=False, status="locked", message=str(e))
    except Exception as e:  # noqa: BLE001 (AC-5.8: fail safe, index stays usable)
        return EnsureResult(ok=False, status="failed", message=str(e))
    return EnsureResult(ok=True, status="current", report=report)


class ReadOnlyVectorStore:
    """Read-only facade over the vector store (Article II.2, AC-5.5)."""

    def __init__(self, store) -> None:
        self._store = store

    def ids(self) -> set:
        return self._store.ids()

    def count(self) -> int:
        return self._store.count()

    def search(self, vector, limit: int) -> list:
        return self._store.search(vector, limit)

    def records_for_ids(self, ids) -> dict:
        return self._store.records_for_ids(ids)

    def paths_for_ids(self, ids) -> dict:
        return self._store.paths_for_ids(ids)

    def vectors_for_paths(self, paths) -> dict:
        return self._store.vectors_for_paths(paths)

    def symbols_for_path(self, path) -> list:
        return self._store.symbols_for_path(path)

    def close(self) -> None:
        self._store = None  # type: ignore[assignment]


class ReadOnlyKeywordIndex:
    """Read-only facade over the keyword index (Article II.2, AC-5.5)."""

    def __init__(self, store) -> None:
        self._store = store

    def ids(self) -> set:
        return self._store.ids()

    def search(self, text: str, limit: int) -> list:
        return self._store.search(text, limit)

    def paths_for_ids(self, ids) -> dict:
        return self._store.paths_for_ids(ids)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None  # type: ignore[assignment]


@dataclass(frozen=True)
class IndexHandles:
    vector: ReadOnlyVectorStore
    keyword: ReadOnlyKeywordIndex
    meta: object = None
    embedder: object = None

    def embed_query(self, text: str) -> list:
        """Embed a question with the index's own embedder (Article II.4)."""
        return self.embedder.embed([text])[0]

    def close(self) -> None:
        self.keyword.close()
        self.vector.close()


def open_index(repo_path, *, config, index_dir=None,
               embedder=None) -> IndexHandles:
    """Read-only handles to both indexes with compatibility checks (AC-5.5).

    Refuses mismatched embedder identity (AC-5.3) and unknown schema (AC-5.4).
    The query embedder (default: the pinned one from config, loaded lazily) is
    attached to the handles; config and embedder must both match the index.
    """
    from .embedding import CodeEmbedder
    from .stores.keyword import KeywordIndex
    from .stores.vector import VectorStore
    idx = index_path_for(repo_path, _base_dir(config, index_dir))
    meta = read_meta(idx)  # raises SchemaMismatchError / FileNotFoundError
    check_compatible(meta, EmbedderIdentity(
        model=config.embedder.model, revision=config.embedder.revision,
        dimension=config.embedder.dimension))
    if embedder is None:
        embedder = CodeEmbedder(config.embedder)
    check_compatible(meta, embedder.identity)
    return IndexHandles(
        vector=ReadOnlyVectorStore(VectorStore(
            idx / "vector", dimension=meta.embedder.dimension)),
        keyword=ReadOnlyKeywordIndex(KeywordIndex(idx / "keyword")),
        meta=meta,
        embedder=embedder,
    )
