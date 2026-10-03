"""T9.2 dry-run tests (tests-first)."""

import subprocess

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSource
from codecompass.offline.meta import read_meta
from tests.support.stub_embedder import StubEmbedder


def _setup(repo):
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "v1"], cwd=repo, check=True)


def test_dry_run_lists_changes_without_writing(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    cfg = load_config(None)
    orchestrator.run(repo, config=cfg, index_dir=base, embedder=StubEmbedder())
    idx = orchestrator.index_path_for(repo, base)
    meta_before = read_meta(idx).indexed_commit
    (repo / "a.py").write_text("def alpha():\n    return 2\n")
    (repo / "b.py").write_text("def beta():\n    return 3\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "v2"], cwd=repo, check=True)

    report = orchestrator.dry_run(repo, config=cfg, index_dir=base)
    assert report.files_added == 1 and report.files_modified == 1
    assert report.chunks_added > 0
    # Nothing written: same indexed commit, no lock file, no new store files.
    assert read_meta(idx).indexed_commit == meta_before
    (idx / "index.lock").unlink(missing_ok=True)  # leftover from real run above
    report = orchestrator.dry_run(repo, config=cfg, index_dir=base)
    assert not (idx / "index.lock").exists()
    assert GitSource(repo).head_sha() != meta_before  # would change for real
    # And a real run after the dry run still works.
    real = orchestrator.run(repo, config=cfg, index_dir=base,
                            embedder=StubEmbedder())
    assert real.mode == "incremental"


def test_dry_run_on_empty_index_creates_nothing(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    report = orchestrator.dry_run(repo, config=load_config(None), index_dir=base)
    assert report.mode in ("dry-run-full", "dry-run")
    assert not (base).exists()
