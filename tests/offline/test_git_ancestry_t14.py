"""T1.4 ancestry tests (tests-first)."""

from codecompass.offline.git_source import GitSource
from tests.support.fixture_repo import build_fixture_repo


def test_is_ancestor_parent_true_unrelated_false(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    assert src.is_ancestor(fx.commits["initial"], fx.commits["rewritten"])
    # Rewritten-away commit is not an ancestor of HEAD.
    assert not src.is_ancestor(fx.commits["modify"], fx.commits["rewritten"])
    assert not src.is_ancestor(fx.commits["rewritten"], fx.commits["initial"])


def test_unresolvable_sha_returns_false(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    assert src.is_ancestor("deadbee" * 5, src.head_sha()) is False
    assert src.is_ancestor(src.head_sha(), "deadbee" * 5) is False
