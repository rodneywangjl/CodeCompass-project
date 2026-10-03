"""Indexing orchestration: one code path for full and incremental runs (plan §1).

A full build is an incremental run from an empty index, so AC-2.6 holds by
construction. The recorded commit advances only after both stores are done.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .chunking import chunk_file
from .chunking.ids import text_hash
from .exclusions import decide_for_source
from .git_source import GitSource
from .lock import acquire_lock
from .meta import check_compatible, default_meta, read_meta, write_meta
from .models import RunReport
from .stores.keyword import KeywordIndex
from .stores.vector import VectorStore


def repo_id(repo_path) -> str:
    """Stable repository identifier (spec C4)."""
    return hashlib.sha1(str(Path(repo_path).resolve()).encode()).hexdigest()[:16]


def index_path_for(repo_path, base_dir) -> Path:
    return Path(base_dir) / repo_id(repo_path)


def config_fingerprint(config) -> str:
    material = json.dumps({
        "chunking": [config.chunking.target_tokens, config.chunking.hard_max_tokens],
        "files": [config.files.max_file_bytes, list(config.files.source_extensions),
                  list(config.files.exclude_patterns), list(config.files.exclude_dirs)],
        "embedder": [config.embedder.model, config.embedder.revision,
                     config.embedder.dimension],
    }, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def run(repo_path, *, config, index_dir=None, embedder=None,
        embedder_factory=None) -> RunReport:
    """Bring the index to HEAD; return a run report. Raises on failure."""
    started = datetime.now(timezone.utc)
    timings: dict[str, float] = {}
    src = GitSource(repo_path)  # validates before creating anything
    head = src.head_sha()
    base_dir = Path(index_dir) if index_dir is not None else Path(config.index.dir)
    idx = index_path_for(repo_path, base_dir)

    meta_path = idx / "meta.json"
    meta = read_meta(idx) if meta_path.exists() else None
    if meta is not None and meta.indexed_commit == head and meta.in_progress is None:
        return RunReport(mode="up-to-date", from_commit=head, to_commit=head)

    with acquire_lock(idx / "index.lock", config.lock.timeout_seconds):
        meta = read_meta(idx) if meta_path.exists() else None
        if meta is not None and meta.indexed_commit == head and meta.in_progress is None:
            return RunReport(mode="up-to-date", from_commit=head, to_commit=head)

        if embedder is None:
            if embedder_factory is None:
                raise ValueError("no embedder available")
            embedder = embedder_factory()
        if meta is None:
            meta = default_meta(embedder.identity, config_fingerprint(config))
        check_compatible(meta, embedder.identity)

        if meta.indexed_commit and src.is_ancestor(meta.indexed_commit, head):
            base_commit: str | None = meta.indexed_commit
            mode = "incremental"
        else:
            base_commit = None
            mode = "full" if meta.indexed_commit is None else "rebuild"

        changeset = src.diff(base_commit, head)
        touched = set(changeset.added) | set(changeset.modified) | set(changeset.deleted)
        if meta.in_progress:
            touched |= set(meta.in_progress.get("touched_paths", []))
        touched = sorted(touched)

        meta = meta.__class__(**{**meta.__dict__, "in_progress": {
            "target_commit": head, "touched_paths": touched}})
        write_meta(idx, meta)

        from .exclusions import Decision, decide

        def classify(path: str):
            """Path rules + size gate without reading content; one read after."""
            quick = decide(path, config.files)
            if not quick.included:
                return quick, None
            if src.blob_size(head, path) > config.files.max_file_bytes:
                return Decision(False, "too-large"), None
            blob = src.read_blob(head, path)
            if b"\x00" in blob[:8192]:
                return Decision(False, "binary"), None
            return Decision(True, "include"), blob

        decisions: dict[str, object] = {}
        blobs: dict[str, bytes] = {}
        for path in sorted(set(changeset.added) | set(changeset.modified)):
            decision, blob = classify(path)
            decisions[path] = decision
            if blob is not None:
                blobs[path] = blob
        for path in sorted(set(changeset.deleted) | set(changeset.added) |
                           set(changeset.modified)):
            decisions.setdefault(path, Decision(True, "include"))
        included = sorted(blobs)

        vector_store = VectorStore(idx / "vector", dimension=embedder.identity.dimension)
        keyword_index = KeywordIndex(idx / "keyword")

        before = vector_store.paths_for_ids(vector_store.ids())
        stale = sorted({c for c, p in before.items() if p in touched})
        chunks_removed = len(stale)

        chunks_added = 0
        files_fallback = 0
        batch_size = config.chunking.batch_files or len(included) or 1
        reuse = vector_store.vectors_for_paths(touched)
        # Phase 1: remove stale chunks first. The keyword delete is committed
        # before any insert because delete tombstones would otherwise also
        # remove documents added later in the same run.
        delete_paths = sorted(set(included) | {before[c] for c in stale})
        if delete_paths:
            vector_store.delete_paths(delete_paths)
            keyword_index.delete_paths(delete_paths)
            keyword_index.commit()
        for i in range(0, len(included), batch_size):
            batch = included[i:i + batch_size]
            new_chunks = []
            for path in batch:
                text = blobs[path].decode("utf-8", "replace")
                chunks, m = chunk_file(path, text, head)
                from .models import ChunkMode
                if m is ChunkMode.FALLBACK:
                    files_fallback += 1
                new_chunks.extend(chunks)
            pending = [c for c in new_chunks if text_hash(c.text) not in reuse]
            if pending:
                from .embedding import embed_in_batches
                for chunk, vector in zip(pending, embed_in_batches(
                        embedder, [c.text for c in pending],
                        config.embedder.batch_size)):
                    reuse.setdefault(text_hash(chunk.text), vector)
            vectors = [reuse[text_hash(c.text)] for c in new_chunks]
            if new_chunks:
                vector_store.add(new_chunks, vectors)
                keyword_index.add(new_chunks)
                chunks_added += len(new_chunks)
        if chunks_added:
            keyword_index.commit()
        elif not delete_paths:
            keyword_index.close()
        vector_store.restamp_commit_sha(head)

        finished = datetime.now(timezone.utc)
        meta = meta.__class__(**{**meta.__dict__, "indexed_commit": head,
                                 "last_run_at": finished.isoformat(),
                                 "in_progress": None})
        write_meta(idx, meta)
        elapsed = (finished - started).total_seconds()
        return RunReport(
            mode=mode, from_commit=base_commit, to_commit=head,
            files_added=len(changeset.added), files_modified=len(changeset.modified),
            files_deleted=len(changeset.deleted),
            files_skipped=sum(1 for p, d in decisions.items()
                              if not d.included and d.reason != "non-code"),
            files_non_code=sum(1 for d in decisions.values() if d.reason == "non-code"),
            files_fallback=files_fallback,
            chunks_added=chunks_added, chunks_removed=chunks_removed,
            embedder_model=embedder.identity.model,
            embedder_revision=embedder.identity.revision,
            elapsed_seconds=elapsed, timings=timings,
        )
