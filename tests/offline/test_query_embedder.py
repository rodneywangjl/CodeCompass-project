"""Query embedder bound to the read-only handles (tests-first).

Fix outside a numbered task: the online pipeline must embed questions with the
index's own embedder (Article II.4) without importing offline internals
(Article II.2). `open_index` attaches the embedder and checks the *instance*
against index metadata, not just the config.
"""

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

from codecompass.offline import ensure_current, open_index
from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.offline.meta import EmbedderMismatchError
from codecompass.offline.models import EmbedderIdentity
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder


def _stub_config():
    return dataclasses.replace(
        load_config(None),
        embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))


def _indexed(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    cfg = _stub_config()
    ensure_current(fx.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=StubEmbedder())
    return fx, cfg


class _OtherEmbedder(StubEmbedder):
    """Same vectors and dimension as the stub, different model identity."""

    def __init__(self) -> None:
        super().__init__()
        self.identity = EmbedderIdentity(model="other/model", revision="r1",
                                         dimension=8)


def test_embed_query_uses_the_given_embedder(tmp_path):
    fx, cfg = _indexed(tmp_path)
    handles = open_index(fx.path, config=cfg, index_dir=tmp_path / "idx",
                         embedder=StubEmbedder())
    try:
        assert handles.embed_query("hello") == StubEmbedder().embed(["hello"])[0]
    finally:
        handles.close()


def test_refuses_mismatched_embedder_instance_even_if_config_matches(tmp_path):
    fx, cfg = _indexed(tmp_path)  # cfg identity matches the index
    with pytest.raises(EmbedderMismatchError):
        open_index(fx.path, config=cfg, index_dir=tmp_path / "idx",
                   embedder=_OtherEmbedder())


def test_refuses_config_mismatch_even_if_embedder_instance_matches(tmp_path):
    # Strict rule: config and instance must both match the index, so the
    # config can never name one model while another is used.
    fx, _ = _indexed(tmp_path)  # default config names jina, index is stub
    with pytest.raises(EmbedderMismatchError):
        open_index(fx.path, config=load_config(None),
                   index_dir=tmp_path / "idx", embedder=StubEmbedder())


def test_default_embedder_comes_from_config_and_loads_lazily(tmp_path):
    fx, _ = _indexed(tmp_path)
    script = (
        "import dataclasses, sys; "
        "from codecompass.offline import open_index; "
        "from codecompass.offline.config import EmbedderConfig, load_config; "
        "cfg = dataclasses.replace(load_config(None), embedder=EmbedderConfig("
        "model='stub', revision='stub-1', dimension=8)); "
        f"h = open_index({str(fx.path)!r}, config=cfg, "
        f"index_dir={str(tmp_path / 'idx')!r}); "
        "assert h.embedder.identity.model == 'stub', h.embedder.identity; "
        "assert 'sentence_transformers' not in sys.modules; "
        "h.close(); print('LAZY_OK')"
    )
    env = {**os.environ,
           "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, env=env)
    assert "LAZY_OK" in proc.stdout, proc.stderr
