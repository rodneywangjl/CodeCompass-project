"""T7.1 incremental update tests (tests-first)."""

import subprocess

from codecompass.offline import orchestrator
from codecompass.offline.chunking import ids as ids_mod
from codecompass.offline.config import load_config
from codecompass.offline.stores.keyword import KeywordIndex
from codecompass.offline.stores.vector import VectorStore
from tests.support.stub_embedder import StubEmbedder


def _init(repo):
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _commit(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True)


def _run(repo, base, **kw):
    kw.setdefault("embedder", StubEmbedder())
    return orchestrator.run(repo, config=load_config(None), index_dir=base, **kw)


def _stores(repo, base):
    idx = orchestrator.index_path_for(repo, base)
    return VectorStore(idx / "vector"), KeywordIndex(idx / "keyword")


def _repo_v1(repo):
    _init(repo)
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    (repo / "b.py").write_text("def beta():\n    return 2\n")
    (repo / "c.py").write_text("def cee():\n    return 3\n")
    _commit(repo)


def test_modify_delete_add_rename(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _repo_v1(repo)
    r1 = _run(repo, base)
    assert r1.mode == "full"
    (repo / "a.py").write_text("def alpha():\n    return 11\n")  # modify
    (repo / "b.py").unlink()  # delete
    subprocess.run(["git", "rm", "-q", "b.py"], cwd=repo, check=True)
    (repo / "d.py").write_text("def delta():\n    return 4\n")  # add
    subprocess.run(["git", "mv", "c.py", "z.py"], cwd=repo, check=True)  # rename
    _commit(repo)
    r2 = _run(repo, base)
    assert r2.mode == "incremental"
    vec, kw = _stores(repo, base)
    try:
        assert vec.ids() == kw.ids()
        assert kw.search("11", 5) != []  # modified content present
        assert kw.search("beta", 5) == []  # deleted file gone
        assert kw.search("delta", 5) != []  # added file present
        assert kw.search("cee", 5) != []  # renamed content under new path
        paths = set(vec.paths_for_ids(vec.ids()).values())
        assert paths == {"a.py", "d.py", "z.py"}  # no stale paths
    finally:
        kw.close()


def test_unchanged_files_not_reread_or_reembedded(tmp_path, monkeypatch):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _repo_v1(repo)
    _run(repo, base)
    (repo / "a.py").write_text("def alpha():\n    return 11\n")
    _commit(repo)
    reads = []
    from codecompass.offline import git_source
    real_read = git_source.GitSource.read_blob

    def counting_read(self, sha, path):
        reads.append(path)
        return real_read(self, sha, path)

    monkeypatch.setattr(git_source.GitSource, "read_blob", counting_read)
    embeds = []
    from tests.support.stub_embedder import StubEmbedder as SE
    real_embed = SE.embed

    def counting_embed(self, texts):
        embeds.extend(texts)
        return real_embed(self, texts)

    monkeypatch.setattr(SE, "embed", counting_embed)
    _run(repo, base)
    assert reads == ["a.py"], reads  # only the changed file is read
    assert all("return 11" in t or "alpha" in t for t in embeds)


def test_second_run_at_same_commit_does_no_work(tmp_path, monkeypatch):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _repo_v1(repo)
    _run(repo, base)
    idx = orchestrator.index_path_for(repo, base)
    before = (idx / "meta.json").stat().st_mtime_ns
    from codecompass.offline import git_source
    monkeypatch.setattr(git_source.GitSource, "read_blob",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("read!")))
    r = orchestrator.run(repo, config=load_config(None), index_dir=base,
                         embedder_factory=lambda: (_ for _ in ()).throw(
                             AssertionError("factory!")))
    assert r.mode == "up-to-date"
    assert (idx / "meta.json").stat().st_mtime_ns == before
