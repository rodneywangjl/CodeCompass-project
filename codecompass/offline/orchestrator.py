"""Indexing orchestration: one code path for full and incremental runs (plan §1).

A full build is an incremental run from an empty index, so AC-2.6 holds by
construction. The recorded commit advances only after both stores are done.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .chunking import chunk_file
from .chunking.ids import text_hash
from .git_source import GitSource
from .lock import acquire_lock
from .meta import (
    check_compatible,
    config_fingerprint,
    default_meta,
    index_path_for,
    read_meta,
    repo_id,  # noqa: F401  (re-exported for existing callers)
    write_meta,
)
from .models import RunReport
from .stores.keyword import KeywordIndex
from .stores.vector import VectorStore

# index_path_for / config_fingerprint are defined in .meta and re-exported
# here so existing callers keep working.
__all__ = ["run", "index_path_for", "repo_id", "config_fingerprint"]


def _compute_plan(src, meta, head, current_fp):
    """Shared read-only planning: base commit, mode label, touched paths."""
    if (meta is not None and meta.indexed_commit
            and src.is_ancestor(meta.indexed_commit, head)
            and meta.config_fingerprint == current_fp):
        base_commit: str | None = meta.indexed_commit
        mode = "incremental"
        note = ""
    else:
        base_commit = None
        if meta is None or meta.indexed_commit is None:
            mode, note = "full", ""
        elif meta.config_fingerprint != current_fp:
            mode = "rebuild"
            note = "indexing configuration changed; full rebuild"
        else:
            mode = "rebuild"
            note = ("recorded commit is not reachable from HEAD "
                    "(history rewritten or unresolvable); full rebuild")
    changeset = src.diff(base_commit, head)
    touched = set(changeset.added) | set(changeset.modified) | set(changeset.deleted)
    if meta is not None and meta.in_progress:
        touched |= set(meta.in_progress.get("touched_paths", []))
    return base_commit, mode, note, changeset, sorted(touched)


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
    current_fp_early = config_fingerprint(config)
    if (meta is not None and meta.indexed_commit == head
            and meta.in_progress is None
            and meta.config_fingerprint == current_fp_early):
        return RunReport(mode="up-to-date", from_commit=head, to_commit=head)

    with acquire_lock(idx / "index.lock", config.lock.timeout_seconds):
        meta = read_meta(idx) if meta_path.exists() else None
        if (meta is not None and meta.indexed_commit == head
                and meta.in_progress is None
                and meta.config_fingerprint == config_fingerprint(config)):
            return RunReport(mode="up-to-date", from_commit=head, to_commit=head)

        if embedder is None:
            if embedder_factory is None:
                raise ValueError("no embedder available")
            embedder = embedder_factory()
        if meta is None:
            meta = default_meta(embedder.identity, config_fingerprint(config))
        check_compatible(meta, embedder.identity)
        current_fp = config_fingerprint(config)
        base_commit, mode, note, changeset, touched = _compute_plan(
            src, meta, head, current_fp)

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
        deleted = set(changeset.deleted)
        t_classify = perf_counter()
        for path in sorted(set(touched) - deleted):
            decision, blob = classify(path)
            decisions[path] = decision
            if blob is not None:
                blobs[path] = blob
        timings["classify"] = perf_counter() - t_classify
        for path in sorted(set(touched)):
            decisions.setdefault(path, Decision(True, "include"))
        included = sorted(blobs)

        vector_store = VectorStore(idx / "vector", dimension=embedder.identity.dimension)
        keyword_index = KeywordIndex(idx / "keyword")

        before = vector_store.paths_for_ids(vector_store.ids())
        stale = sorted({c for c, p in before.items() if p in touched})
        chunks_removed = len(stale)

        reuse = vector_store.vectors_for_paths(touched)
        # Phase A (pure compute): chunk every included file. No store has been
        # touched yet, so a failure here leaves the index unchanged (T8.3).
        from .chunking.sizing import SizePolicy
        policy = SizePolicy(target_tokens=config.chunking.target_tokens,
                            hard_max_tokens=config.chunking.hard_max_tokens)
        from .models import ChunkMode
        # Size chunks with the embedder's own tokenizer when it has one (spec C7,
        # AC-3.3); without one the chunkers count whitespace words.
        tokenizer = getattr(embedder, "tokenize", None)
        new_chunks = []
        files_fallback = 0
        t_chunk = perf_counter()
        for path in included:
            text = blobs[path].decode("utf-8", "replace")
            chunks, m = chunk_file(path, text, head, policy=policy,
                                   tokenizer=tokenizer)
            if m is ChunkMode.FALLBACK:
                files_fallback += 1
            new_chunks.extend(chunks)
        timings["chunk"] = perf_counter() - t_chunk
        # Phase B (pure compute): embed everything new. Still no mutations,
        # so an embedding failure returns with the existing index untouched.
        # Vectors for the whole run are held in memory; bounded-memory
        # batching (O9) is revisited with measurements per C6.
        pending = [c for c in new_chunks if text_hash(c.text) not in reuse]
        t_embed = perf_counter()
        if pending:
            from .embedding import embed_in_batches
            for chunk, vector in zip(pending, embed_in_batches(
                    embedder, [c.text for c in pending],
                    config.embedder.batch_size,
                    config.embedder.max_batch_cost)):
                reuse.setdefault(text_hash(chunk.text), vector)
        timings["embed"] = perf_counter() - t_embed
        vectors = [reuse[text_hash(c.text)] for c in new_chunks]
        chunks_added = len(new_chunks)
        t_store = perf_counter()
        # Phase C (mutation): remove stale chunks first. The keyword delete is
        # committed before any insert because delete tombstones would
        # otherwise also remove documents added later in the same run.
        delete_paths = sorted(set(included) | {before[c] for c in stale})
        if delete_paths:
            vector_store.delete_paths(delete_paths)
            keyword_index.delete_paths(delete_paths)
            keyword_index.commit()
        if new_chunks:
            vector_store.add(new_chunks, vectors)
            keyword_index.add(new_chunks)
            keyword_index.commit()
        elif not delete_paths:
            keyword_index.close()
        # Stamp confirmation for AC-2.6/T7.3 (see restamp_commit_sha): even a
        # metadata-only advance confirms every chunk present at HEAD. This is
        # metadata-only (no re-embed, no keyword churn), which is why T7.7
        # scopes "no store write" to content writes.
        vector_store.restamp_commit_sha(head)
        timings["store"] = perf_counter() - t_store

        finished = datetime.now(timezone.utc)
        meta = meta.__class__(**{**meta.__dict__, "indexed_commit": head,
                                 "last_run_at": finished.isoformat(),
                                 "config_fingerprint": current_fp,
                                 "in_progress": None})
        write_meta(idx, meta)
        elapsed = (finished - started).total_seconds()
        from collections import Counter
        skipped_by_rule = Counter(
            d.reason for d in decisions.values() if not d.included)
        report = RunReport(
            mode=mode, from_commit=base_commit, to_commit=head, note=note,
            files_added=len(changeset.added), files_modified=len(changeset.modified),
            files_deleted=len(changeset.deleted),
            files_skipped=sum(1 for p, d in decisions.items()
                              if not d.included and d.reason != "non-code"),
            skipped_by_rule=dict(skipped_by_rule),
            files_non_code=sum(1 for d in decisions.values() if d.reason == "non-code"),
            files_fallback=files_fallback,
            chunks_added=chunks_added, chunks_removed=chunks_removed,
            embedder_model=embedder.identity.model,
            embedder_revision=embedder.identity.revision,
            elapsed_seconds=elapsed, timings=timings,
        )
        from .report import write_json
        stamp = finished.isoformat(timespec="seconds").replace(":", "").replace("+", "")
        write_json(report, idx / "runs" / f"{stamp}.json")
        return report


def dry_run(repo_path, *, config, index_dir=None) -> RunReport:
    """List what a run would change without writing anything (AC-7.3).

    No lock file, no metadata change, no store opens, no embedding: only git
    reads, exclusion checks, and chunk counting.
    """
    from collections import Counter

    from .chunking.sizing import SizePolicy
    from .exclusions import Decision, decide
    from .models import ChunkMode

    started = perf_counter()
    src = GitSource(repo_path)
    head = src.head_sha()
    idx = index_path_for(repo_path, Path(index_dir) if index_dir is not None
                         else Path(config.index.dir))
    meta_path = idx / "meta.json"
    meta = read_meta(idx) if meta_path.exists() else None
    if (meta is not None and meta.indexed_commit == head
            and meta.in_progress is None
            and meta.config_fingerprint == config_fingerprint(config)):
        return RunReport(mode="up-to-date", from_commit=head, to_commit=head)
    current_fp = config_fingerprint(config)
    base_commit, mode, note, changeset, touched = _compute_plan(
        src, meta, head, current_fp)
    policy = SizePolicy(target_tokens=config.chunking.target_tokens,
                        hard_max_tokens=config.chunking.hard_max_tokens)
    decisions: dict[str, object] = {}
    chunks_added = 0
    files_fallback = 0
    for path in sorted(set(touched) - set(changeset.deleted)):
        quick = decide(path, config.files)
        if not quick.included:
            decisions[path] = quick
            continue
        if src.blob_size(head, path) > config.files.max_file_bytes:
            decisions[path] = Decision(False, "too-large")
            continue
        blob = src.read_blob(head, path)
        if b"\x00" in blob[:8192]:
            decisions[path] = Decision(False, "binary")
            continue
        decisions[path] = Decision(True, "include")
        chunks, m = chunk_file(path, blob.decode("utf-8", "replace"), head,
                               policy=policy)
        if m is ChunkMode.FALLBACK:
            files_fallback += 1
        chunks_added += len(chunks)
    for path in sorted(set(touched)):
        decisions.setdefault(path, Decision(True, "include"))
    skipped_by_rule = Counter(
        d.reason for d in decisions.values() if not d.included)
    label = {"full": "dry-run-full", "rebuild": "dry-run-rebuild"}.get(
        mode, "dry-run")
    return RunReport(
        mode=label, from_commit=base_commit, to_commit=head, note=note,
        files_added=len(changeset.added), files_modified=len(changeset.modified),
        files_deleted=len(changeset.deleted),
        files_skipped=sum(1 for d in decisions.values()
                          if not d.included and d.reason != "non-code"),
        skipped_by_rule=dict(skipped_by_rule),
        files_non_code=sum(1 for d in decisions.values()
                           if d.reason == "non-code"),
        files_fallback=files_fallback,
        chunks_added=chunks_added, chunks_removed=0,
        elapsed_seconds=perf_counter() - started, timings={},
    )
