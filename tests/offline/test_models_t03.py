"""T0.3 core models tests (tests-first, must fail before implementation)."""

import pytest

from codecompass.offline.models import (
    ChangeSet,
    Chunk,
    ChunkMode,
    EmbedderIdentity,
    IndexMeta,
    RunReport,
)


def _chunk(**kw):
    base = dict(
        id="abc123",
        text="def f():\n    pass\n",
        path="src/a.py",
        start_line=1,
        end_line=2,
        language="python",
        symbol="f",
        commit_sha="a1b2c3d",
    )
    base.update(kw)
    return Chunk(**base)


def test_chunk_valid_and_symbol_optional():
    c = _chunk()
    assert c.symbol == "f"
    assert _chunk(symbol=None).symbol is None


def test_chunk_rejects_bad_fields():
    with pytest.raises(ValueError):
        _chunk(start_line=5, end_line=2)  # start > end
    with pytest.raises(ValueError):
        _chunk(path="")  # empty path
    with pytest.raises(ValueError):
        _chunk(path="src\\a.py")  # backslash paths rejected
    with pytest.raises(ValueError):
        _chunk(path="/abs/a.py")  # must be repo-relative
    with pytest.raises(ValueError):
        _chunk(id="")  # id required


def test_chunk_mode_values():
    assert {m.value for m in ChunkMode} == {"structured", "fallback"}


def test_changeset_holds_added_modified_deleted():
    cs = ChangeSet(added=["n.py"], modified=["m.py"], deleted=["d.py"])
    assert cs.added == ["n.py"] and cs.modified == ["m.py"] and cs.deleted == ["d.py"]
    assert ChangeSet().added == []


def test_index_meta_round_trip_fields():
    meta = IndexMeta(
        schema_version=1,
        embedder=EmbedderIdentity(model="m", revision="r", dimension=8),
        indexed_commit="a1b2c3d",
        last_run_at="2024-01-01T00:00:00Z",
    )
    assert meta.indexed_commit == "a1b2c3d"
    assert meta.in_progress is None


def test_run_report_fields():
    rep = RunReport(mode="full", to_commit="a1b2c3d", chunks_added=3, chunks_removed=1)
    assert rep.mode == "full" and rep.chunks_added == 3
