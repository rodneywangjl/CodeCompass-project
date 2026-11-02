"""T16.1 unreferenced sources tests (tests-first).

Contract under test (Spec AC-4.4, 4.10, 7.5; Plan D20; Article VI.3, VI.5):
  - a Sources entry that matches the context but whose marker the answer body never
    uses is "unreferenced": still in `unverified` and still outcome G (T9.3), but
    not shown as a failed verification
  - it is listed in CitationResult.unreferenced; an entry that fails the evidence
    check, a duplicated marker and a marker with no entry never are
  - when every flagged entry is unreferenced the banner is UNREFERENCED_BANNER and the
    entry is prefixed "[NOT REFERENCED IN ANSWER] " (not "[UNVERIFIED] ")
  - any other flagged answer keeps BANNER, and each entry keeps its own prefix
  - the audit log lists the markers under `unreferenced` only when there are some

Seen in use (7B, spm_proj): the answer listed backend/registration_policy.py, lines
31-74, a range inside a chunk it was sent, with no [1] in the body, and was shown as
"citations could not be verified" with the entry marked [UNVERIFIED].
"""

import re

from codecompass.online.agent.tools import CommitRecord
from codecompass.online.citation import checker, formatter
from codecompass.online.context import RetrievedChunk
from codecompass.online.models import CitationResult
import codecompass.online as online
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

SHA = "a1b2c3d" + "0" * 33
CHUNKS = [RetrievedChunk("c1", "x", "src/auth.py", 42, 58, "python", SHA)]
COMMITS = [CommitRecord("f00dbab" + "1" * 33, "Alice Tan", "2024-03-14", "fix")]
GOOD = "src/auth.py, lines 42-58 (indexed at a1b2c3d)"
BAD = "src/other.py, lines 1-2 (indexed at a1b2c3d)"
COMMIT = 'Commit f00dbab, "fix", Alice Tan, 2024-03-14'

UNREF_BANNER = ("⚠ WARNING: Sources are listed, but the answer does not say which "
                "statement each one supports. Check them yourself before relying on "
                "the answer.")
UNREF_MARK = "[NOT REFERENCED IN ANSWER] "


def check(text):
    return checker.check(text, CHUNKS, COMMITS)


def render(text):
    return formatter.render(check(text))


# --- checker (AC-4.10) -------------------------------------------------------------


def test_matching_entry_without_marker_is_unreferenced_and_still_g():
    result = check(f"A [1].\n\nSources\n[1] {GOOD}\n[2] {GOOD}")
    assert result.outcome == "G"
    assert result.unreferenced == [2]
    assert 2 in result.unverified and 1 not in result.unverified


def test_a_fully_referenced_answer_has_none_and_is_f():
    result = check(f"A [1].\n\nSources\n[1] {GOOD}")
    assert result.outcome == "F"
    assert result.unreferenced == []


def test_a_commit_entry_matching_a_tool_result_can_be_unreferenced():
    result = check(f"A.\n\nSources\n[1] {COMMIT}")
    assert result.outcome == "G"
    assert result.unreferenced == [1]


def test_an_entry_that_fails_the_evidence_check_is_not_unreferenced():
    result = check(f"A.\n\nSources\n[1] {BAD}")
    assert result.unreferenced == []
    assert result.unverified == [1]


def test_duplicate_marker_entries_are_not_unreferenced():
    result = check(f"A.\n\nSources\n[1] {GOOD}\n[1] {GOOD}")
    assert result.unreferenced == []
    assert 1 in result.unverified


def test_a_marker_with_no_entry_is_not_unreferenced():
    result = check(f"A [1] B [2].\n\nSources\n[1] {GOOD}")
    assert result.unreferenced == []
    assert result.unverified == [2]


def test_unreferenced_is_always_a_subset_of_unverified():
    result = check(f"A [1] B [3].\n\nSources\n[1] {BAD}\n[2] {GOOD}")
    assert set(result.unreferenced) <= set(result.unverified)


def test_the_result_defaults_to_no_unreferenced_entries():
    assert CitationResult(outcome="F").unreferenced == []


# --- formatter (AC-4.4, 4.10) ------------------------------------------------------


