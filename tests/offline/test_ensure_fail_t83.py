"""T8.3 ensure_current failure and concurrency tests (tests-first)."""

import dataclasses
import subprocess
import threading

from codecompass.offline import ensure_current
from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.lock import acquire_lock
from codecompass.offline.meta import read_meta
from codecompass.offline.stores.keyword import KeywordIndex
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def _advance(fx):
    (fx.path / "src" / "main.py").write_text("def hello():\n    return 'v2'\n")
    subprocess.run(["git", "add", "-A"], cwd=fx.path, check=True)
    subprocess.run(["git", "commit", "-qm", "code"], cwd=fx.path, check=True)


def test_embedding_failure_returns_failed_and_index_usable(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    ensure_current(fx.path, config=cfg, index_dir=base, embedder=StubEmbedder())
    idx = orchestrator.index_path_for(fx.path, base)
    kw = KeywordIndex(idx / "keyword")
    before = kw.ids()
    kw.close()
    indexed_before = read_meta(idx).indexed_commit
    _advance(fx)

    class Boom(StubEmbedder):
        def embed(self, texts):
            raise RuntimeError("embedding down")

    r = ensure_current(fx.path, config=cfg, index_dir=base, embedder=Boom())
    assert not r.ok and r.status == "failed" and r.message != ""
    assert read_meta(idx).indexed_commit == indexed_before
    kw = KeywordIndex(idx / "keyword")
    try:
        assert kw.ids() == before  # existing index unchanged and usable
        assert kw.search("hello", 5) != []
    finally:
        kw.close()


def test_concurrent_callers_serialize(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    results = []

    def call():
        results.append(ensure_current(
            fx.path, config=cfg, index_dir=base, embedder=StubEmbedder()))

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert all(r.ok for r in results)
    assert sorted(r.report.mode for r in results) == ["full", "up-to-date"]


def test_lock_timeout_returns_locked(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = load_config(None)
    base = tmp_path / "idx"
    idx = orchestrator.index_path_for(fx.path, base)
    idx.mkdir(parents=True, exist_ok=True)
    cfg = dataclasses.replace(
        cfg, lock=dataclasses.replace(cfg.lock, timeout_seconds=1))
    with acquire_lock(idx / "index.lock", timeout_seconds=10):
        out = []
        t = threading.Thread(
            target=lambda: out.append(ensure_current(
                fx.path, config=cfg, index_dir=base, embedder=StubEmbedder())))
        t.start()
        t.join(timeout=30)
        assert not t.is_alive(), "ensure_current must never block forever"
    assert len(out) == 1 and not out[0].ok and out[0].status == "locked"
