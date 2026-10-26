"""T9.5 harness-copied commit metadata tests (tests-first).

Contract under test (Spec AC-4.6, FR-16; Plan D10):
  - after check(), each verified commit entry carries the subject, author and
    date of the matching commit record, whatever the model wrote
  - the Sources line in result.answer_text is rewritten to the harness values,
    so the rendered answer shows them
  - a commit entry whose hash matches no record stays unverified and is not
    rewritten
  - records from git_blame and git_log are treated the same
"""

from codecompass.online.agent import tools
from codecompass.online.citation import checker, formatter
from tests.support.fixture_repo import build_history_repo


def test_model_details_replaced_by_tool_record():
    rec = tools.CommitRecord("f00dbab" + "1" * 33, "Alice Tan", "2024-03-14",
                             "Handle flaky upstream service, raise MAX_RETRIES to 5")
    text = ('Raised for a flaky upstream [1].\n\nSources\n'
            '[1] Commit f00dbab, "make it faster", Mallory, 1999-01-01')
    result = checker.check(text, [], [rec])
    entry = result.sources[0]
    assert entry.verified
    assert (entry.subject, entry.author, entry.date) == (
        rec.subject, rec.author, rec.date)
    expected_line = (f'[1] Commit f00dbab, "{rec.subject}", Alice Tan, 2024-03-14')
    assert expected_line in result.answer_text.splitlines()
    assert "Mallory" not in result.answer_text
    assert "Mallory" not in formatter.render(result)


def test_unknown_hash_not_rewritten_and_unverified():
    text = 'X [1].\n\nSources\n[1] Commit deadbee, "invented", Bob, 2024-01-01'
    result = checker.check(text, [], [])
    assert not result.sources[0].verified
    assert result.sources[0].author == "Bob"
    assert result.answer_text == text


def test_records_from_real_blame_and_log(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    head = repo.commits["wip"]
    blame = tools.git_blame(repo.path, head, "src/auth.py", lines="3", timeout=30)
    log = tools.git_log(repo.path, head, "src/auth.py", 10, limit=20, timeout=30)
    sha7 = repo.commits["raise_retries"][:7]
    retry7 = repo.commits["retry"][:7]
    text = (f"Raised [1], retries added [2].\n\nSources\n"
            f'[1] Commit {sha7}, "?", ?, 2000-01-01\n'
            f'[2] Commit {retry7}, "?", ?, 2000-01-01')
    result = checker.check(text, [], list(blame.commits) + list(log.commits))
    assert result.outcome == "F"
    assert [s.author for s in result.sources] == ["Alice Tan", "Bob Lee"]
