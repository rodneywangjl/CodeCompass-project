"""T9.2 citation checker outcome F tests (tests-first).

Contract under test (Spec AC-4.1, AC-4.3; Plan D9):
  - checker.check(answer, chunks, commits) -> CitationResult
    chunks: RetrievedChunk list placed in context; commits: CommitRecord list
    from tool results placed in context
  - a code entry is verified when every cited line lies inside retrieved
    chunks of the same path whose commit starts with the cited hash; ranges
    may span adjacent chunks
  - a commit entry is verified when its hash prefixes a commit record
  - all verified -> outcome "F", every source marked verified, no unverified
"""

from codecompass.online.agent.tools import CommitRecord
from codecompass.online.citation import checker
from codecompass.online.context import RetrievedChunk

SHA = "a1b2c3d" + "0" * 33
TOOL_SHA = "f00dbab" + "1" * 33


def chunk(path, start, end, sha=SHA):
    return RetrievedChunk(chunk_id=f"{path}:{start}", text="x", path=path,
                          start_line=start, end_line=end, language="python",
                          commit_sha=sha)


CHUNKS = [chunk("src/auth.py", 1, 20), chunk("src/auth.py", 21, 40),
          chunk("src/util.py", 5, 9)]
COMMITS = [CommitRecord(TOOL_SHA, "Alice Tan", "2024-03-14", "handle flaky upstream")]


def answer(*entries):
    markers = " ".join(f"[{i}]" for i in range(1, len(entries) + 1))
    lines = "\n".join(f"[{i}] {e}" for i, e in enumerate(entries, 1))
    return f"Claims {markers}.\n\nSources\n{lines}"


def test_exact_chunk_citation_is_f():
    result = checker.check(answer("src/auth.py, lines 1-20 (indexed at a1b2c3d)"),
                           CHUNKS, COMMITS)
    assert result.outcome == "F"
    assert result.unverified == []
    assert all(s.verified for s in result.sources)


def test_sub_range_inside_a_chunk_is_f():
    result = checker.check(answer("src/util.py, lines 6-8 (indexed at a1b2c3d)"),
                           CHUNKS, COMMITS)
    assert result.outcome == "F"


def test_range_spanning_adjacent_chunks_is_f():
    result = checker.check(answer("src/auth.py, lines 15-30 (indexed at a1b2c3d)"),
                           CHUNKS, COMMITS)
    assert result.outcome == "F"


def test_commit_and_code_together_is_f():
    result = checker.check(
        answer("src/auth.py, lines 1-5 (indexed at a1b2c3d)",
               'Commit f00dbab, "handle flaky upstream", Alice Tan, 2024-03-14'),
        CHUNKS, COMMITS)
    assert result.outcome == "F"
    assert [s.verified for s in result.sources] == [True, True]


def test_result_keeps_answer_text():
    text = answer("src/auth.py, lines 1-5 (indexed at a1b2c3d)")
    assert checker.check(text, CHUNKS, COMMITS).answer_text == text
