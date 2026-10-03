"""T0.5 stub embedder and in-memory fakes tests (tests-first)."""

from tests.support.fakes import FakeKeywordIndex, FakeVectorStore
from tests.support.fixture_repo import MAIN_V1
from tests.support.stub_embedder import StubEmbedder
from codecompass.offline.models import Chunk


def _chunk(cid="c1", path="a.py", text="def f():\n    pass\n"):
    return Chunk(id=cid, text=text, path=path, start_line=1,
                 end_line=2, language="python", symbol="f", commit_sha="abc")


def test_stub_deterministic_and_sized():
    s = StubEmbedder()
    assert s.embed([MAIN_V1]) == s.embed([MAIN_V1])
    assert s.embed(["aaa"]) != s.embed(["bbb"])
    assert len(s.embed(["x"])[0]) == s.identity.dimension


def test_stub_batch_order():
    s = StubEmbedder()
    texts = ["one", "two", "three"]
    assert s.embed(texts) == [s.embed([t])[0] for t in texts]


def test_fake_vector_store_protocol():
    v = FakeVectorStore()
    ch = [_chunk(), _chunk("c2", "b.py")]
    vecs = StubEmbedder().embed([c.text for c in ch])
    v.add(ch, vecs)
    assert v.ids() == {"c1", "c2"} and v.count() == 2
    assert isinstance(v.vectors_for_paths(["a.py"]), dict)
    v.delete_paths(["a.py"])
    assert v.ids() == {"c2"}


def test_fake_keyword_index_protocol():
    k = FakeKeywordIndex()
    assert k.search("anything", 5) == []
    k.add([_chunk(text="def get_user_by_id():\n    pass\n")])
    assert k.search("get_user_by_id", 5) == ["c1"]
    k.delete_paths(["a.py"])
    assert k.ids() == set()
