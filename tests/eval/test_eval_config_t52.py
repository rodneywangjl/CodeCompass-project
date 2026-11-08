"""T5.2 evaluation config tests (tests-first).

Contract under test (Spec AC-5.4, AC-5.4a; Plan 003 §3.2):
  - eval/codecompass.eval.toml is a full copy of codecompass.toml with exactly these
    differences: [embedder] device = "cuda"; [reranker] device = "cuda",
    dtype = "float16"; [retrieval] docs_fallback = false (stated explicitly);
    [generator] timeout_seconds = 300
  - so it has the full [generator] section and the dev profile, not only GPU settings
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

from codecompass.online.config import get_generator_profile, load_online_config

ROOT = Path(__file__).resolve().parents[2]
EVAL_CONFIG = ROOT / "eval" / "codecompass.eval.toml"
BASE_CONFIG = ROOT / "codecompass.toml"

EXPECTED_DIFFERENCES = {
    ("embedder", "device"): "cuda",
    ("reranker", "device"): "cuda",
    ("reranker", "dtype"): "float16",
    ("retrieval", "docs_fallback"): False,
    ("generator", "timeout_seconds"): 300,
}


def _raw(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


@pytest.fixture
def raw_eval() -> dict:
    return _raw(EVAL_CONFIG)


def test_eval_config_is_committed_where_the_plan_says():
    assert EVAL_CONFIG.is_file()


def test_eval_config_loads_with_the_project_loader():
    # load_online_config() falls back to the defaults for a missing path, so check the
    # file first: otherwise this test would pass with no file at all.
    assert EVAL_CONFIG.is_file()
    load_online_config(EVAL_CONFIG)  # raises on any invalid value


def test_gpu_settings(raw_eval):
    assert raw_eval["embedder"]["device"] == "cuda"
    assert raw_eval["reranker"]["device"] == "cuda"
    assert raw_eval["reranker"]["dtype"] == "float16"


def test_docs_fallback_is_stated_off(raw_eval):
    """Stated explicitly, not left to the default, so the results file shows it."""
    assert raw_eval["retrieval"]["docs_fallback"] is False


def test_timeout_is_300(raw_eval):
    assert raw_eval["generator"]["timeout_seconds"] == 300


def test_loaded_values_match_the_raw_file():
    cfg = load_online_config(EVAL_CONFIG)
    assert cfg.offline.embedder.device == "cuda"
    assert (cfg.reranker.device, cfg.reranker.dtype) == ("cuda", "float16")
    assert cfg.retrieval.docs_fallback is False
    assert cfg.generator.timeout_seconds == 300


def test_every_other_value_equals_codecompass_toml(raw_eval):
    """Exactly the planned differences: nothing else may drift from the project config."""
    expected = copy.deepcopy(_raw(BASE_CONFIG))
    for (section, key), value in EXPECTED_DIFFERENCES.items():
        expected.setdefault(section, {})[key] = value
    assert raw_eval == expected


def test_full_generator_section_and_dev_profile_are_present(raw_eval):
    """A file with only the GPU settings would silently fall back to defaults."""
    assert "dev" in raw_eval["generator"]["profiles"]
    assert raw_eval["generator"]["profiles"]["dev"] == _raw(BASE_CONFIG)["generator"]["profiles"]["dev"]


def test_dev_profile_resolves_to_the_pinned_14b_model():
    cfg = load_online_config(EVAL_CONFIG)
    base = get_generator_profile(load_online_config(BASE_CONFIG), "dev")
    dev = get_generator_profile(cfg, "dev")
    assert dev == base
    assert "14B" in dev.model_id
    assert dev.context_window == 32768
    assert dev.gguf_checksum and dev.gguf_checksum == base.gguf_checksum
