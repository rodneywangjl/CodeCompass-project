"""T9.4 flagged answer formatting tests (tests-first).

Contract under test (Spec AC-4.4, AC-4.7, FR-10; Plan D11):
  - formatter.BANNER is the whole-answer warning; it says citations could not
    be verified and does not claim the answer is true or false
  - formatter.render(result) -> str
    F: the answer text unchanged
    G: BANNER, a blank line, then the answer with each unverified Sources
       entry prefixed "[UNVERIFIED] "; a marker with no entry gets its own
       "[UNVERIFIED] [N] (no matching Sources entry)" line
  - a G answer never renders identically to the same text as F
"""

from codecompass.online.agent.tools import CommitRecord
from codecompass.online.citation import checker, formatter
from codecompass.online.context import RetrievedChunk

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
GOOD = "[1] src/auth.py, lines 42-58 (indexed at a1b2c3d)"
BAD = "[2] src/other.py, lines 1-2 (indexed at a1b2c3d)"


def render(text):
    return formatter.render(checker.check(text, CHUNKS, []))


def test_banner_wording():
    assert formatter.BANNER.startswith("⚠ WARNING: Some citations")
    assert "could not be verified" in formatter.BANNER
    assert "true" not in formatter.BANNER.lower()


def test_cited_answer_is_unchanged():
    text = f"A [1].\n\nSources\n{GOOD}"
    assert render(text) == text


def test_flagged_answer_has_banner_and_marks_only_bad_entries():
    text = f"A [1] B [2].\n\nSources\n{GOOD}\n{BAD}"
    out = render(text)
    assert out.startswith(formatter.BANNER + "\n\n")
    lines = out.splitlines()
    assert GOOD in lines
    assert "[UNVERIFIED] " + BAD in lines
    assert BAD not in lines


def test_marker_without_entry_gets_a_line():
    out = render(f"A [1] B [2].\n\nSources\n{GOOD}")
    assert "[UNVERIFIED] [2] (no matching Sources entry)" in out.splitlines()


def test_flagged_never_identical_to_cited():
    text = f"A [1].\n\nSources\n{BAD.replace('[2]', '[1]')}"
    result = checker.check(text, CHUNKS, [])
    assert result.outcome == "G"
    assert formatter.render(result) != text


def test_no_sources_section_gets_uncited_note():
    # Changed by T9.7 (spec AC-4.8, team decision Q1, 2026-10-26): an answer
    # with no citations shows the uncited note, not the unverified banner.
    # Approved-test change; needs reviewer sign-off (Article IX.3).
    out = render("Five retries.")
    assert out == formatter.UNCITED_NOTE + "\n\nFive retries."
