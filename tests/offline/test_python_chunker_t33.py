"""T3.3 Python chunker tests (tests-first)."""

from codecompass.offline.chunking import treesitter
from codecompass.offline.models import ChunkMode

SRC = '''import os

CONST = 1


def foo():
    return 1


class Bar:
    def m(self):
        return 2


@deco
def baz():
    pass


def outer():
    def inner():
        return 3
    return inner()
'''


def _chunk(path="src/a.py", text=SRC):
    chunks, mode = treesitter.chunk(path, text, "abc123")
    assert mode == ChunkMode.STRUCTURED
    return chunks


def test_units_and_header():
    chunks = _chunk()
    by_symbol = {c.symbol: c for c in chunks}
    assert set(by_symbol) == {"foo", "Bar", "baz", "outer", None}
    assert "def m(self)" in by_symbol["Bar"].text  # small class stays one chunk
    assert "import os" in by_symbol[None].text and "CONST = 1" in by_symbol[None].text
    assert by_symbol["baz"].text.startswith("@deco")
    assert "def inner" in by_symbol["outer"].text  # nested stays inside parent


def test_ranges_match_file_lines():
    lines = SRC.split("\n")
    for c in _chunk():
        assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])
        assert c.path == "src/a.py" and c.commit_sha == "abc123"
        assert c.language == "python"


def test_no_mid_unit_cuts():
    # Every top-level def/class range appears exactly as a chunk range.
    chunks = _chunk()
    ranges = {(c.start_line, c.end_line) for c in chunks}
    assert (6, 7) in ranges  # foo
    assert (10, 12) in ranges  # Bar
    assert (20, 23) in ranges  # outer (nested inner stays inside)


def test_empty_file_yields_zero_chunks():
    chunks, _ = treesitter.chunk("src/e.py", "", "abc123")
    assert chunks == []
