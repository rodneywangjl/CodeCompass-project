"""T7.7 metadata-only advance tests (tests-first)."""

import subprocess

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSource
from codecompass.offline.meta import read_meta
from tests.support.stub_embedder import StubEmbedder


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_doc_only_commit_advances_without_store_writes(tmp_path, monkeypatch):
    repo, base = tmp_path / "r", tmp_path / "idx"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    (repo / "README.md").write_text("# docs\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")
    cfg = load_config(None)
    orchestrator.run(repo, config=cfg, index_dir=base, embedder=StubEmbedder())
    (repo / "README.md").write_text("# docs v2\n")
    (repo / ".env").write_text("SECRET=x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs only")

    calls = []
    from codecompass.offline.stores import vector as vec_mod
    from codecompass.offline.stores import keyword as kw_mod

    for cls, names in ((vec_mod.VectorStore, ("add", "delete_paths")),
                       (kw_mod.KeywordIndex, ("add", "delete_paths", "commit"))):
        # NOTE (AC-2.6 vs O8): restamp_commit_sha is deliberately NOT spied
        # here. AC-2.6/T7.3 require every advancing run to equal a fresh build,
        # so chunk commit stamps are confirmed as metadata-only writes with no
        # re-embedding. This test verifies no CONTENT writes happen: no chunk
        # add/delete and no keyword churn.
        for name in names:
            real = getattr(cls, name)

            def spy(self, *a, _real=real, _name=name, **k):
                calls.append(_name)
                return _real(self, *a, **k)

            monkeypatch.setattr(cls, name, spy)

    report = orchestrator.run(repo, config=cfg, index_dir=base,
                              embedder=StubEmbedder())
    assert calls == [], calls
    assert read_meta(orchestrator.index_path_for(repo, base)).indexed_commit == \
        GitSource(repo).head_sha()
    assert report.to_commit == GitSource(repo).head_sha()