def test_only_unreferenced_entries_get_their_own_banner_and_mark():
    out = render(f"The policy does X.\n\nSources\n[1] {GOOD}")
    assert out.startswith(UNREF_BANNER + "\n\n")
    assert UNREF_MARK + "[1] " + GOOD in out.splitlines()
    assert "[UNVERIFIED]" not in out
    assert formatter.BANNER not in out


def test_a_failed_entry_alongside_an_unreferenced_one_keeps_the_main_banner():
    out = render(f"A [1] and B.\n\nSources\n[1] {BAD}\n[2] {GOOD}")
    assert out.startswith(formatter.BANNER + "\n\n")
    assert UNREF_BANNER not in out
    assert "[UNVERIFIED] [1] " + BAD in out.splitlines()
    assert UNREF_MARK + "[2] " + GOOD in out.splitlines()


def test_a_marker_with_no_entry_alongside_an_unreferenced_one_keeps_the_main_banner():
    out = render(f"A [1] B [3].\n\nSources\n[1] {GOOD}\n[2] {GOOD}")
    assert out.startswith(formatter.BANNER + "\n\n")
    assert "[UNVERIFIED] [3] (no matching Sources entry)" in out.splitlines()
    assert UNREF_MARK + "[2] " + GOOD in out.splitlines()


def test_a_plain_failed_citation_is_unchanged():
    out = render(f"A [2].\n\nSources\n[2] {BAD}")
    assert out.startswith(formatter.BANNER + "\n\n")
    assert "[UNVERIFIED] [2] " + BAD in out.splitlines()
    assert UNREF_MARK not in out


def test_banner_wording():
    assert formatter.UNREFERENCED_BANNER == UNREF_BANNER
    assert "which statement" in formatter.UNREFERENCED_BANNER
    assert "true" not in formatter.UNREFERENCED_BANNER.lower()  # Article VI.5


def test_flagged_is_never_identical_to_the_same_text_as_cited():
    text = f"The policy does X.\n\nSources\n[1] {GOOD}"
    assert render(text) != text
    assert UNREF_BANNER in render(text)


# --- through ask (AC-4.10, 7.5) ----------------------------------------------------

_HEADER = re.compile(r"^--- (.+?) \| \w+ ---$", re.M)
QUESTION = "Why does authenticate retry?"


class UnlinkedSourceGenerator(StubGenerator):
    """Lists the first chunk it was shown under Sources but writes no [1] in the body."""

    def __init__(self) -> None:
        super().__init__(["unused"])

    def generate(self, messages):
        super().generate(messages)
        label = _HEADER.search(messages[1]["content"]).group(1)
        return f"Login retries on timeout.\n\nSources\n[1] {label}"


def _ask(tmp_path, generator):
    repo = build_history_repo(tmp_path / "repo")
    return online.ask(repo.path, QUESTION, config=config(tmp_path),
                      index_dir=tmp_path / "idx", **stubs(generator))


def test_ask_shows_the_new_banner_and_logs_the_unreferenced_marker(tmp_path):
    result = _ask(tmp_path, UnlinkedSourceGenerator())
    assert result.citation_outcome == "G"
    assert result.answer.startswith(UNREF_BANNER + "\n\n")
    assert UNREF_MARK + "[1] " in result.answer
    assert "[UNVERIFIED]" not in result.answer
    assert result.audit_log["citation"] == {"outcome": "G", "unverified": [1],
                                            "unreferenced": [1]}


def test_ask_log_of_an_ordinary_answer_has_no_unreferenced_key(tmp_path):
    result = _ask(tmp_path, CitingGenerator())
    assert result.audit_log["citation"] == {"outcome": "F", "unverified": []}


def test_ask_log_of_a_failed_citation_has_no_unreferenced_key(tmp_path):
    bad = "Login retries [1].\n\nSources\n[1] src/nowhere.py, lines 1-3 (indexed at abc1234)"
    result = _ask(tmp_path, StubGenerator([bad]))
    assert result.citation_outcome == "G"
    assert result.answer.startswith(formatter.BANNER + "\n\n")
    assert "unreferenced" not in result.audit_log["citation"]
