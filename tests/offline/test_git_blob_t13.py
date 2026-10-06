"""T1.3 blob reads and sizes tests (tests-first)."""

import subprocess

import pytest

from codecompass.offline.git_source import GitSource, GitSourceError
from tests.support.fixture_repo import build_fixture_repo


def test_read_blob_returns_committed_content(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    head = GitSource(fx.path).head_sha()
    (fx.path / "README.md").write_text("dirty\n")
    data = GitSource(fx.path).read_blob(head, "README.md")
    assert data == b"# Fixture rewritten\n"


def test_untracked_and_ignored_invisible(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    head = GitSource(fx.path).head_sha()
    src = GitSource(fx.path)
    with pytest.raises(GitSourceError):
        src.read_blob(head, "untracked.txt")
    with pytest.raises(GitSourceError):
        src.read_blob(head, "ignored.log")


def test_blob_size_and_crlf_and_unicode(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=fx.path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=fx.path, check=True)
    (fx.path / "win.txt").write_bytes(b"a\r\nb\r\n")
    (fx.path / "ünïcode.py").write_bytes(b"x = 1\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "add", "-A"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "edge"], cwd=fx.path, check=True)
    src = GitSource(fx.path)
    head = src.head_sha()
    assert src.read_blob(head, "win.txt") == b"a\r\nb\r\n"
    assert src.blob_size(head, "win.txt") == 6
    assert src.read_blob(head, "ünïcode.py") == b"x = 1\n"


def test_symlink_and_submodule_flagged(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=fx.path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=fx.path, check=True)
    (fx.path / "real.txt").write_text("real\n")
    subprocess.run(["git", "add", "real.txt"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "real"], cwd=fx.path, check=True)
    link_sha = subprocess.run(["git", "rev-parse", "HEAD:real.txt"], cwd=fx.path,
                              capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", "120000",
                    link_sha, "link.txt"], cwd=fx.path, check=True)
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", "160000",
                    link_sha, "submod"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "links"], cwd=fx.path, check=True)
    src = GitSource(fx.path)
    head = src.head_sha()
    assert src.entry_kind(head, "link.txt") == "symlink"
    assert src.entry_kind(head, "submod") == "submodule"
    assert src.entry_kind(head, "real.txt") == "blob"
    with pytest.raises(GitSourceError):
        src.read_blob(head, "link.txt")
