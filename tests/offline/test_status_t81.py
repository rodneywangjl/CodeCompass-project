"""T8.1 index status tests (tests-first)."""

import subprocess

from codecompass.offline import status
from codecompass.offline.config import load_config
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder
from codecompass.offline import orchestrator


def test_empty_status_makes_no_writes(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    st = status(fx.path, config=load_config(None), index_dir=tmp_path / "idx")
    assert st.state == "empty" and st.indexed_commit is None
    assert not (tmp_path / "idx").exists()


def test_current_and_stale_and_metadata(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    st0 = status(fx.path, config=cfg, index_dir=base)
    assert st0.state == "empty"
    orchestrator.run(fx.path, config=cfg, index_dir=base, embedder=StubEmbedder())
    st1 = status(fx.path, config=cfg, index_dir=base)
    assert st1.state == "current"
    assert st1.embedder_model == "stub" and st1.schema_version == 1
    assert st1.last_run_at is not None
    (fx.path / "README.md").write_text("# new\n")
    subprocess.run(["git", "add", "-A"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "doc"], cwd=fx.path, check=True)
    st2 = status(fx.path, config=cfg, index_dir=base)
    assert st2.state == "stale"
