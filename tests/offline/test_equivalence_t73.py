"""T7.3 incremental-equals-from-scratch property test (tests-first)."""

import random
import subprocess

import pytest

from codecompass.offline import orchestrator
from codecompass.offline.config import load_config
from codecompass.offline.stores.keyword import KeywordIndex
from codecompass.offline.stores.vector import VectorStore
from tests.support.stub_embedder import StubEmbedder


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True)


def _commit(repo):
    _git(repo, "add", "-A")
    subprocess.run(["git", "commit", "-qm", "x", "--allow-empty"],
                   cwd=repo, check=True, capture_output=True)


def _run(repo, base):
    return orchestrator.run(repo, config=load_config(None),
                            index_dir=base, embedder=StubEmbedder())


def _snapshot(repo, base):
    idx = orchestrator.index_path_for(repo, base)
    vec = VectorStore(idx / "vector")
    kw = KeywordIndex(idx / "keyword")
    try:
        return vec.records_for_ids(vec.ids()), kw.ids(), \
            kw.paths_for_ids(kw.ids())
    finally:
        kw.close()


def _same_records(a, b):
    assert set(a) == set(b)
    for cid in a:
        assert a[cid]["text"] == b[cid]["text"]
        assert a[cid]["metadata"] == b[cid]["metadata"]
        assert list(a[cid]["vector"]) == pytest.approx(b[cid]["vector"], abs=1e-6)


def test_incremental_matches_fresh_after_random_sequence(tmp_path):
    rng = random.Random(7)
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    names = [f"mod{i}.py" for i in range(4)]
    (repo / "pkg").mkdir()
    for i, n in enumerate(names):
        (repo / n).write_text(f"def f{i}():\n    return {i}\n")
    (repo / "pkg" / "a.py").write_text("def pa():\n    return 0\n")
    _commit(repo)
    inc, fresh_root = tmp_path / "inc", tmp_path / "fresh"
    _run(repo, inc)

    for step in range(6):
        op = rng.choice(["add", "modify", "delete", "rename",
                         "rename_modify", "revert", "mode", "dirmove"])
        live = sorted(p.name for p in repo.glob("*.py"))
        if op == "add":
            n = f"new{step}.py"
            (repo / n).write_text(f"def g{step}():\n    return {step}\n")
        elif op == "modify" and live:
            n = rng.choice(live)
            (repo / n).write_text((repo / n).read_text() + f"\n# s{step}\n")
        elif op == "delete" and live:
            n = rng.choice(live)
            (repo / n).unlink()
        elif op == "rename" and live:
            n = rng.choice(live)
            _git(repo, "mv", n, f"r{step}_{n}")
        elif op == "rename_modify" and live:
            n = rng.choice(live)
            _git(repo, "mv", n, f"m{step}_{n}")
            p = repo / f"m{step}_{n}"
            p.write_text(p.read_text().replace("return", "return 1 +"))
        elif op == "revert" and step > 0:
            _git(repo, "checkout", "HEAD~1", "--", ".")
        elif op == "mode" and live:
            (repo / rng.choice(live)).chmod(0o755)
        elif op == "dirmove":
            if (repo / "pkg").exists():
                _git(repo, "mv", "pkg", f"pkg{step}")
        _commit(repo)
        _run(repo, inc)
        fresh = fresh_root / f"s{step}"
        _run(repo, fresh)
        rec_inc, kw_inc, paths_inc = _snapshot(repo, inc)
        rec_fresh, kw_fresh, paths_fresh = _snapshot(repo, fresh)
        _same_records(rec_inc, rec_fresh)
        assert kw_inc == kw_fresh == set(rec_fresh)
        assert paths_inc == paths_fresh
