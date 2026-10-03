"""BM25 keyword index behind the KeywordIndex interface (Article XI.3)."""

from __future__ import annotations

import tantivy


def _schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("body", stored=True)
    builder.add_text_field("cid", stored=True, tokenizer_name="raw")
    builder.add_text_field("path", stored=True, tokenizer_name="raw")
    return builder.build()


class KeywordIndex:
    """tantivy-backed keyword index; no other module imports tantivy."""

    def __init__(self, path) -> None:
        import pathlib
        self.dir = pathlib.Path(path)
        self.dir.mkdir(parents=True, exist_ok=True)
        schema = _schema()
        try:
            self._index = tantivy.Index.open(str(self.dir))
        except Exception:
            self._index = tantivy.Index(schema, str(self.dir))
        self._schema = self._index.schema
        self._writer = self._index.writer()

    def add(self, chunks) -> None:
        for chunk in chunks:
            self._writer.add_document(tantivy.Document(
                body=chunk.text, cid=chunk.id, path=chunk.path,
            ))

    def delete_paths(self, paths) -> None:
        for path in paths:
            self._writer.delete_documents_by_term("path", path)

    def commit(self) -> None:
        self._writer.commit()
        self._index.reload()

    def close(self) -> None:
        """Release the writer lock so the index can be reopened."""
        self._writer = None

    def search(self, text: str, limit: int) -> list[str]:
        query = self._index.parse_query_lenient(text, ["body"])
        hits = self._index.searcher().search(query[0], limit).hits
        return [self._cid_of(addr) for _, addr in hits]

    def ids(self) -> set[str]:
        searcher = self._index.searcher()
        if searcher.num_docs == 0:
            return set()
        hits = searcher.search(tantivy.Query.all_query(), searcher.num_docs).hits
        return {self._cid_of(addr) for _, addr in hits}

    def paths_for_ids(self, ids) -> dict[str, str]:
        """chunk id -> file path (for the consistency check)."""
        wanted = set(ids)
        if not wanted:
            return {}
        searcher = self._index.searcher()
        if searcher.num_docs == 0:
            return {}
        out = {}
        hits = searcher.search(tantivy.Query.all_query(), searcher.num_docs).hits
        for _, addr in hits:
            doc = searcher.doc(addr)
            cid = doc.get_first("cid")
            if cid in wanted:
                out[str(cid)] = str(doc.get_first("path"))
        return out

    def _cid_of(self, address) -> str:
        doc = self._index.searcher().doc(address)
        value = doc.get_first("cid")
        return str(value) if value is not None else ""
