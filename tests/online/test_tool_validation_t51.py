"""T5.1 tool argument validation tests (tests-first).

Contract under test (Spec AC-3.3, AC-3.4; Plan D6):
  - codecompass.online.agent.tools.ToolArgumentError (a ValueError)
  - validate_path(repo, commit, path) -> normalised repo-relative path;
    rejects absolute paths, a leading "-", any ".." component, and paths
    that are not a file at the commit. No character blacklist: names like
    "app/(auth)/page.tsx" or "Outer$Inner.java" are valid.
  - validate_lines(spec, line_count) -> (start, end) for "N" or "N-M" with
    1 <= N <= M <= line_count
  - validate_n(n, limit) -> int in 1..limit
"""

import subprocess

import pytest

from codecompass.online.agent import tools
from tests.support.fixture_repo import build_history_repo


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    r = build_history_repo(tmp_path_factory.mktemp("hist") / "repo")
    for rel in ("app/(auth)/page.tsx", "src/Outer$Inner.java"):
        p = r.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t",
                                 "commit", "-q", "-m", "odd names"]):
        subprocess.run(["git", *args], cwd=r.path, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=r.path,
                          capture_output=True, text=True).stdout.strip()
    return r.path, head


def test_valid_path_passes_and_is_normalised(repo):
    path, commit = repo
    assert tools.validate_path(path, commit, "src/auth.py") == "src/auth.py"
    assert tools.validate_path(path, commit, "./src//auth.py") == "src/auth.py"


@pytest.mark.parametrize("name", ["app/(auth)/page.tsx", "src/Outer$Inner.java"])
def test_real_names_with_special_characters_pass(repo, name):
    path, commit = repo
    assert tools.validate_path(path, commit, name) == name


@pytest.mark.parametrize("bad", [
    "../etc/passwd", "src/../../x.py", "/etc/passwd", "-rf", "--output=x",
    "", ".", "src", "src/missing.py",
])
def test_bad_paths_rejected(repo, bad):
    path, commit = repo
    with pytest.raises(tools.ToolArgumentError):
        tools.validate_path(path, commit, bad)


def test_path_must_exist_at_the_given_commit(repo, tmp_path):
    path, _ = repo
    first = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                           cwd=path, capture_output=True, text=True).stdout.strip()
    with pytest.raises(tools.ToolArgumentError):
        tools.validate_path(path, first, "src/util.py")


def test_errors_are_value_errors():
    assert issubclass(tools.ToolArgumentError, ValueError)


@pytest.mark.parametrize("spec,expected", [("42-58", (42, 58)), ("7", (7, 7)),
                                           ("1-60", (1, 60))])
def test_valid_line_ranges(spec, expected):
    assert tools.validate_lines(spec, line_count=60) == expected


@pytest.mark.parametrize("spec", ["58-42", "0-3", "a-b", "3-", "", "1-61",
                                  "61", "1;rm -rf /"])
def test_bad_line_ranges_rejected(spec):
    with pytest.raises(tools.ToolArgumentError):
        tools.validate_lines(spec, line_count=60)


@pytest.mark.parametrize("n", [1, 20, "5"])
def test_valid_n(n):
    assert tools.validate_n(n, limit=20) == int(n)


@pytest.mark.parametrize("n", [0, 21, -1, "x", True, 2.5])
def test_bad_n_rejected(n):
    with pytest.raises(tools.ToolArgumentError):
        tools.validate_n(n, limit=20)
