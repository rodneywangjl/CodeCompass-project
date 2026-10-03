"""T4.1 keyword index tests (tests-first; identifier lookup first, risk R1)."""

from codecompass.offline.models import Chunk
from codecompass.offline.stores.keyword import KeywordIndex


def _chunk(cid="c1", path="a.py", text="x = 1\n"):
    return Chunk(id=cid, text=text, path=path, start_line=1,
                 end_line=1, language="python", symbol=None, commit_sha="abc")


def test_identifier_lookup(tmp_path):
    k = KeywordIndex(tmp_path / "kw")
    k.add([
        _chunk("c1", "a.py", "def get_user_by_id():\n    pass\n"),
        _chunk("c2", "b.py", "def getUserById():\n    return a.b.c\n"),
        _chunk("c3", "c.py", "raise E1234\n"),
    ])
    k.commit()
    assert "c1" in k.search("get_user_by_id", 5)
    assert "c2" in k.search("getUserById", 5)
    assert "c2" in k.search("a.b.c", 5)
    assert "c3" in k.search("E1234", 5)


def test_delete_ids_empty_and_persist(tmp_path):
    k = KeywordIndex(tmp_path / "kw")
    assert k.search("anything", 5) == [] and k.ids() == set()
    k.add([_chunk("c1", "a.py", "hello world\n"), _chunk("c2", "b.py", "other\n")])
    k.commit()
    assert k.ids() == {"c1", "c2"}
    k.delete_paths(["a.py"])
    k.commit()
    assert k.ids() == {"c2"}
    assert k.search("hello", 5) == []
    k.close()
    k2 = KeywordIndex(tmp_path / "kw")
    assert k2.ids() == {"c2"}
    k2.close()
