"""T19.2 an oversized chunk does not block the others (tests-first).

Bug (dev test 2 Nov 2026, B2): fit_chunks stopped at the first chunk that did
not fit. The top-ranked chunk was bigger than the whole budget, so no chunk was
sent and the answer, ranked 3rd, never reached the model.

Contract under test (Spec AC-2.6; Plan D4 item 1; Article I.2, IV.2, VIII.4):
  - context.fit_chunks(chunks, budget, count_tokens) skips a chunk that does not
    fit the room left and still tries the later ones
  - the kept chunks are in input (re-ranker) order
  - their total cost never exceeds the budget
"""

import pytest

from codecompass.online import context
from codecompass.online.context import RetrievedChunk, format_chunk
from tests.support.stub_generator import StubGenerator

COUNT = StubGenerator(["x"]).count_tokens        # whitespace tokens, deterministic


def _chunk(cid, words):
    return RetrievedChunk(cid, " ".join(["w"] * words), f"src/{cid}.py", 1, 2,
                          "python", "a" * 40)


def _cost(chunks):
    return sum(COUNT(format_chunk(c)) for c in chunks)


SMALL = _chunk("small", 10)
BLOCK = COUNT(format_chunk(SMALL))               # cost of one small chunk


def _small(cid):
    return _chunk(cid, 10)


def _huge(cid):
    return _chunk(cid, 1000)                     # far bigger than any budget below


def test_an_oversized_first_chunk_does_not_block_the_rest():
    chunks = [_huge("top"), _small("b"), _small("answer")]
    assert context.fit_chunks(chunks, 3 * BLOCK, COUNT) == chunks[1:]


def test_an_oversized_middle_chunk_is_skipped():
    chunks = [_small("a"), _huge("big"), _small("c")]
    assert context.fit_chunks(chunks, 3 * BLOCK, COUNT) == [chunks[0], chunks[2]]


def test_a_later_smaller_chunk_fills_the_room_left():
    medium = _chunk("medium", 40)
    chunks = [_small("a"), medium, _small("c")]
    budget = 2 * BLOCK + 5                       # room for the two small ones only
    assert COUNT(format_chunk(medium)) > budget - BLOCK
    assert context.fit_chunks(chunks, budget, COUNT) == [chunks[0], chunks[2]]


def test_every_chunk_over_budget_gives_none():
    chunks = [_huge("a"), _huge("b")]
    assert context.fit_chunks(chunks, 3 * BLOCK, COUNT) == []


@pytest.mark.parametrize("sizes, budget", [
    ([1000, 10, 10, 10], 2 * BLOCK),
    ([10, 1000, 40, 10, 10], 3 * BLOCK),
    ([40, 10, 1000, 10, 40], 2 * BLOCK + 5),
    ([10, 10, 10], 3 * BLOCK),
])
def test_kept_chunks_keep_their_order_and_fit_the_budget(sizes, budget):
    chunks = [_chunk(f"c{i}", n) for i, n in enumerate(sizes)]
    kept = context.fit_chunks(chunks, budget, COUNT)
    assert kept == [c for c in chunks if c in kept]   # input order
    assert _cost(kept) <= budget
    left = budget - _cost(kept)
    for c in chunks:                                  # nothing that would fit was left out
        if c not in kept:
            assert COUNT(format_chunk(c)) > left
