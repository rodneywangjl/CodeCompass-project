"""T3.2 chunk ids and text hashes tests (tests-first)."""

from codecompass.offline.chunking.ids import chunk_id, text_hash


def test_deterministic_same_inputs():
    a = chunk_id("src/a.py", "f", 0, "def f():\n    pass\n")
    b = chunk_id("src/a.py", "f", 0, "def f():\n    pass\n")
    assert a == b and len(a) > 0


def test_line_shift_does_not_change_id():
    # Id covers path+symbol+occurrence+text, not line numbers.
    a = chunk_id("src/a.py", "f", 0, "def f():\n    pass\n")
    assert a == chunk_id("src/a.py", "f", 0, "def f():\n    pass\n")


def test_duplicates_and_changes():
    t = "x = 1\n"
    assert chunk_id("a.py", None, 0, t) != chunk_id("a.py", None, 1, t)
    assert chunk_id("a.py", "f", 0, t) != chunk_id("a.py", "g", 0, t)
    assert chunk_id("a.py", "f", 0, t) != chunk_id("a.py", "f", 0, t + "\n")
    assert chunk_id("a.py", "f", 0, t) != chunk_id("b.py", "f", 0, t)


def test_text_hash_changes_with_text():
    assert text_hash("a") != text_hash("b")
    assert text_hash("a") == text_hash("a")
