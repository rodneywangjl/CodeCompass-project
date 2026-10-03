"""T3.8 dispatcher and failure-handling tests (tests-first)."""

from unittest.mock import patch

from codecompass.offline.chunking import chunk_file
from codecompass.offline.models import ChunkMode


def test_grammar_language_uses_treesitter():
    chunks, mode = chunk_file("src/a.py", "def f():\n    return 1\n", "sha")
    assert mode == ChunkMode.STRUCTURED
    assert [c.symbol for c in chunks] == ["f"]


def test_grammarless_language_uses_fallback():
    chunks, mode = chunk_file("src/tool.go", "package main\n\nfunc main() {}\n", "sha")
    assert mode == ChunkMode.FALLBACK
    assert chunks and chunks[0].language == "go"


def test_syntax_error_file_does_not_crash():
    chunks, mode = chunk_file("src/broken.py", "def broken(:\n    pass\n", "sha")
    assert mode in (ChunkMode.STRUCTURED, ChunkMode.FALLBACK)
    assert isinstance(chunks, list)


def test_parser_exception_falls_back():
    with patch("codecompass.offline.chunking.treesitter._parser",
               side_effect=RuntimeError("boom")):
        chunks, mode = chunk_file("src/a.py", "def f():\n    pass\n", "sha")
    assert mode == ChunkMode.FALLBACK
    assert len(chunks) == 1
