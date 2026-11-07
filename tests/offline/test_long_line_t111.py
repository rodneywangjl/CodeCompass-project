"""T11.1 a line over the hard max is split, never emitted whole or crashed on (tests first).

Bug (GPU cluster, 7 Nov 2026): the fallback chunker joined the tokenizer's output
with spaces (a TypeError with the embedder's integer ids), and the tree-sitter
chunker emitted an over-long line as one chunk. Both must split the line by
characters, re-counted with the real tokenizer (Article VIII.1, Spec 001 AC-3.3).

Stub tokenizers only: CHARS returns one integer id per character, like the
real embedder's ``tokenize`` returns ids; WORDS returns strings, as the old
stub did. No model, network or GPU.
"""

import pytest

from codecompass.offline.chunking import fallback, treesitter
from codecompass.offline.chunking.sizing import SizePolicy, count_tokens

HARD = 60
POLICY = SizePolicy(target_tokens=20, hard_max_tokens=HARD)
CHARS = lambda s: [ord(c) for c in s]  # noqa: E731 (one integer id per character)
WORDS = str.split

LONG_LINE = '    s = "' + "ab" * 120 + '"'  # 133 characters, line 3 of FUNC
FUNC = "def f():\n    a = 1\n" + LONG_LINE + "\n    return s\n"
LONG_NO = 3

CHUNKERS = {
    "fallback": lambda src, tok=CHARS: fallback.chunk("src/long.py", src, "sha",
                                                      policy=POLICY, tokenizer=tok)[0],
    "treesitter": lambda src, tok=CHARS: treesitter.chunk("src/long.py", src, "sha",
                                                          policy=POLICY, tokenizer=tok)[0],
}


@pytest.fixture(params=sorted(CHUNKERS))
def chunker(request):
    return CHUNKERS[request.param]


def _pieces_of_long_line(chunks):
    """Chunks that contain the long line (their ranges include LONG_NO)."""
    return [c for c in chunks if c.start_line <= LONG_NO <= c.end_line]


def test_no_crash_and_every_chunk_within_hard_max(chunker):
    chunks = chunker(FUNC)  # would raise TypeError in the fallback before the fix
    assert chunks
    for c in chunks:
        assert count_tokens(c.text, CHARS) <= HARD


def test_long_line_is_split_and_pieces_join_to_the_original(chunker):
    pieces = _pieces_of_long_line(chunker(FUNC))
    assert len(pieces) > 1, "the long line must be split, not emitted whole"
    for c in pieces:
        assert c.start_line == c.end_line == LONG_NO
    assert "".join(c.text for c in pieces) == LONG_LINE


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_long_line_first_in_the_file_is_split_without_a_crash(name):
    # The long line starts its own window: the path where the fallback joined ids.
    line = LONG_LINE.lstrip()
    chunks = CHUNKERS[name](line + "\n    return 1\n")
    pieces = [c for c in chunks if c.start_line == 1 and c.end_line == 1]
    assert len(pieces) > 1, "the long line must be split, not emitted whole"
    assert "".join(c.text for c in pieces) == line
    for c in chunks:
        assert count_tokens(c.text, CHARS) <= HARD


def test_tree_sitter_short_lines_before_a_long_line_in_a_function_stay_out_of_it():
    chunks = CHUNKERS["treesitter"](FUNC)
    for c in chunks:
        if c.start_line <= LONG_NO <= c.end_line:
            assert c.start_line == c.end_line == LONG_NO


def test_surrounding_short_lines_are_not_merged_into_the_long_line(chunker):
    # Short lines before the long line sit in the same window: the chunk holding
    # them must end before the long line, not include it.
    src = "a = 1\nb = 2\n" + LONG_LINE + "\nc = 3\nd = 4\n"
    chunks = chunker(src)
    for c in chunks:
        if not (c.start_line <= LONG_NO <= c.end_line):
            continue
        assert c.start_line == c.end_line == LONG_NO


def test_fallback_lines_before_and_after_are_chunked_as_without_the_long_line():
    before, after = "a = 1\nb = 2\n", "c = 3\nd = 4\n"
    full = fallback.chunk("src/long.py", before + LONG_LINE + "\n" + after, "sha",
                          policy=POLICY, tokenizer=CHARS)[0]
    head = fallback.chunk("src/long.py", before, "sha", policy=POLICY, tokenizer=CHARS)[0]
    tail = fallback.chunk("src/long.py", after, "sha", policy=POLICY, tokenizer=CHARS)[0]
    assert (full[0].text, full[0].start_line, full[0].end_line) == (
        head[0].text, head[0].start_line, head[0].end_line)
    last = full[-1]  # the tail starts after the two head lines and the long line
    assert last.text == tail[-1].text
    assert (last.start_line, last.end_line) == (tail[-1].start_line + 3, tail[-1].end_line + 3)


def test_tree_sitter_units_around_the_long_line_are_unchanged():
    before = "def before():\n    return 1\n"
    mid = 'def mid():\n    s = "' + "ab" * 120 + '"\n    return s\n'
    after = "def after():\n    return 2\n"
    short_mid = 'def mid():\n    s = "x"\n    return s\n'  # same number of lines
    src = before + mid + after
    base = before + short_mid + after
    keep = lambda chunks: [(c.text, c.start_line, c.end_line, c.symbol)  # noqa: E731
                           for c in chunks if c.symbol in ("before", "after")]
    got = keep(treesitter.chunk("src/long.py", src, "sha", policy=POLICY, tokenizer=CHARS)[0])
    want = keep(treesitter.chunk("src/long.py", base, "sha", policy=POLICY, tokenizer=CHARS)[0])
    assert got and got == want


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_chunk_ids_are_unique(name):
    chunks = CHUNKERS[name](FUNC)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_string_returning_tokenizer_still_works(name):
    line = '    s = "' + " ".join(["w"] * 200) + '"'
    src = "def f():\n    a = 1\n" + line + "\n    return s\n"  # the long line is line 3
    chunks = CHUNKERS[name](src, WORDS)
    pieces = _pieces_of_long_line(chunks)
    assert len(pieces) > 1
    for c in chunks:
        assert count_tokens(c.text, WORDS) <= HARD
    assert "".join(c.text for c in pieces) == line


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_a_character_that_cannot_fit_raises_instead_of_emitting_oversize(name):
    too_costly = lambda s: [0] * (HARD + 1) * max(len(s), 1)  # noqa: E731
    with pytest.raises(ValueError):
        CHUNKERS[name](FUNC, too_costly)
