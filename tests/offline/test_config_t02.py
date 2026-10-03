"""T0.2 config loader tests (tests-first, must fail before implementation).

Contract under test (from plan §7, FR-17):
  load_config(path | None) -> Config  (typed, validated, defaults applied)
"""

import pathlib

import pytest

from codecompass.offline.config import load_config

EMBEDDER_ID = "jinaai/jina-embeddings-v2-base-code"


def test_defaults_when_keys_missing(tmp_path):
    cfg = load_config(None)
    assert cfg.chunking.target_tokens == 512
    assert cfg.chunking.target_tokens <= cfg.chunking.hard_max_tokens
    assert cfg.lock.timeout_seconds == 120
    assert cfg.embedder.model == EMBEDDER_ID
    assert "python" in cfg.languages.treesitter
    assert cfg.index.dir is not None


def test_overrides_honoured(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text(
        "[chunking]\ntarget_tokens = 256\n"
        "[lock]\ntimeout_seconds = 10\n"
        '[embedder]\nmodel = "other/model"\n'
    )
    cfg = load_config(f)
    assert cfg.chunking.target_tokens == 256
    assert cfg.lock.timeout_seconds == 10
    assert cfg.embedder.model == "other/model"


def test_unknown_key_rejected(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text("[nope]\nfoo = 1\n")
    with pytest.raises(ValueError):
        load_config(f)
    f.write_text("[lock]\nnot_a_key = 1\n")
    with pytest.raises(ValueError):
        load_config(f)


def test_target_over_hard_max_rejected(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text("[chunking]\ntarget_tokens = 99999\nhard_max_tokens = 100\n")
    with pytest.raises(ValueError):
        load_config(f)


def test_relative_paths_resolved(tmp_path):
    f = tmp_path / "sub" / "codecompass.toml"
    f.parent.mkdir()
    f.write_text('[index]\ndir = "idx"\n')
    cfg = load_config(f)
    assert pathlib.Path(cfg.index.dir).is_absolute()


def test_nothing_hardcoded():
    # Model names appear only in config defaults, never scattered in code.
    hits = []
    for p in pathlib.Path("codecompass").rglob("*.py"):
        if p.name == "config.py":
            continue
        if "jina" in p.read_text().lower():
            hits.append(str(p))
    assert hits == [], f"model name hard-coded outside config defaults: {hits}"
