"""T5.4 tool allow list tests (tests-first).

Contract under test (Spec AC-3.2, AC-3.3; Plan D6):
  - tools.ALLOWED_TOOLS == ("git_blame", "git_log"); the dispatch table is the
    allow list, so config cannot add a tool (Article V.2)
  - tools.execute(repo, commit, call, *, settings) -> ToolOutput, never raises
    for bad model input: unknown tools, unexpected or invalid arguments come
    back as error outputs the model can read
  - git_log without n uses settings.git_log_limit
"""

import pytest

from codecompass.online.agent import tools
from codecompass.online.config import ToolsConfig
from codecompass.online.models import ToolCall
from tests.support.fixture_repo import build_history_repo

SETTINGS = ToolsConfig()


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    r = build_history_repo(tmp_path_factory.mktemp("hist") / "repo")
    return r.path, r.commits["wip"]


def run(repo, tool, **args):
    path, commit = repo
    return tools.execute(path, commit, ToolCall(tool=tool, args=args),
                         settings=SETTINGS)


def test_allowed_tools_constant():
    assert tools.ALLOWED_TOOLS == ("git_blame", "git_log")


def test_git_blame_and_git_log_succeed(repo):
    assert not run(repo, "git_blame", path="src/auth.py", lines="1-3").error
    out = run(repo, "git_log", path="src/auth.py", n=2)
    assert not out.error and len(out.commits) == 2


def test_git_log_defaults_n_to_limit(repo):
    out = run(repo, "git_log", path="src/auth.py")
    assert len(out.commits) == 3


@pytest.mark.parametrize("name", ["git_diff", "cat", "ls", "bash", ""])
def test_other_tools_rejected_with_clear_error(repo, name):
    out = run(repo, name, path="src/auth.py")
    assert out.error
    assert "not allowed" in out.text
    assert "git_blame" in out.text and "git_log" in out.text


def test_invalid_arguments_become_error_output(repo):
    out = run(repo, "git_blame", path="../secret")
    assert out.error and "inside the repository" in out.text


def test_unexpected_arguments_rejected(repo):
    out = run(repo, "git_log", path="src/auth.py", format="%H")
    assert out.error and "format" in out.text


def test_config_cannot_add_a_tool(repo):
    path, commit = repo
    widened = ToolsConfig(allowed_tools=("git_blame", "git_log", "git_diff"))
    out = tools.execute(path, commit, ToolCall(tool="git_diff", args={}),
                        settings=widened)
    assert out.error
