"""T7.4 journal and crash recovery tests (tests-first)."""

import subprocess

import pytest

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSource
from codecompass.offline.meta import read_meta
from codecompass.offline.stores.consistency import check_consistency
from codecompass.offline.stores.keyword import KeywordIndex
from codecompass.offline.stores.vector import VectorStore
from tests.support.stub_embedder import StubEmbedder


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _setup(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    (repo / "b.py").write_text("def beta():\n    return 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")


def _run(repo, base, **kw):
    kw.setdefault("embedder", StubEmbedder())
    return orchestrator.run(repo, config=load_config(None), index_dir=base, **kw)


def _ids(repo, base):
    idx = orchestrator.index_path_for(repo, base)
    vec = VectorStore(idx / "vector")
    kw = KeywordIndex(idx / "keyword")
    try:
        assert check_consistency(vec, kw).ok
        return vec.ids(), kw.ids()
    finally:
        kw.close()


def _indexed(repo, base):
    return read_meta(orchestrator.index_path_for(repo, base)).indexed_commit


def _fail_then_converge(tmp_path, monkeypatch, point):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    _run(repo, base)
    (repo / "a.py").write_text("def alpha():\n    return 11\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v2")
    head = GitSource(repo).head_sha()
    if point == "embed":
        class Boom(StubEmbedder):
            def embed(self, texts):
                raise RuntimeError("embedding down")
        with pytest.raises(RuntimeError):
            _run(repo, base, embedder=Boom())
    elif point == "vector_add":
        monkeypatch.setattr(VectorStore, "add",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no vec")))
        with pytest.raises(RuntimeError):
            _run(repo, base)
    elif point == "keyword_add":
        from codecompass.offline.stores.keyword import KeywordIndex as KI
        monkeypatch.setattr(KI, "add",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no kw")))
        with pytest.raises(RuntimeError):
            _run(repo, base)
    elif point == "commit":
        from codecompass.offline.stores.keyword import KeywordIndex as KI
        monkeypatch.setattr(KI, "commit",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no commit")))
        with pytest.raises(RuntimeError):
            _run(repo, base)
    assert _indexed(repo, base) != head  # commit not advanced
    monkeypatch.undo()  # clean re-run with no injected failure
    _run(repo, base)  # clean re-run converges
    assert _indexed(repo, base) == head
    _run(repo, tmp_path / "fresh")  # fresh build for comparison
    assert _ids(repo, base)[0] == _ids(repo, tmp_path / "fresh")[0]


@pytest.mark.parametrize("point", ["embed", "vector_add", "keyword_add", "commit"])
def test_crash_at_each_point_recovers(tmp_path, monkeypatch, point):
    _fail_then_converge(tmp_path, monkeypatch, point)


def test_revert_after_half_processed_run(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    _run(repo, base)
    (repo / "a.py").write_text("def alpha():\n    return 11\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v2")

    class BoomOnce(StubEmbedder):
        def embed(self, texts):
            raise RuntimeError("mid-run failure")

    with pytest.raises(RuntimeError):
        _run(repo, base, embedder=BoomOnce())
    _git(repo, "checkout", "HEAD~1", "--", "a.py")
    _git(repo, "commit", "-qm", "v3-revert", "--allow-empty")
    _run(repo, base)
    _run(repo, tmp_path / "fresh")
    assert _ids(repo, base)[0] == _ids(repo, tmp_path / "fresh")[0]
    vec_ids, kw_ids = _ids(repo, base)
    assert vec_ids == kw_ids
