"""T6.3 no writes on invalid input tests (tests-first)."""

import subprocess

import pytest

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSourceError
from tests.support.stub_embedder import StubEmbedder


def _run(repo, base):
    return orchestrator.run(repo, config=load_config(None),
                            index_dir=base, embedder=StubEmbedder())


def test_non_repo_writes_nothing(tmp_path):
    with pytest.raises(GitSourceError):
        _run(tmp_path / "nope", tmp_path / "idx")
    assert not (tmp_path / "idx").exists()


def test_zero_commit_repo_writes_nothing(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    with pytest.raises(GitSourceError):
        _run(repo, tmp_path / "idx")
    assert not (tmp_path / "idx").exists()
