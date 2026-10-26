"""T0.5 tool settings validation tests (tests-first).

Contract under test (Spec AC-3.9, FR-6; Plan §7; Article V.1, V.2 as of 1.3.0):
  - tools.max_verifier_rounds is configurable (default 3) but must be a
    non-negative integer; anything else fails load_online_config loudly,
    naming Article V.1
  - tools.allowed_tools may narrow the allow list, never extend it; an
    unknown tool fails load_online_config loudly, naming Article V.2
  - tools.execute refuses a tool that settings switch off
"""

import pytest

from codecompass.online.agent import tools
from codecompass.online.config import ToolsConfig, load_online_config
from codecompass.online.models import ToolCall
from tests.support.fixture_repo import build_history_repo


def load(tmp_path, body):
    f = tmp_path / "codecompass.toml"
    f.write_text("[tools]\n" + body + "\n")
    return load_online_config(f)


def test_defaults(tmp_path):
    cfg = load_online_config(None)
    assert cfg.tools.max_verifier_rounds == 3
    assert cfg.tools.allowed_tools == ("git_blame", "git_log")


@pytest.mark.parametrize("value", [0, 1, 5])
def test_round_limit_can_be_raised_or_lowered(tmp_path, value):
    assert load(tmp_path, f"max_verifier_rounds = {value}").tools.max_verifier_rounds == value


@pytest.mark.parametrize("value", ["-1", "2.5", '"3"', "true"])
def test_invalid_round_limit_fails_loudly(tmp_path, value):
    with pytest.raises(ValueError, match="Article V.1"):
        load(tmp_path, f"max_verifier_rounds = {value}")


def test_allowed_tools_can_narrow(tmp_path):
    cfg = load(tmp_path, 'allowed_tools = ["git_log"]')
    assert cfg.tools.allowed_tools == ("git_log",)


def test_allowed_tools_cannot_add_a_tool(tmp_path):
    with pytest.raises(ValueError, match="Article V.2"):
        load(tmp_path, 'allowed_tools = ["git_log", "cat"]')


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    r = build_history_repo(tmp_path_factory.mktemp("hist") / "repo")
    return r.path, r.commits["wip"]


def test_execute_refuses_a_tool_switched_off(repo):
    path, commit = repo
    narrowed = ToolsConfig(allowed_tools=("git_log",))
    out = tools.execute(path, commit,
                        ToolCall(tool="git_blame", args={"path": "src/auth.py"}),
                        settings=narrowed)
    assert out.error
    assert "git_blame" in out.text and "switched off" in out.text
    ok = tools.execute(path, commit,
                       ToolCall(tool="git_log", args={"path": "src/auth.py", "n": 1}),
                       settings=narrowed)
    assert not ok.error
