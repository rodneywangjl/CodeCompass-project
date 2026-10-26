"""T0.2 history fixture repo tests (tests-first).

Contract under test (Tasks 002 T0.2, Plan D7):
  - tests.support.fixture_repo.build_history_repo(root) -> HistoryRepo
  - HistoryRepo.commits maps each HISTORY key to its full commit sha
  - Commits carry the known authors, dates and subjects in HISTORY, so
    git_log / git_blame tests can assert exact values
  - An author name with a space and a subject with a comma are included
    (exercises the 0x1F log format and porcelain parsing)
  - The last commit has an uninformative message (Article V.5)
  - Building twice gives the same shas (fixed identities and dates)
"""

import subprocess

from tests.support import fixture_repo


def _git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _blame_shas(repo, path):
    """Line number (1-based) -> full sha, from git blame --porcelain."""
    out = _git(repo, "blame", "--porcelain", "HEAD", "--", path)
    shas, line_no = {}, 0
    for line in out.splitlines():
        parts = line.split(" ")
        if len(parts[0]) == 40 and len(parts) >= 3 and parts[2].isdigit():
            line_no = int(parts[2])
            shas[line_no] = parts[0]
    return shas


def test_commits_have_known_author_date_and_subject(tmp_path):
    repo = fixture_repo.build_history_repo(tmp_path / "hist")
    for key, author, _email, date, subject in fixture_repo.HISTORY:
        sha = repo.commits[key]
        out = _git(repo.path, "show", "-s", "--format=%an%x1f%ad%x1f%s",
                   "--date=short", sha)
        assert out.strip().split("\x1f") == [author, date, subject]


def test_git_log_on_auth_file_lists_its_commits_newest_first(tmp_path):
    repo = fixture_repo.build_history_repo(tmp_path / "hist")
    out = _git(repo.path, "log", "--format=%H%x1f%an%x1f%ad%x1f%s",
               "--date=short", "HEAD", "--", "src/auth.py")
    entries = [line.split("\x1f") for line in out.splitlines()]
    expected = [
        [repo.commits[key], author, date, subject]
        for key, author, _email, date, subject in reversed(fixture_repo.HISTORY)
        if key in fixture_repo.AUTH_COMMITS
    ]
    assert entries == expected
    assert len(entries) == 3


def test_git_blame_attributes_lines_to_expected_commits(tmp_path):
    repo = fixture_repo.build_history_repo(tmp_path / "hist")
    shas = _blame_shas(repo.path, "src/auth.py")
    lines = (repo.path / "src" / "auth.py").read_text().splitlines()
    assert lines[0] == "import time"
    assert shas[1] == repo.commits["add_auth"]
    assert lines[2] == "MAX_RETRIES = 5"
    assert shas[3] == repo.commits["raise_retries"]
    assert lines[6].startswith("    for attempt")
    assert shas[7] == repo.commits["retry"]


def test_history_includes_hard_to_parse_and_uninformative_commits(tmp_path):
    repo = fixture_repo.build_history_repo(tmp_path / "hist")
    authors = {author for _, author, _, _, _ in fixture_repo.HISTORY}
    subjects = [subject for _, _, _, _, subject in fixture_repo.HISTORY]
    assert any(" " in a for a in authors)
    assert any("," in s for s in subjects)
    assert fixture_repo.HISTORY[-1][4] == "wip"
    head = _git(repo.path, "rev-parse", "HEAD").strip()
    assert head == repo.commits[fixture_repo.HISTORY[-1][0]]


def test_build_is_deterministic(tmp_path):
    a = fixture_repo.build_history_repo(tmp_path / "a")
    b = fixture_repo.build_history_repo(tmp_path / "b")
    assert a.commits == b.commits
