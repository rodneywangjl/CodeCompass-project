"""T4.2 vector store tests (tests-first)."""

import pytest

from codecompass.offline.models import Chunk
from codecompass.offline.stores.vector import VectorStore
from tests.support.stub_embedder import StubEmbedder


def _chunk(cid="c1", path="a.py", text="def f():\n    pass\n"):
    return Chunk(id=cid, text=text, path=path, start_line=1,
                 end_line=2, language="python", symbol="f", commit_sha="abc")


def _vecs(texts):
    return StubEmbedder().embed(texts)


def test_add_ids_count_and_cosine_space(tmp_path):
    v = VectorStore(tmp_path / "vec")
    ch = [_chunk(), _chunk("c2", "b.py", "x = 1\n")]
    v.add(ch, _vecs([c.text for c in ch]))
    assert v.ids() == {"c1", "c2"} and v.count() == 2
    assert v.space() == "cosine"


def test_delete_paths_and_vector_reuse_lookup(tmp_path):
    v = VectorStore(tmp_path / "vec")
    ch = [_chunk(), _chunk("c2", "b.py", "x = 1\n")]
    vecs = _vecs([c.text for c in ch])
    v.add(ch, vecs)
    reuse = v.vectors_for_paths(["a.py"])
    assert len(reuse) == 1
    assert list(reuse.values())[0] == pytest.approx(vecs[0], abs=1e-6)  # chroma stores float32
    v.delete_paths(["a.py"])
    assert v.ids() == {"c2"}


def test_persist_and_wrong_dimension(tmp_path):
    v = VectorStore(tmp_path / "vec")
    ch = [_chunk()]
    v.add(ch, _vecs([ch[0].text]))
    del v
    assert VectorStore(tmp_path / "vec").ids() == {"c1"}
    with pytest.raises(Exception):
        VectorStore(tmp_path / "vec2", dimension=8).add(ch, [[0.1, 0.2]])
