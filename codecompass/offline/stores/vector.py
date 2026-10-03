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
        self._collection.delete(where={"file_path": {"$in": list(paths)}})

    def ids(self) -> set[str]:
        return set(self._collection.get(limit=10_000_000)["ids"])

    def count(self) -> int:
        return self._collection.count()

    def vectors_for_paths(self, paths) -> dict[str, list[float]]:
        """text_hash -> vector for chunks under *paths* (vector reuse, O3)."""
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
