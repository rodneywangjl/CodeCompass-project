"""T9.7 uncited answers and uncited parts tests (tests-first).

Contract under test (Spec AC-4.8, AC-4.9, FR-19; Plan D11; Article VI.3):
  - formatter.UNCITED_NOTE, PARTIAL_NOTE and TAG hold the exact spec wording
  - no markers and no Sources entries: UNCITED_NOTE above the answer, no BANNER
  - an answer with citations: each paragraph or list item without a [N]
    marker gets TAG at its end, and PARTIAL_NOTE goes above the answer
    (below BANNER for G); headings, fenced code and lead-ins ending ":" are
    never tagged
  - outcomes are unchanged: an answer with no citations is G, a partly cited
    answer whose citations all verify is F
"""

from codecompass.online.citation import checker, formatter
from codecompass.online.context import RetrievedChunk

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
GOOD = "[1] src/auth.py, lines 42-58 (indexed at a1b2c3d)"
BAD = "[1] src/other.py, lines 1-2 (indexed at a1b2c3d)"


def check(text):
    return checker.check(text, CHUNKS, [])


def render(text):
    return formatter.render(check(text))


def test_wording_matches_the_spec():
    assert formatter.UNCITED_NOTE == (
        "Note: This answer is not supported by any citation from the repository. "
        "Verify it against the source code before relying on it.")
    assert formatter.PARTIAL_NOTE == (
        "Note: Some statements in this answer are not supported by a citation. "
        "They are marked (not cited). Verify them against the source code before "
        "relying on them.")
    assert formatter.TAG == " (not cited)"


def test_answer_with_no_citations_gets_the_note_not_the_banner():
    out = render("Five retries.")
    assert out == formatter.UNCITED_NOTE + "\n\nFive retries."
    assert formatter.BANNER not in out


def test_empty_sources_heading_counts_as_no_citations():
    text = "Five retries.\n\nSources"
    assert render(text) == formatter.UNCITED_NOTE + "\n\n" + text


def test_uncited_paragraph_in_a_cited_answer_is_tagged():
    text = ("Login retries three times [1].\n\n"
            "This was added for a flaky server.\n\n"
            f"Sources\n{GOOD}")
    assert check(text).outcome == "F"
    assert render(text) == (
        formatter.PARTIAL_NOTE + "\n\n"
        "Login retries three times [1].\n\n"
        "This was added for a flaky server. (not cited)\n\n"
        f"Sources\n{GOOD}")


def test_list_items_are_tagged_one_by_one_at_their_last_line():
    text = ("How it works:\n"
            "- retries three times [1]\n"
            "- logs each failure\n"
            "  to stderr\n\n"
            f"Sources\n{GOOD}")
    lines = render(text).splitlines()
    assert "How it works:" in lines
    assert "- retries three times [1]" in lines
    assert "- logs each failure" in lines
    assert "  to stderr (not cited)" in lines


def test_headings_code_and_lead_ins_are_not_tagged():
    text = ("## Retry logic\n\n"
            "Here is the call:\n\n"
            "```python\nretry(3)\n```\n\n"
            "It retries three times [1].\n\n"
            f"Sources\n{GOOD}")
    assert render(text) == text


def test_flagged_answer_shows_banner_then_note():
    text = f"Retries [1].\n\nAn uncited claim.\n\nSources\n{BAD}"
    out = render(text)
    assert check(text).outcome == "G"
    assert out.startswith(formatter.BANNER + "\n\n" + formatter.PARTIAL_NOTE + "\n\n")
    lines = out.splitlines()
    assert "An uncited claim. (not cited)" in lines
    assert "[UNVERIFIED] " + BAD in lines


def test_markers_without_sources_is_a_citation_failure_not_uncited():
    out = render("Retries three times [1].")
    assert out.startswith(formatter.BANNER)
    assert formatter.UNCITED_NOTE not in out
    assert "[UNVERIFIED] [1] (no matching Sources entry)" in out.splitlines()


def test_outcomes_are_unchanged():
    assert check("Five retries.").outcome == "G"
    assert check(f"A [1].\n\nB.\n\nSources\n{GOOD}").outcome == "F"
