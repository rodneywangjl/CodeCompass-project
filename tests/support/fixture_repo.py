"""Scripted git fixture repository for offline-pipeline tests (T0.4)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MAIN_V1 = 'def hello():\n    return "hi"\n\n\ndef helper():\n    return 1\n'
MAIN_V2 = 'def hello_v2():\n    return "hi"\n\n\ndef helper():\n    return 1\n'
APP_JS = "export function run() {\n  return 42;\n}\n"
OVERSIZE = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(300))
BROKEN = "def broken(:\n    pass\n"
GO_TOOL = 'package main\n\nfunc main() {}\n'


@dataclass
class FixtureRepo:
    path: Path
    commits: dict = field(default_factory=dict)


def _git(repo: Path, *args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, **kw
    )


def _commit(repo: Path, message: str) -> str:
    r = _git(repo, "-c", "user.name=t", "-c", "user.email=t@t",
             "commit", "-q", "-m", message)
    assert r.returncode == 0, r.stderr
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def build_fixture_repo(root: str | Path) -> FixtureRepo:
    """Create a scripted repo covering add/modify/delete/rename/rewrite + edge files."""
    repo = Path(root)
    repo.mkdir(parents=True, exist_ok=True)
    assert _git(repo, "init", "-q").returncode == 0
    commits: dict[str, str] = {}

    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text(MAIN_V1)
    (repo / "src" / "app.js").write_text(APP_JS)
    (repo / "src" / "oversize.py").write_text(OVERSIZE)
    (repo / "src" / "broken.py").write_text(BROKEN)
    (repo / "src" / "tool.go").write_text(GO_TOOL)
    (repo / "image.bin").write_bytes(b"\x89PNG\x00\x01\x02binary-bytes")
    (repo / ".env").write_text("SECRET=topsecret\n")
    (repo / ".gitignore").write_text("ignored.log\n")
    (repo / "ignored.log").write_text("noise\n")
    (repo / "README.md").write_text("# Fixture\n")
    _git(repo, "add", "-A")
    commits["initial"] = _commit(repo, "initial")

    (repo / "src" / "main.py").write_text(MAIN_V2)
    _git(repo, "add", "-A")
    commits["modify"] = _commit(repo, "modify main")

    _git(repo, "rm", "-q", "src/app.js")
    commits["delete"] = _commit(repo, "delete app.js")

    _git(repo, "mv", "src/main.py", "src/core.py")
    commits["rename"] = _commit(repo, "rename main to core")

    (repo / "src" / "core.py").write_text(MAIN_V2.replace("return 1", "return 2"))
    _git(repo, "mv", "src/core.py", "src/engine.py")
    _git(repo, "add", "-A")
    commits["rename_modify"] = _commit(repo, "rename and modify")

    # History rewrite: back to initial, then diverge.
    assert _git(repo, "reset", "--hard", "-q", commits["initial"]).returncode == 0
    (repo / "README.md").write_text("# Fixture rewritten\n")
    _git(repo, "add", "-A")
    commits["rewritten"] = _commit(repo, "rewritten history")

    (repo / "untracked.txt").write_text("untracked\n")
    return FixtureRepo(path=repo, commits=commits)
