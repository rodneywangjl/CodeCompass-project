"""In-memory fakes of the vector store and keyword index protocols."""

from __future__ import annotations

from codecompass.offline.chunking.ids import text_hash


class FakeVectorStore:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_path: dict[str, set] = {}

    def add(self, chunks, vectors) -> None:
        for chunk, vector in zip(chunks, vectors):
            self._by_id[chunk.id] = (chunk, vector)
            self._by_path.setdefault(chunk.path, set()).add(chunk.id)

    def delete_paths(self, paths) -> None:
        for path in paths:
            for cid in self._by_path.pop(path, set()):
                self._by_id.pop(cid, None)

    def ids(self) -> set:
        return set(self._by_id)

    def count(self) -> int:
        return len(self._by_id)

    def vectors_for_paths(self, paths) -> dict:
        out = {}
        for path in paths:
            for cid in self._by_path.get(path, set()):
                chunk, vector = self._by_id[cid]
                out.setdefault(text_hash(chunk.text), vector)
        return out


class FakeKeywordIndex:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_path: dict[str, set] = {}

    def add(self, chunks) -> None:
        for chunk in chunks:
            self._by_id[chunk.id] = chunk
            self._by_path.setdefault(chunk.path, set()).add(chunk.id)

    def delete_paths(self, paths) -> None:
        for path in paths:
            for cid in self._by_path.pop(path, set()):
                self._by_id.pop(cid, None)

    def commit(self) -> None:
        pass

    def search(self, text: str, limit: int) -> list:
        hits = [cid for cid, c in self._by_id.items() if text in c.text]
        return hits[:limit]

    def ids(self) -> set:
        return set(self._by_id)
