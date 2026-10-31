"""Chroma (HNSW, cosine) vector store behind the VectorStore interface."""

from __future__ import annotations

import chromadb

from codecompass.offline.chunking.ids import text_hash

COLLECTION = "chunks"


class VectorStore:
    """One collection `chunks`; document is the chunk text (plan §7)."""

    def __init__(self, path, dimension: int | None = None) -> None:
        import pathlib
        self.dir = pathlib.Path(path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.dir))
        self._collection = self._client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"})
        if dimension is not None:
            self._dimension = dimension
        else:
            existing = self._collection.get(limit=1, include=["embeddings"])
            got = existing["embeddings"]
            self._dimension = len(got[0]) if len(got) > 0 else None

    def space(self) -> str:
        return self._collection.metadata.get("hnsw:space", "")

    def add(self, chunks, vectors) -> None:
        for chunk, vector in zip(chunks, vectors):
            if self._dimension is None:
                self._dimension = len(vector)
            if len(vector) != self._dimension:
                raise ValueError(
                    f"vector dimension {len(vector)} != store dimension {self._dimension}")
        self._collection.add(
            ids=[c.id for c in chunks],
            embeddings=[list(map(float, v)) for v in vectors],
            documents=[c.text for c in chunks],
            metadatas=[{
                "file_path": c.path, "start_line": c.start_line,
                "end_line": c.end_line, "language": c.language,
                "symbol": c.symbol or "", "commit_sha": c.commit_sha,
                "text_hash": text_hash(c.text),
            } for c in chunks],
        )

    def delete_paths(self, paths) -> None:
        paths = list(paths)
        if paths:
            self._collection.delete(where={"file_path": {"$in": paths}})

    def ids(self) -> set[str]:
        return set(self._collection.get(limit=10_000_000)["ids"])

    def count(self) -> int:
        return self._collection.count()

    def search(self, vector, limit: int) -> list[str]:
        """Chunk ids nearest to *vector* by cosine, nearest first (ANN read path)."""
        n = min(limit, self._collection.count())
        if n <= 0:
            return []
        got = self._collection.query(
            query_embeddings=[list(map(float, vector))], n_results=n, include=[])
        return list(got["ids"][0])

    def vectors_for_paths(self, paths) -> dict[str, list[float]]:
        """text_hash -> vector for chunks under *paths* (vector reuse, O3)."""
        paths = list(paths)
        if not paths:
            return {}
        got = self._collection.get(
            where={"file_path": {"$in": list(paths)}},
            limit=10_000_000, include=["embeddings", "metadatas"])
        out = {}
        for meta, emb in zip(got["metadatas"], got["embeddings"]):
            out.setdefault(meta["text_hash"], list(emb))
        return out

    def paths_for_ids(self, ids) -> dict[str, str]:
        """chunk id -> file path (for the consistency check)."""
        ids = list(ids)
        if not ids:
            return {}
        got = self._collection.get(ids=ids, limit=10_000_000, include=["metadatas"])
        return {cid: meta["file_path"]
                for cid, meta in zip(got["ids"], got["metadatas"])}

    def symbols_for_path(self, path) -> list[tuple[str, int, int]]:
        """(symbol, start_line, end_line) of the indexed chunks of *path*, by line.

        Chunks split from one symbol are merged into one range; chunks with no
        symbol are left out. Read-only; used by the open_file outline (Plan D18).
        """
        got = self._collection.get(where={"file_path": path}, limit=10_000_000,
                                   include=["metadatas"])
        spans: dict[str, list[int]] = {}
        for meta in got["metadatas"]:
            name = meta.get("symbol") or ""
            if not name:
                continue
            span = spans.setdefault(name, [meta["start_line"], meta["end_line"]])
            span[0] = min(span[0], meta["start_line"])
            span[1] = max(span[1], meta["end_line"])
        return sorted(((n, s, e) for n, (s, e) in spans.items()), key=lambda x: (x[1], x[0]))

    def records_for_ids(self, ids) -> dict[str, dict]:
        """chunk id -> {text, metadata, vector} (read path and equivalence)."""
        ids = list(ids)
        if not ids:
            return {}
        got = self._collection.get(
            ids=ids, limit=10_000_000,
            include=["documents", "metadatas", "embeddings"])
        return {cid: {"text": doc, "metadata": meta, "vector": list(vec)}
                for cid, doc, meta, vec
                in zip(got["ids"], got["documents"], got["metadatas"],
                       got["embeddings"])}

    def restamp_commit_sha(self, commit_sha: str) -> int:
        """Set commit_sha on every record still carrying an older one.

        AC-2.6/T7.3 require an incremental run to equal a fresh build, so each
        advancing run confirms every chunk present at HEAD. Metadata-only: no
        re-embedding, no text changes.
        """
        got = self._collection.get(limit=10_000_000, include=["metadatas"])
        stale_ids, stale_metas = [], []
        for cid, meta in zip(got["ids"], got["metadatas"]):
            if meta.get("commit_sha") != commit_sha:
                stale_ids.append(cid)
                stale_metas.append({**meta, "commit_sha": commit_sha})
        if stale_ids:
            self._collection.update(ids=stale_ids, metadatas=stale_metas)
        return len(stale_ids)
