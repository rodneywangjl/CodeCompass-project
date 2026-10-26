"""T9.3 citation checker outcome G tests (tests-first).

Contract under test (Spec AC-4.1, AC-4.4, AC-4.5, §6; Plan D9):
  - any unverified entry -> outcome "G", its marker listed in unverified
  - a code citation to a file not in context, a wrong range, a range that
    overlaps a chunk but extends past it, or a wrong indexed-at hash -> G
  - a commit hash not in any tool result -> G
  - an inline marker with no Sources entry -> G
  - a Sources entry no inline marker refers to -> G
  - two entries with the same marker -> G
  - no Sources section at all -> G (spec §6; presentation of honest
    "could not determine" answers is [NEEDS CLARIFICATION])
"""

import pytest

from codecompass.online.agent.tools import CommitRecord
from codecompass.online.citation import checker
from codecompass.online.context import RetrievedChunk

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
COMMITS = [CommitRecord("f00dbab" + "1" * 33, "Alice Tan", "2024-03-14", "fix")]
GOOD = "src/auth.py, lines 42-58 (indexed at a1b2c3d)"


def check(text):
    return checker.check(text, CHUNKS, COMMITS)


@pytest.mark.parametrize("entry", [
    "src/missing.py, lines 42-58 (indexed at a1b2c3d)",
    "src/auth.py, lines 1-10 (indexed at a1b2c3d)",
    "src/auth.py, lines 1-500 (indexed at a1b2c3d)",
    "src/auth.py, lines 50-70 (indexed at a1b2c3d)",
    "src/auth.py, lines 58-42 (indexed at a1b2c3d)",
    "src/auth.py, lines 42-58 (indexed at 9999999)",
    'Commit deadbee, "invented", Bob, 2024-01-01',
    "the auth module",
])
def test_unverifiable_entry_is_g(entry):
    result = check(f"Claim [1].\n\nSources\n[1] {entry}")
    assert result.outcome == "G"
    assert result.unverified == [1]


def test_one_bad_entry_among_good_ones_is_g():
    result = check(f"A [1] B [2].\n\nSources\n[1] {GOOD}\n"
                   "[2] src/other.py, lines 1-2 (indexed at a1b2c3d)")
    assert result.outcome == "G"
    assert [s.verified for s in result.sources] == [True, False]
    assert result.unverified == [2]


def test_marker_without_entry_is_g():
    result = check(f"A [1] B [2].\n\nSources\n[1] {GOOD}")
    assert result.outcome == "G"
    assert 2 in result.unverified


def test_entry_without_marker_is_g():
    result = check(f"A [1].\n\nSources\n[1] {GOOD}\n[2] {GOOD}")
    assert result.outcome == "G"
    assert 2 in result.unverified


def test_duplicate_marker_entries_are_g():
    result = check(f"A [1].\n\nSources\n[1] {GOOD}\n[1] {GOOD}")
    assert result.outcome == "G"


def test_no_sources_section_is_g():
    result = check("The retry count is five.")
    assert result.outcome == "G"
    assert result.sources == []


def test_markers_but_no_sources_section_is_g():
    assert check("The retry count is five [1].").outcome == "G"
