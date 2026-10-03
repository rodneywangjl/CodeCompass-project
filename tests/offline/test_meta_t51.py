"""T5.1 index metadata tests (tests-first)."""

import json

import pytest

from codecompass.offline.meta import (
    SchemaMismatchError,
    default_meta,
    read_meta,
    write_meta,
)
from codecompass.offline.models import EmbedderIdentity


def _identity():
    return EmbedderIdentity(model="m", revision="r", dimension=8)


def test_round_trip_all_fields(tmp_path):
    meta = default_meta(_identity(), fingerprint="fp1")
    meta = meta.__class__(**{**meta.__dict__, "indexed_commit": "abc",
                             "last_run_at": "2024-01-01T00:00:00Z",
                             "in_progress": {"target_commit": "def",
                                             "touched_paths": ["a.py"]}})
    write_meta(tmp_path, meta)
    back = read_meta(tmp_path)
    assert back == meta


def test_atomic_write_survives_mid_write_crash(tmp_path, monkeypatch):
    write_meta(tmp_path, default_meta(_identity()))
    import codecompass.offline.meta as meta_mod
    monkeypatch.setattr(meta_mod.os, "replace",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        write_meta(tmp_path, default_meta(_identity(), fingerprint="new"))
    assert read_meta(tmp_path).config_fingerprint == ""


def test_unknown_schema_names_expected_and_found(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({
        "schema_version": 999, "embedder": {"model": "m", "revision": "r", "dimension": 8},
        "indexed_commit": None, "last_run_at": None,
        "config_fingerprint": "", "in_progress": None,
    }))
    with pytest.raises(SchemaMismatchError) as e:
        read_meta(tmp_path)
    assert "999" in str(e.value) and "expected 1" in str(e.value)
