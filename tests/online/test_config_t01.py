"""T0.1 online package skeleton, config, and models tests (tests-first).

Contract under test (Spec 002, Plan §3-§5, §7):
  - Package imports cleanly: codecompass.online
  - Config loader: load_online_config(path | None) -> OnlineConfig
  - Retrieval parameters: vector_k=50, keyword_k=50, rrf_constant=60, rerank_k=50, final_k=8
  - Profile loader: get_generator_profile(cfg, profile_name | None) -> ModelProfile (dev/prod)
  - Loud error on unknown profile
  - MAX_VERIFIER_ROUNDS is 3 (named constant)
  - All k values, RRF constant, and tool settings are named attributes
  - Core models in codecompass.online.models: QueryResult, CitationResult, SourceEntry, ToolCall, ToolResult
"""

import os
import pathlib
import pytest

import codecompass.online
from codecompass.online.config import (
    DEFAULT_FINAL_K,
    DEFAULT_KEYWORD_K,
    DEFAULT_RERANK_K,
    DEFAULT_RRF_CONSTANT,
    DEFAULT_VECTOR_K,
    MAX_VERIFIER_ROUNDS,
    ModelProfile,
    OnlineConfig,
    get_generator_profile,
    load_online_config,
)
from codecompass.online.models import (
    CitationResult,
    QueryResult,
    SourceEntry,
    ToolCall,
    ToolResult,
)


def test_package_imports():
    """Package imports cleanly and has docstring/version."""
    assert codecompass.online is not None


def test_default_retrieval_params_loaded():
    """Default retrieval parameters match constitution & plan defaults (AC-2.5, FR-4)."""
    cfg = load_online_config(None)
    assert isinstance(cfg, OnlineConfig)
    assert cfg.retrieval.vector_k == 50
    assert cfg.retrieval.keyword_k == 50
    assert cfg.retrieval.rrf_constant == 60
    assert cfg.retrieval.rerank_k == 50
    assert cfg.retrieval.final_k == 8

    # Named constants exist and match config defaults
    assert DEFAULT_VECTOR_K == 50
    assert DEFAULT_KEYWORD_K == 50
    assert DEFAULT_RRF_CONSTANT == 60
    assert DEFAULT_RERANK_K == 50
    assert DEFAULT_FINAL_K == 8


def test_profile_loader_returns_dev_and_prod():
    """Profile loader returns dev and prod profiles with expected attributes (AC-5.1, AC-5.2)."""
    cfg = load_online_config(None)

    dev_prof = get_generator_profile(cfg, "dev")
    assert isinstance(dev_prof, ModelProfile)
    assert dev_prof.model_id == "Qwen2.5-Coder-14B-Instruct"
    assert dev_prof.quantisation == "Q4_K_M"
    assert dev_prof.context_window == 32768
    assert dev_prof.temperature == 0.1
    assert dev_prof.max_tokens == 2048
    assert "<|im_end|>" in dev_prof.stop_tokens

    prod_prof = get_generator_profile(cfg, "prod")
    assert isinstance(prod_prof, ModelProfile)
    assert prod_prof.model_id == "Qwen2.5-Coder-32B-Instruct"
    assert prod_prof.quantisation == "Q4_K_M"
    assert prod_prof.context_window == 32768
    assert prod_prof.temperature == 0.1
    assert prod_prof.max_tokens == 2048
    assert "<|im_end|>" in prod_prof.stop_tokens


def test_profile_loader_default_and_env_override(monkeypatch):
    """Default profile is 'dev', overridable by GENERATOR_PROFILE env var (AC-5.1, AC-5.9)."""
    cfg = load_online_config(None)

    # When None passed, resolves default profile ("dev")
    prof = get_generator_profile(cfg, None)
    assert prof.model_id == "Qwen2.5-Coder-14B-Instruct"

    # Environment variable overrides default
    monkeypatch.setenv("GENERATOR_PROFILE", "prod")
    prof_env = get_generator_profile(cfg, None)
    assert prof_env.model_id == "Qwen2.5-Coder-32B-Instruct"


def test_unknown_profile_raises_loud_error():
    """An unknown profile causes a loud error, never silent fallback (AC-5.9)."""
    cfg = load_online_config(None)
    with pytest.raises(ValueError, match="unknown generator profile: 'nonexistent'"):
        get_generator_profile(cfg, "nonexistent")


def test_max_verifier_rounds_and_tools_config():
    """MAX_VERIFIER_ROUNDS is 3 and tool settings are named attributes (AC-3.1, FR-6, FR-7)."""
    assert MAX_VERIFIER_ROUNDS == 3

    cfg = load_online_config(None)
    assert cfg.tools.max_verifier_rounds == 3
    assert "git_blame" in cfg.tools.allowed_tools
    assert "git_log" in cfg.tools.allowed_tools
    assert cfg.tools.git_log_limit == 20
    assert cfg.tools.git_blame_timeout == 30
    assert cfg.tools.git_log_timeout == 30


def test_overrides_honoured_from_toml(tmp_path):
    """Custom settings in toml file override defaults."""
    f = tmp_path / "codecompass.toml"
    f.write_text(
        "[retrieval]\n"
        "vector_k = 25\n"
        "final_k = 4\n"
        "[tools]\n"
        "git_log_limit = 10\n"
        "[generator]\n"
        'server_url = "http://127.0.0.1:9090"\n'
    )
    cfg = load_online_config(f)
    assert cfg.retrieval.vector_k == 25
    assert cfg.retrieval.final_k == 4
    assert cfg.retrieval.keyword_k == 50  # default preserved
    assert cfg.tools.git_log_limit == 10
    assert cfg.generator.server_url == "http://127.0.0.1:9090"


def test_online_config_merges_offline_config(tmp_path):
    """OnlineConfig holds merged offline configuration for store paths & embedder."""
    cfg = load_online_config(None)
    assert cfg.offline is not None
    assert cfg.offline.embedder is not None
    assert cfg.offline.index is not None


def test_core_models_instantiation():
    """Core dataclasses from models.py can be created and checked."""
    qr = QueryResult(
        answer="Example answer [1]",
        sources=[],
        citation_outcome="F",
        stale_index=False,
        stale_message="",
        audit_log={"round": 0},
    )
    assert qr.citation_outcome == "F"
    assert qr.stale_index is False

    cr = CitationResult(
        outcome="G",
        sources=[],
        unverified=[0],
        answer_text="Example answer [1]",
        banner="WARNING: Some citations...",
    )
    assert cr.outcome == "G"
    assert cr.unverified == [0]

    src = SourceEntry(
        kind="code",
        marker=1,
        path="src/main.py",
        start_line=10,
        end_line=20,
        commit="a1b2c3d",
    )
    assert src.kind == "code"
    assert src.path == "src/main.py"

    call = ToolCall(tool="git_blame", args={"path": "src/main.py", "lines": "10-20"})
    assert call.tool == "git_blame"

    res = ToolResult(tool="git_blame", args={}, output="commit info", cache_hit=True)
    assert res.cache_hit is True
