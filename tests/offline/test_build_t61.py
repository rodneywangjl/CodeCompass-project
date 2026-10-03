"""T6.1 orchestrator full-build tests (tests-first; stub embedder, real stores)."""

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.git_source import GitSource
from codecompass.offline.meta import read_meta
from codecompass.offline.models import RunReport
from codecompass.offline.stores.keyword import KeywordIndex
from codecompass.offline.stores.vector import VectorStore
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def _run(repo, index_base):
    cfg = load_config(None)
    return orchestrator.run(repo, config=cfg, index_dir=index_base,
                            embedder=StubEmbedder())


def test_full_build_writes_both_stores(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    report = _run(fx.path, tmp_path / "idx")
    assert isinstance(report, RunReport) and report.mode == "full"
    head = GitSource(fx.path).head_sha()
    assert report.to_commit == head
    idx = orchestrator.index_path_for(fx.path, tmp_path / "idx")
    assert read_meta(idx).indexed_commit == head
    vec = VectorStore(idx / "vector")
    kw = KeywordIndex(idx / "keyword")
    try:
        assert len(vec.ids()) > 0 and vec.ids() == kw.ids()
        assert kw.search("hello", 5) != []  # src/main.py indexed
    finally:
        kw.close()


def test_excluded_and_non_code_absent(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    _run(fx.path, tmp_path / "idx")
    idx = orchestrator.index_path_for(fx.path, tmp_path / "idx")
    kw = KeywordIndex(idx / "keyword")
    try:
        assert kw.search("topsecret", 5) == []  # .env never indexed
        assert kw.search("Fixture", 5) == []  # README is non-code
    finally:
        kw.close()
