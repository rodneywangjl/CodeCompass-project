"""T1.1 repo validation and HEAD tests (tests-first)."""

import subprocess

import pytest

from codecompass.offline.git_source import GitSource, GitSourceError
from tests.support.fixture_repo import build_fixture_repo


def test_non_git_path_raises(tmp_path):
    with pytest.raises(GitSourceError):
        GitSource(tmp_path)


def test_zero_commit_repo_raises(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    with pytest.raises(GitSourceError):
        GitSource(tmp_path)


def test_head_sha_and_detached_head(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    assert src.head_sha() == fx.commits["rewritten"]
    subprocess.run(["git", "checkout", "-q", fx.commits["initial"]],
                   cwd=fx.path, check=True)
    assert GitSource(fx.path).head_sha() == fx.commits["initial"]


def test_uncommitted_edits_do_not_change_head(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    before = GitSource(fx.path).head_sha()
    (fx.path / "README.md").write_text("dirty\n")
    assert GitSource(fx.path).head_sha() == before
