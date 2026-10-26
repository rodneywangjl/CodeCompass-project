"""T4.1 chunk formatting tests (tests-first).

Contract under test (Spec AC-1.4, FR-5; Plan D3):
  - codecompass.online.context.RetrievedChunk.from_record(chunk_id, record)
    builds a chunk from a vector-store record ({text, metadata, vector}) and
    keeps no vector
  - citation_label(chunk) -> "path, lines S-E (indexed at abc1234)", the exact
    Sources code-citation form (Article VI.4)
  - format_chunk(chunk) -> "--- <citation_label> | <language> ---\n<text>"
  - format_context(chunks) joins blocks with a blank line, in the given order
  - the formatted text contains no vectors and no chunk ids
"""

from codecompass.online import context

SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
RECORD = {
    "text": "def authenticate(user, password):\n    return True",
    "metadata": {
        "file_path": "src/auth/client.py", "start_line": 42, "end_line": 58,
        "language": "python", "symbol": "authenticate", "commit_sha": SHA,
        "text_hash": "h",
    },
    "vector": [0.1, 0.2, 0.3],
}


def chunk(cid="chunk-1", record=RECORD):
    return context.RetrievedChunk.from_record(cid, record)


def test_from_record_keeps_metadata_and_drops_vector():
    c = chunk()
    assert (c.chunk_id, c.path, c.start_line, c.end_line) == (
        "chunk-1", "src/auth/client.py", 42, 58)
    assert c.language == "python" and c.commit_sha == SHA
    assert c.text == RECORD["text"]
    assert not hasattr(c, "vector")


def test_citation_label_is_sources_form():
    assert context.citation_label(chunk()) == (
        "src/auth/client.py, lines 42-58 (indexed at a1b2c3d)")


def test_format_chunk_header_and_text():
    assert context.format_chunk(chunk()) == (
        "--- src/auth/client.py, lines 42-58 (indexed at a1b2c3d) | python ---\n"
        "def authenticate(user, password):\n    return True")


def test_format_context_joins_in_order_without_ids_or_vectors():
    other = dict(RECORD, metadata=dict(RECORD["metadata"], file_path="b.py",
                                       start_line=1, end_line=2))
    text = context.format_context([chunk("id-a"), chunk("id-b", other)])
    assert text.index("src/auth/client.py") < text.index("b.py")
    assert "\n\n--- b.py, lines 1-2" in text
    assert "id-a" not in text and "id-b" not in text
    assert "0.1" not in text


def test_format_context_of_nothing_is_empty():
    assert context.format_context([]) == ""
