"""T1.2 change-set tests (tests-first)."""

import subprocess
from pathlib import Path

from codecompass.offline.git_source import GitSource


def _init(repo: Path):
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _commit(repo: Path, msg: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()


def test_added_modified_deleted(tmp_path):
    repo = tmp_path / "r"
    _init(repo)
    (repo / "a.txt").write_text("1")
    c1 = _commit(repo, "one")
    (repo / "a.txt").write_text("2")
    (repo / "b.txt").write_text("new")
    c2 = _commit(repo, "two")
    cs = GitSource(repo).diff(c1, c2)
    assert cs.modified == ["a.txt"] and cs.added == ["b.txt"] and cs.deleted == []


def test_rename_is_delete_plus_add(tmp_path):
    repo = tmp_path / "r"
    _init(repo)
    (repo / "a.txt").write_text("x")
    c1 = _commit(repo, "one")
    subprocess.run(["git", "mv", "a.txt", "c.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "mv"], cwd=repo, check=True)
    c2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                        capture_output=True, text=True, check=True).stdout.strip()
    cs = GitSource(repo).diff(c1, c2)
    assert cs.deleted == ["a.txt"] and cs.added == ["c.txt"]


def test_diff_from_none_lists_everything_and_revert_is_empty(tmp_path):
    repo = tmp_path / "r"
    _init(repo)
    (repo / "a.txt").write_text("v1")
    (repo / "b.txt").write_text("b")
    c1 = _commit(repo, "one")
    (repo / "a.txt").write_text("v2")
    _commit(repo, "two")
    (repo / "a.txt").write_text("v1")
    c3 = _commit(repo, "three")
    src = GitSource(repo)
    assert sorted(src.diff(None, c1).added) == ["a.txt", "b.txt"]
    cs = src.diff(c1, c3)
    assert cs.added == [] and cs.modified == [] and cs.deleted == []


def test_directory_move_lists_deletes_and_adds(tmp_path):
    repo = tmp_path / "r"
    _init(repo)
    (repo / "d").mkdir()
    (repo / "d" / "x.txt").write_text("x")
    (repo / "d" / "y.txt").write_text("y")
    c1 = _commit(repo, "one")
    subprocess.run(["git", "mv", "d", "e"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "mvdir"], cwd=repo, check=True)
    c2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                        capture_output=True, text=True, check=True).stdout.strip()
    cs = GitSource(repo).diff(c1, c2)
    assert sorted(cs.deleted) == ["d/x.txt", "d/y.txt"]
    assert sorted(cs.added) == ["e/x.txt", "e/y.txt"]
