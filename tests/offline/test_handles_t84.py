"""T8.4 read-only handles and export surface tests (tests-first)."""

import pytest

import codecompass.offline as offline
from codecompass.offline import ensure_current
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.offline.meta import EmbedderMismatchError, SchemaMismatchError
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def _stub_config():
    cfg = load_config(None)
    import dataclasses
    return dataclasses.replace(
        cfg, embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))


def test_export_surface():
    assert set(offline.__all__) == {
        "ensure_current", "status", "open_index", "check_consistency"}
    for name in ("IndexStatus", "EnsureResult", "IndexHandles"):
        assert hasattr(offline, name), name


def test_handles_are_read_only_and_consistent(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = _stub_config()
    ensure_current(fx.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=StubEmbedder())
    handles = offline.open_index(fx.path, config=cfg, index_dir=tmp_path / "idx")
    try:
        for handle in (handles.vector, handles.keyword):
            for write_method in ("add", "delete_paths", "commit", "update"):
                assert not hasattr(handle, write_method), write_method
        assert handles.vector.ids() == handles.keyword.ids()
        assert handles.keyword.search("hello", 5) != []
        assert offline.check_consistency(handles.vector, handles.keyword).ok
    finally:
        handles.close()


def test_open_refuses_mismatched_embedder_and_schema(tmp_path):
    import dataclasses
    import json
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = _stub_config()
    ensure_current(fx.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=StubEmbedder())
    other = dataclasses.replace(
        cfg, embedder=dataclasses.replace(cfg.embedder, model="other/model"))
    with pytest.raises(EmbedderMismatchError):
        offline.open_index(fx.path, config=other, index_dir=tmp_path / "idx")
    meta_file = next((tmp_path / "idx").rglob("meta.json"))
    raw = json.loads(meta_file.read_text())
    raw["schema_version"] = 999
    meta_file.write_text(json.dumps(raw))
    with pytest.raises(SchemaMismatchError):
        offline.open_index(fx.path, config=cfg, index_dir=tmp_path / "idx")
