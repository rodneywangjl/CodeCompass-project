"""T10.2 end-to-end smoke test with the real embedder (model-marked)."""

import json
import subprocess

import pytest

pytestmark = pytest.mark.model

from codecompass.offline import check_consistency, ensure_current, open_index
from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.embedding import CodeEmbedder


def test_real_embedder_end_to_end(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    (repo / "b.py").write_text("def beta():\n    return 2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "v1"], cwd=repo, check=True)
    cfg = load_config(None)
    base = tmp_path / "idx"

    r1 = ensure_current(repo, config=cfg, index_dir=base,
                        embedder=CodeEmbedder(cfg.embedder))
    assert r1.ok and r1.status == "current"
    # Second call is up to date without touching the model.
    r2 = ensure_current(repo, config=cfg, index_dir=base,
                        embedder=CodeEmbedder(cfg.embedder))
    assert r2.ok and r2.report.mode == "up-to-date"

    handles = open_index(repo, config=cfg, index_dir=base)
    try:
        assert check_consistency(handles.vector, handles.keyword).ok
    finally:
        handles.close()
    # Report timings persisted for the performance target (C6).
    runs = sorted((orchestrator.index_path_for(repo, base) / "runs").glob("*.json"))
    assert runs, "expected persisted run reports"
    saved = json.loads(runs[-1].read_text())
    assert saved["to_commit"] and "embed" in saved["timings"]
