"""T9.3 CLI tests (tests-first; stub embedder keeps the suite model-free)."""

from codecompass.offline import cli
from codecompass.offline.config import load_config
from tests.support.fixture_repo import build_fixture_repo


def _args(repo, base, *extra):
    return [str(repo), "--index-dir", str(base), *extra]


def _index_args(repo, base, *extra):
    return [*_args(repo, base), "--embedder", "stub", *extra]


def test_index_status_check_round_trip(tmp_path, capsys):
    fx = build_fixture_repo(tmp_path / "repo")
    base = tmp_path / "idx"
    assert cli.main(["index", *_index_args(fx.path, base)]) == 0
    out = capsys.readouterr().out
    assert "full" in out
    assert cli.main(["status", *_args(fx.path, base)]) == 0
    assert "current" in capsys.readouterr().out
    assert cli.main(["check", *_args(fx.path, base), "--embedder", "stub"]) == 0


def test_index_dry_run_full_and_failure_codes(tmp_path, capsys):
    fx = build_fixture_repo(tmp_path / "repo")
    base = tmp_path / "idx"
    assert cli.main(["index", *_index_args(fx.path, base), "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out
    assert cli.main(["index", *_index_args(fx.path, base), "--full"]) == 0
    assert cli.main(["index", str(tmp_path / "nope"),
                     "--index-dir", str(base)]) == 1
    assert cli.main(["check", *_args(fx.path, base), "--embedder", "stub"]) == 0
    assert "consistent" in capsys.readouterr().out.lower()
    # Checking an index that was never built fails loudly.
    assert cli.main(["check", *_args(tmp_path / "other",
                                     tmp_path / "idx2")]) == 1
