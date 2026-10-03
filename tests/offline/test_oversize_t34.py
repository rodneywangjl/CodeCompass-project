"""T3.4 oversize splitting tests (tests-first)."""

import random

from codecompass.offline.chunking import treesitter
from codecompass.offline.chunking.sizing import SizePolicy, count_tokens
from codecompass.offline.models import ChunkMode

POLICY = SizePolicy(target_tokens=20, hard_max_tokens=60)
TOK = lambda s: s.split()  # noqa: E731


def _chunk(text, path="src/a.py"):
    chunks, mode = treesitter.chunk(path, text, "sha", policy=POLICY, tokenizer=TOK)
    assert mode == ChunkMode.STRUCTURED
    return chunks


def test_big_class_becomes_header_plus_methods():
    src = "class C:\n" + "".join(
        f"    def m{i}(self):\n        return {i}\n" for i in range(8))
    chunks = _chunk(src)
    symbols = [c.symbol for c in chunks]
    assert symbols[0] == "C" and "class C" in chunks[0].text
    assert symbols[1:] == [f"C.m{i}" for i in range(8)]


def test_long_function_splits_at_blocks():
    src = "def f():\n" + "".join(f"    x{i} = {i}\n" for i in range(30))
    chunks = _chunk(src)
    assert len(chunks) > 1
    assert {c.symbol for c in chunks} == {"f"}
    ranges = sorted((c.start_line, c.end_line) for c in chunks)
    for (s1, e1), (s2, e2) in zip(ranges, ranges[1:]):
        assert e1 < s2  # never overlap


def test_leaf_over_hard_max_becomes_line_windows():
    src = "x = [\n" + "".join(f"    {i},\n" for i in range(100)) + "]\n"
    chunks, mode = treesitter.chunk("src/d.py", src, "sha",
                                    policy=POLICY, tokenizer=TOK)
    assert len(chunks) > 1
    for c in chunks:
        assert count_tokens(c.text, TOK) <= POLICY.hard_max_tokens


def test_property_no_chunk_exceeds_hard_max_and_no_overlap():
    rng = random.Random(0)
    for trial in range(30):
        parts = []
        for f in range(rng.randint(1, 5)):
            n = rng.randint(1, 40)
            parts.append(f"def f{trial}_{f}():\n" +
                         "".join(f"    x{i} = {i}\n" for i in range(n)))
        if rng.random() < 0.5:
            m = "".join(f"    def m{i}(self):\n        return {i}\n"
                        for i in range(rng.randint(1, 6)))
            parts.append(f"class C{trial}:\n    CONST = 1\n{m}")
        src = "\n".join(parts) + "\n"
        chunks = _chunk(src)
        lines = src.split("\n")
        ranges = []
        for c in chunks:
            assert count_tokens(c.text, TOK) <= POLICY.hard_max_tokens
            assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])
            ranges.append((c.start_line, c.end_line))
        ranges.sort()
        for (s1, e1), (s2, e2) in zip(ranges, ranges[1:]):
            assert e1 < s2
