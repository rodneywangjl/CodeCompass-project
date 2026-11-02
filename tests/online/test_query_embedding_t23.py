"""T2.3 query embedding tests (tests-first).

Contract under test (Spec AC-2.2, FR-1; Plan §3, D1):
  - retrieval.embedder.embed_question(handles, question) -> list[float], via
    handles.embed_query: the index's own, identity-checked embedder
  - the online package never imports offline internals such as
    codecompass.offline.embedding (Article II.2); only the public package and
    the shared config module (Article XI.2)
  The same-instance (O2) and mismatch-propagation checks need ask(); they are
  in test_ask_t121.py.
"""

import ast
import dataclasses
from pathlib import Path

import pytest

import codecompass.offline as offline
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online.retrieval import embedder
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder

ONLINE = Path(__file__).resolve().parents[2] / "codecompass" / "online"


@pytest.fixture
def handles(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg = dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    offline.ensure_current(repo.path, config=cfg, index_dir=tmp_path / "idx",
                           embedder=StubEmbedder())
    h = offline.open_index(repo.path, config=cfg, index_dir=tmp_path / "idx",
                           embedder=StubEmbedder())
    yield h
    h.close()


def test_question_is_embedded_with_the_index_embedder(handles):
    question = "Why does authenticate retry?"
    vector = embedder.embed_question(handles, question)
    assert vector == StubEmbedder().embed([question])[0]
    assert len(vector) == handles.meta.embedder.dimension


def test_online_imports_only_the_public_offline_api():
    allowed = {"codecompass.offline", "codecompass.offline.config"}
    for path in ONLINE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            for name in names:
                if name.startswith("codecompass.offline"):
                    assert name in allowed, f"{path.name} imports {name}"
