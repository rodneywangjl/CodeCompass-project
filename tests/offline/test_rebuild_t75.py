"""T7.5 unreachable indexed commit tests (tests-first)."""

import subprocess

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSource
from codecompass.offline.meta import read_meta, write_meta
from codecompass.offline.stores.keyword import KeywordIndex
from codecompass.offline.stores.vector import VectorStore
from tests.support.stub_embedder import StubEmbedder


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _run(repo, base):
    return orchestrator.run(repo, config=load_config(None),
                            index_dir=base, embedder=StubEmbedder())


def _setup(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def alpha():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")
    (repo / "a.py").write_text("def alpha():\n    return 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v2")


def test_history_rewrite_triggers_rebuild_with_reason(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    _run(repo, base)
    _git(repo, "reset", "--hard", "-q", "HEAD~1")
    (repo / "a.py").write_text("def alpha():\n    return 99\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "rewritten")
    report = _run(repo, base)
    assert report.mode == "rebuild"
    assert report.note != ""
    assert read_meta(orchestrator.index_path_for(repo, base)).indexed_commit == \
        GitSource(repo).head_sha()
    idx = orchestrator.index_path_for(repo, base)
    vec, kw = VectorStore(idx / "vector"), KeywordIndex(idx / "keyword")
    try:
        assert vec.ids() == kw.ids() and kw.search("99", 5) != []
    finally:
        kw.close()


def test_unresolvable_commit_triggers_rebuild(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    _run(repo, base)
    idx = orchestrator.index_path_for(repo, base)
    meta = read_meta(idx)
    write_meta(idx, meta.__class__(**{**meta.__dict__,
                                      "indexed_commit": "0" * 40}))
    report = _run(repo, base)
    assert report.mode == "rebuild" and report.note != ""
