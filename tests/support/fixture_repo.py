"""Scripted git fixture repository for offline-pipeline tests (T0.4)."""

from __future__ import annotations

import os
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


# History fixture for verifier-tool tests (T0.2): (key, author, email, date, subject).
HISTORY = [
    ("add_auth", "Alice Tan", "alice@example.com", "2024-01-10", "Add auth client"),
    ("retry", "Bob Lee", "bob@example.com", "2024-02-20",
     "Fix auth timeout by adding retry logic"),
    ("raise_retries", "Alice Tan", "alice@example.com", "2024-03-14",
     "Handle flaky upstream service, raise MAX_RETRIES to 5"),
    ("wip", "Carol Ng", "carol@example.com", "2024-04-01", "wip"),
]
AUTH_COMMITS = {"add_auth", "retry", "raise_retries"}

AUTH_V1 = (
    "import time\n\n\n"
    "def authenticate(client, user, password):\n"
    "    return client.login(user, password)\n"
)
AUTH_V2 = (
    "import time\n\nMAX_RETRIES = 3\n\n\n"
    "def authenticate(client, user, password):\n"
    "    for attempt in range(MAX_RETRIES):\n"
    "        try:\n"
    "            return client.login(user, password)\n"
    "        except TimeoutError:\n"
    "            time.sleep(2 ** attempt)\n"
    '    raise TimeoutError("login failed after retries")\n'
)
AUTH_V3 = AUTH_V2.replace("MAX_RETRIES = 3", "MAX_RETRIES = 5")
UTIL = "def noop():\n    return None\n"

_HISTORY_FILES = {
    "add_auth": {"src/auth.py": AUTH_V1},
    "retry": {"src/auth.py": AUTH_V2},
    "raise_retries": {"src/auth.py": AUTH_V3},
    "wip": {"src/util.py": UTIL},
}


def build_history_repo(root: str | Path) -> FixtureRepo:
    """Create a repo with known authors, dates and messages for git blame/log tests."""
    repo = Path(root)
    repo.mkdir(parents=True, exist_ok=True)
    assert _git(repo, "init", "-q").returncode == 0
    commits: dict[str, str] = {}
    for key, author, email, date, subject in HISTORY:
        for rel, text in _HISTORY_FILES[key].items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text)
        _git(repo, "add", "-A")
        stamp = f"{date}T12:00:00+00:00"
        r = _git(repo, "-c", f"user.name={author}", "-c", f"user.email={email}",
                 "commit", "-q", "-m", subject,
                 env={**os.environ, "GIT_AUTHOR_DATE": stamp,
                      "GIT_COMMITTER_DATE": stamp})
        assert r.returncode == 0, r.stderr
        commits[key] = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return FixtureRepo(path=repo, commits=commits)
