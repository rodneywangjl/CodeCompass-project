"""T0.4 fixture-repo builder tests (tests-first)."""

import subprocess

from tests.support.fixture_repo import build_fixture_repo


def _show(repo, sha, path):
    return subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=repo, capture_output=True, check=True, text=True,
    ).stdout


def test_builder_commit_contents(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    assert fx.commits["initial"] and fx.commits["modify"]
    assert "def hello" in _show(fx.path, fx.commits["initial"], "src/main.py")
    assert "def hello_v2" in _show(fx.path, fx.commits["modify"], "src/main.py")
    # Deleted file absent at later commit.
    gone = subprocess.run(
        ["git", "show", f"{fx.commits['delete']}:src/app.js"],
        cwd=fx.path, capture_output=True,
    )
    assert gone.returncode != 0
    # Rename visible as new path.
    assert "def hello" in _show(fx.path, fx.commits["rename"], "src/core.py")


def test_rewrite_makes_old_sha_unreachable(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    old = fx.commits["modify"]
    assert old != fx.commits["rewritten"]
    r = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old, "HEAD"],
        cwd=fx.path, capture_output=True,
    )
    assert r.returncode != 0, "rewritten-away commit must be unreachable from HEAD"


def test_fixture_has_edge_case_files(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    head = fx.commits["rewritten"]
    assert "SECRET" in _show(fx.path, head, ".env")
    assert (fx.path / "untracked.txt").exists()  # untracked, uncommitted
