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

        decisions = {p: decide_for_source(p, config.files, src, head) for p in touched}
        included = sorted(p for p, d in decisions.items() if d.included)

        vector_store = VectorStore(idx / "vector", dimension=embedder.identity.dimension)
        keyword_index = KeywordIndex(idx / "keyword")

        before = vector_store.paths_for_ids(vector_store.ids())
        stale = sorted({c for c, p in before.items() if p in touched})
        chunks_removed = len(stale)

        chunks_added = 0
        files_fallback = 0
        batch_size = config.chunking.batch_files or len(included) or 1
        reuse = vector_store.vectors_for_paths(touched)
        for i in range(0, len(included), batch_size):
            batch = included[i:i + batch_size]
            vector_store.delete_paths(batch)
            keyword_index.delete_paths(batch)
            new_chunks = []
            for path in batch:
                blob = src.read_blob(head, path)
                text = blob.decode("utf-8", "replace")
                chunks, m = chunk_file(path, text, head)
                from .models import ChunkMode
                if m is ChunkMode.FALLBACK:
                    files_fallback += 1
                new_chunks.extend(chunks)
            pending = [c for c in new_chunks if text_hash(c.text) not in reuse]
            if pending:
                order = sorted(range(len(pending)), key=lambda k: len(pending[k].text))
                got: dict[int, list[float]] = {}
                step = config.embedder.batch_size or len(pending)
                for j in range(0, len(order), step):
                    slot = order[j:j + step]
                    vecs = embedder.embed([pending[k].text for k in slot])
                    for k, v in zip(slot, vecs):
                        got[k] = v
                for k, c in enumerate(pending):
                    reuse.setdefault(text_hash(c.text), got[k])
            vectors = [reuse[text_hash(c.text)] for c in new_chunks]
            if new_chunks:
                vector_store.add(new_chunks, vectors)
                keyword_index.add(new_chunks)
                chunks_added += len(new_chunks)
        if stale:
            vector_store.delete_paths(sorted({before[c] for c in stale}))
            keyword_index.delete_paths(sorted({before[c] for c in stale}))
        dirty = bool(chunks_added or chunks_removed or included)
        if dirty:
            keyword_index.commit()
        else:
            keyword_index.close()

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
