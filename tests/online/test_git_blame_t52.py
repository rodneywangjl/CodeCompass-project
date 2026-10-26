"""T5.2 git_blame executor tests (tests-first).

Contract under test (Spec AC-3.2, AC-3.4; Plan D6, D7):
  - tools.git_blame(repo, commit, path, lines=None, *, timeout) -> ToolOutput
  - runs `git blame --porcelain [-L s,e] <commit> -- <path>` with shell=False
  - validates path and lines first (ToolArgumentError)
  - ToolOutput.commits: CommitRecord(sha, author, date, subject) per commit,
    date as YYYY-MM-DD from author-time and author-tz
  - ToolOutput.text: one line per commit, `<7-char sha> <date> <author> "<subject>"
    lines <ranges>`
  - blames the given commit, not HEAD
  - a timeout gives an error ToolOutput, not an exception
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


def test_whole_file_blame_lists_each_commit(repo):
    out = tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py", timeout=30)
    assert not out.error
    assert set(out.commits) == {record(repo, k)
                                for k in ("add_auth", "retry", "raise_retries")}


def test_line_range_limits_blame(repo):
    out = tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py",
                          lines="3", timeout=30)
    assert out.commits == (record(repo, "raise_retries"),)


def test_blames_the_given_commit_not_head(repo):
    out = tools.git_blame(repo.path, repo.commits["retry"], "src/auth.py",
                          lines="3", timeout=30)
    assert out.commits == (record(repo, "retry"),)


def test_text_is_one_line_per_commit_with_line_ranges(repo):
    out = tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py", timeout=30)
    lines = out.text.splitlines()
    assert len(lines) == 3
    sha7 = repo.commits["raise_retries"][:7]
    assert (f'{sha7} 2024-03-14 Alice Tan '
            f'"Handle flaky upstream service, raise MAX_RETRIES to 5" lines 3') in lines


def test_invalid_arguments_raise(repo):
    with pytest.raises(tools.ToolArgumentError):
        tools.git_blame(repo.path, repo.commits["wip"], "../x", timeout=30)
    with pytest.raises(tools.ToolArgumentError):
        tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py",
                        lines="1-99", timeout=30)


def test_runs_without_shell_and_with_separator(repo, monkeypatch):
    seen = []
    real = subprocess.run

    def spy(cmd, *args, **kwargs):
        seen.append((cmd, kwargs.get("shell")))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py", lines="1-2",
                    timeout=30)
    blame = [(c, s) for c, s in seen if "blame" in c]
    assert len(blame) == 1
    cmd, shell = blame[0]
    assert shell is False
    assert cmd[-2:] == ["--", "src/auth.py"]
    assert "--porcelain" in cmd and "-L" in cmd


def test_timeout_gives_error_output(repo, monkeypatch):
    real = subprocess.run

    def slow(cmd, *args, **kwargs):
        if "blame" in cmd:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", slow)
    out = tools.git_blame(repo.path, repo.commits["wip"], "src/auth.py", timeout=1)
    assert out.error
    assert "timed out" in out.text
    assert out.commits == ()
