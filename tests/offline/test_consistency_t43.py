"""T4.3 consistency-check tests (tests-first)."""

from codecompass.offline.models import Chunk
from codecompass.offline.stores.consistency import check_consistency
from tests.support.fakes import FakeKeywordIndex, FakeVectorStore
from tests.support.stub_embedder import StubEmbedder


def _chunk(cid="c1", path="a.py", text="x = 1\n"):
    return Chunk(id=cid, text=text, path=path, start_line=1,
                 end_line=1, language="python", symbol=None, commit_sha="abc")


def _pair():
    v, k = FakeVectorStore(), FakeKeywordIndex()
    ch = [_chunk(), _chunk("c2", "b.py", "y = 2\n")]
    v.add(ch, StubEmbedder().embed([c.text for c in ch]))
    k.add(ch)
    return v, k


def test_equal_sets_pass():
    v, k = _pair()
    result = check_consistency(v, k)
    assert result.ok and result.only_in_vector == {} and result.only_in_keyword == {}


def test_missing_id_reported_with_side_and_path():
    v, k = _pair()
    k.delete_paths(["b.py"])
    result = check_consistency(v, k)
    assert not result.ok
    assert result.only_in_vector == {"c2": "b.py"}
    assert result.only_in_keyword == {}
    v2, k2 = _pair()
    v2.delete_paths(["a.py"])
    result2 = check_consistency(v2, k2)
    assert result2.only_in_keyword == {"c1": "a.py"}


def test_per_path_disagreement_reported():
    v, k = _pair()
    k.add([_chunk("cX", "b.py", "zzz\n")])
    result = check_consistency(v, k)
    assert not result.ok
    assert "b.py" in result.path_disagreements
