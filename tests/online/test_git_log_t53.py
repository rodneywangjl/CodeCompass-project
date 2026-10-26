"""T5.3 git_log executor tests (tests-first).

Contract under test (Spec AC-3.2, AC-3.4, AC-3.7; Plan D6, D7):
  - tools.git_log(repo, commit, path, n, *, limit, timeout) -> ToolOutput
  - runs `git log --format=%H%x1f%an%x1f%ad%x1f%s --date=short -n <n> <commit> -- <path>`
    with shell=False; n validated against limit
  - fields split on 0x1F, so an author with a space and a subject with a
    comma parse exactly
  - newest first; logs the given commit's history, not HEAD's
  - a timeout gives an error ToolOutput; a path with no history at the
    commit is rejected by validation
"""

import subprocess

import pytest

from codecompass.online.agent import tools
from tests.support.fixture_repo import HISTORY, build_history_repo

META = {key: (author, date, subject) for key, author, _, date, subject in HISTORY}


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return build_history_repo(tmp_path_factory.mktemp("hist") / "repo")


def record(repo, key):
    author, date, subject = META[key]
    return tools.CommitRecord(sha=repo.commits[key], author=author, date=date,
                              subject=subject)


def log(repo, commit_key="wip", path="src/auth.py", n=10, limit=20):
    return tools.git_log(repo.path, repo.commits[commit_key], path, n,
                         limit=limit, timeout=30)


def test_entries_newest_first_with_exact_fields(repo):
    out = log(repo)
    assert not out.error
    assert out.commits == tuple(record(repo, k)
                                for k in ("raise_retries", "retry", "add_auth"))


def test_comma_subject_and_spaced_author_rendered(repo):
    sha7 = repo.commits["raise_retries"][:7]
    assert (f'{sha7} 2024-03-14 Alice Tan '
            f'"Handle flaky upstream service, raise MAX_RETRIES to 5"'
            ) in log(repo).text.splitlines()


def test_n_limits_entries(repo):
    assert log(repo, n=1).commits == (record(repo, "raise_retries"),)


def test_n_over_limit_rejected(repo):
    with pytest.raises(tools.ToolArgumentError):
        log(repo, n=21, limit=20)


def test_logs_the_given_commit_not_head(repo):
    assert log(repo, commit_key="retry").commits == (
        record(repo, "retry"), record(repo, "add_auth"))


def test_file_absent_at_commit_rejected(repo):
    with pytest.raises(tools.ToolArgumentError):
        log(repo, commit_key="retry", path="src/util.py")


def test_runs_without_shell_and_with_separator(repo, monkeypatch):
    seen = []
    real = subprocess.run

    def spy(cmd, *args, **kwargs):
        seen.append((cmd, kwargs.get("shell")))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    log(repo, n=3)
    cmd, shell = next((c, s) for c, s in seen if "log" in c)
    assert shell is False
    assert cmd[-2:] == ["--", "src/auth.py"]
    assert "-n" in cmd and cmd[cmd.index("-n") + 1] == "3"


def test_timeout_gives_error_output(repo, monkeypatch):
    real = subprocess.run

    def slow(cmd, *args, **kwargs):
        if "log" in cmd:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", slow)
    out = log(repo)
    assert out.error and "timed out" in out.text
