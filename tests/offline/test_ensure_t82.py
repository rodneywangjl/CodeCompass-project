"""T8.2 ensure_current fast path and stale path tests (tests-first)."""

import os
import subprocess
import sys

from codecompass.offline import ensure_current
from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def test_stale_runs_update_and_returns_current(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    r1 = ensure_current(fx.path, config=cfg, index_dir=base,
                        embedder=StubEmbedder())
    assert r1.ok and r1.status == "current"
    (fx.path / "README.md").write_text("# more\n")
    subprocess.run(["git", "add", "-A"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "doc"], cwd=fx.path, check=True)
    r2 = ensure_current(fx.path, config=cfg, index_dir=base,
                        embedder=StubEmbedder())
    assert r2.ok and r2.status == "current"
    assert r2.report is not None and r2.report.to_commit is not None


def test_fast_path_reads_no_source_writes_nothing_no_heavy_imports(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    orchestrator.run(fx.path, config=cfg, index_dir=base, embedder=StubEmbedder())
    idx = orchestrator.index_path_for(fx.path, base)
    before = {p.name: p.stat().st_mtime_ns for p in idx.iterdir()}
    script = (
        "import sys; "
        "from codecompass.offline import ensure_current; "
        "from codecompass.offline.config import load_config; "
        "from codecompass.offline.git_source import GitSource; "
        "GitSource.read_blob = lambda *a, **k: (_ for _ in ()).throw("
        "AssertionError('source read!')); "
        f"r = ensure_current({str(fx.path)!r}, config=load_config(None), "
        f"index_dir={str(base)!r}, "
        "embedder_factory=lambda: (_ for _ in ()).throw(AssertionError('factory!'))); "
        "assert r.ok and r.status == 'current', r; "
        "heavy = [m for m in sys.modules if m.split('.')[0] in "
        "('chromadb', 'tantivy', 'tree_sitter', 'tree_sitter_language_pack') "
        "or m.startswith('codecompass.offline.stores')]; "
        "assert not heavy, heavy; "
        "print('FAST_OK')"
    )
    env = {**os.environ, "PYTHONPATH": str(__import__('pathlib').Path(
        __file__).resolve().parents[2])}
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, env=env)
    assert "FAST_OK" in proc.stdout, proc.stderr
    after = {p.name: p.stat().st_mtime_ns for p in idx.iterdir()}
    assert before == after
