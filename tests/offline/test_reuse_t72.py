"""T7.2 vector reuse tests (tests-first)."""

import subprocess

import pytest

from codecompass.offline import orchestrator
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


FUNCS = "".join(f"def f{i}():\n    return {i}\n\n\n" for i in range(5))


def test_only_changed_chunk_reembedded(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _init(repo)
    (repo / "big.py").write_text(FUNCS)
    _commit(repo)
    cfg = load_config(None)
    orchestrator.run(repo, config=cfg, index_dir=base, embedder=StubEmbedder())
    (repo / "big.py").write_text(FUNCS.replace("return 2", "return 22"))
    _commit(repo)
    embedded = []
    real = StubEmbedder.embed

    def spy(self, texts):
        embedded.extend(texts)
        return real(self, texts)

    StubEmbedder.embed = spy
    try:
        orchestrator.run(repo, config=cfg, index_dir=base, embedder=StubEmbedder())
    finally:
        StubEmbedder.embed = real
    assert len(embedded) == 1 and "return 22" in embedded[0]


def test_incremental_equals_fresh_build(tmp_path):
    repo = tmp_path / "r"
    _init(repo)
    (repo / "big.py").write_text(FUNCS)
    _commit(repo)
    cfg = load_config(None)
    orchestrator.run(repo, config=cfg, index_dir=tmp_path / "inc",
                     embedder=StubEmbedder())
    (repo / "big.py").write_text(FUNCS.replace("return 2", "return 22"))
    _commit(repo)
    orchestrator.run(repo, config=cfg, index_dir=tmp_path / "inc",
                     embedder=StubEmbedder())
    orchestrator.run(repo, config=cfg, index_dir=tmp_path / "fresh",
                     embedder=StubEmbedder())
    iv = VectorStore(orchestrator.index_path_for(repo, tmp_path / "inc") / "vector")
    fv = VectorStore(orchestrator.index_path_for(repo, tmp_path / "fresh") / "vector")
    assert iv.ids() == fv.ids()
    assert iv.paths_for_ids(iv.ids()) == fv.paths_for_ids(fv.ids())
    ih = iv.vectors_for_paths(["big.py"])
    fh = fv.vectors_for_paths(["big.py"])
    assert set(ih) == set(fh)
    for h in ih:
        assert list(ih[h]) == pytest.approx(fh[h], abs=1e-6)
    ik = KeywordIndex(orchestrator.index_path_for(repo, tmp_path / "inc") / "keyword")
    fk = KeywordIndex(orchestrator.index_path_for(repo, tmp_path / "fresh") / "keyword")
    try:
        assert ik.ids() == fk.ids()
    finally:
        ik.close()
        fk.close()
