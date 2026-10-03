"""T7.6 config fingerprint and newly excluded paths tests (tests-first)."""

import dataclasses
import subprocess

from codecompass.offline import orchestrator
from codecompass.offline.config import FilesConfig, load_config
from codecompass.offline.meta import read_meta
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
    (repo / "b.py").write_text(
        "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(60)))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")


def _run(repo, base, cfg):
    return orchestrator.run(repo, config=cfg, index_dir=base, embedder=StubEmbedder())


def _ids(repo, base):
    idx = orchestrator.index_path_for(repo, base)
    vec = VectorStore(idx / "vector")
    kw = KeywordIndex(idx / "keyword")
    try:
        return vec.ids(), kw.ids(), vec.paths_for_ids(vec.ids())
    finally:
        kw.close()


def test_new_exclusion_removes_existing_chunks(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    cfg = load_config(None)
    _run(repo, base, cfg)
    assert "b.py" in _ids(repo, base)[2].values()
    cfg2 = dataclasses.replace(cfg, files=dataclasses.replace(
        cfg.files, exclude_patterns=tuple(cfg.files.exclude_patterns) + ("b.py",)))
    report = _run(repo, base, cfg2)
    vec_ids, kw_ids, paths = _ids(repo, base)
    assert vec_ids == kw_ids
    assert "b.py" not in paths.values()
    assert "a.py" in paths.values()
    assert read_meta(orchestrator.index_path_for(repo, base)).config_fingerprint == \
        orchestrator.config_fingerprint(cfg2)


def test_target_change_rechunks_with_reuse_and_stable_config_is_quiet(tmp_path):
    repo, base = tmp_path / "r", tmp_path / "idx"
    _setup(repo)
    cfg = load_config(None)
    _run(repo, base, cfg)
    # Unchanged config: quiet up-to-date run.
    assert _run(repo, base, cfg).mode == "up-to-date"
    cfg2 = dataclasses.replace(cfg, chunking=dataclasses.replace(
        cfg.chunking, target_tokens=64))
    embedded = []
    real = StubEmbedder.embed

    def spy(self, texts):
        embedded.extend(texts)
        return real(self, texts)

    StubEmbedder.embed = spy
    try:
        report = orchestrator.run(repo, config=cfg2, index_dir=base,
                                  embedder=StubEmbedder())
    finally:
        StubEmbedder.embed = real
    assert report.mode == "rebuild"
    vec_ids, kw_ids, _ = _ids(repo, base)
    assert vec_ids == kw_ids and vec_ids
    assert 'def alpha():\n    return 1' not in embedded  # tiny chunk reused
    assert embedded  # big file rechunked and embedded
