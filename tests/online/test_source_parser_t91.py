"""T9.1 source entry parser tests (tests-first).

Contract under test (Spec AC-4.5; Plan D9; Article VI.4):
  - parser.parse_answer(text) -> ParsedAnswer(body, sources, has_sources)
  - the Sources heading is a line "Sources", optionally with "#", "**" or ":";
    the last such line splits body from sources
  - code entry: [N] path, lines X-Y (indexed at abc1234)
  - commit entry: [N] Commit abc1234, "subject", author, YYYY-MM-DD
  - an entry line starting with [N] that matches neither is kept with
    kind "invalid", so the checker can flag it
  - parser.body_markers(body) -> set of N for inline [N] markers, ignoring
    indexing like arr[0]
"""

import pytest

from codecompass.online.citation import parser
from codecompass.online.models import SourceEntry

ANSWER = """Retries happen three times [1], added for a flaky upstream [2].

Sources
[1] src/auth/client.py, lines 42-58 (indexed at a1b2c3d)
[2] Commit a1b2c3d, "handle flaky upstream, again", Alice Tan, 2024-03-14
"""


def test_splits_body_and_parses_both_entry_kinds():
    parsed = parser.parse_answer(ANSWER)
    assert parsed.has_sources
    assert parsed.body.strip() == ANSWER.split("\n\nSources")[0]
    assert parsed.sources == [
        SourceEntry(kind="code", marker=1, path="src/auth/client.py",
                    start_line=42, end_line=58, commit="a1b2c3d"),
        SourceEntry(kind="commit", marker=2, commit="a1b2c3d",
                    subject="handle flaky upstream, again", author="Alice Tan",
                    date="2024-03-14"),
    ]


@pytest.mark.parametrize("heading", ["Sources", "Sources:", "## Sources",
                                     "**Sources**", "  sources  "])
def test_heading_variants(heading):
    text = f"x [1]\n\n{heading}\n[1] a.py, lines 1-2 (indexed at abcdef0)"
    parsed = parser.parse_answer(text)
    assert parsed.has_sources and parsed.sources[0].path == "a.py"


def test_no_sources_section():
    parsed = parser.parse_answer("I could not find enough evidence.")
    assert not parsed.has_sources
    assert parsed.sources == []
    assert parsed.body == "I could not find enough evidence."


@pytest.mark.parametrize("line", [
    "[3] somewhere in the auth module",
    "[3] a.py, lines 58 (indexed at abcdef0)",
    "[3] a.py, lines 1-2 (indexed at XYZ)",
    "[3] Commit abc, no quotes, Bob, 2024-01-01",
])
def test_unparseable_entries_are_kept_as_invalid(line):
    parsed = parser.parse_answer(f"x [3]\n\nSources\n{line}")
    assert parsed.sources == [SourceEntry(kind="invalid", marker=3)]


def test_non_entry_lines_in_sources_are_ignored():
    parsed = parser.parse_answer(
        "x [1]\n\nSources\n\n[1] a.py, lines 1-2 (indexed at abcdef0)\nHope this helps!")
    assert [s.marker for s in parsed.sources] == [1]


def test_body_markers_ignore_indexing():
    assert parser.body_markers("see [1] and [12], not arr[0] or m[2][3]") == {1, 12}
