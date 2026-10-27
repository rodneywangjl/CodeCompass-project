"""T7.1 model profile loading tests (tests-first).

Contract under test (Spec AC-5.1, AC-5.2, AC-5.9, AC-5.11, FR-17; Article VIII.4):
  - generator.profiles.resolve_profile(config, name=None) -> (name, ModelProfile)
    name falls back to GENERATOR_PROFILE, then generator.default_profile ("dev")
  - an unknown profile raises loudly; a backend other than llama.cpp is
    rejected when the config is loaded
  - every profile carries model_id, backend, context_window, server_args,
    temperature, seed, max_tokens, stop_tokens and cache_prompt
  - defaults need no GPU: local models run on "cpu", server_args is empty
"""

import dataclasses

import pytest

from codecompass.online.config import OnlineConfig, load_online_config
from codecompass.online.generator import profiles

FIELDS = {"model_id", "backend", "context_window", "server_args", "temperature",
          "seed", "max_tokens", "stop_tokens", "cache_prompt"}


def test_dev_and_prod_profiles(monkeypatch):
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    cfg = OnlineConfig()
    assert profiles.resolve_profile(cfg, "dev")[1].model_id == "Qwen2.5-Coder-14B-Instruct"
    assert profiles.resolve_profile(cfg, "prod")[1].model_id == "Qwen2.5-Coder-32B-Instruct"


def test_default_is_dev_and_env_overrides(monkeypatch):
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    assert profiles.resolve_profile(OnlineConfig())[0] == "dev"
    monkeypatch.setenv("GENERATOR_PROFILE", "prod")
    name, profile = profiles.resolve_profile(OnlineConfig())
    assert (name, profile.model_id) == ("prod", "Qwen2.5-Coder-32B-Instruct")


def test_unknown_profile_fails_loudly(monkeypatch):
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    with pytest.raises(ValueError, match="unknown generator profile"):
        profiles.resolve_profile(OnlineConfig(), "large")


def test_profiles_carry_every_required_field():
    for profile in OnlineConfig().generator.profiles.values():
        assert FIELDS <= {f.name for f in dataclasses.fields(profile)}
        assert profile.backend == "llama.cpp"
        assert profile.cache_prompt is True
        assert isinstance(profile.seed, int)


def test_other_backend_is_rejected_when_loading(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text('[generator.profiles.dev]\nmodel_id = "x"\nbackend = "vllm"\n')
    with pytest.raises(ValueError, match="llama.cpp"):
        load_online_config(f)


def test_server_args_load_from_config(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text('[generator.profiles.dev]\nmodel_id = "x"\nserver_args = ["-np", "1"]\n')
    assert load_online_config(f).generator.profiles["dev"].server_args == ("-np", "1")


def test_defaults_run_on_cpu_without_gpu_settings():
    cfg = OnlineConfig()
    assert cfg.reranker.device == "cpu"
    assert cfg.offline.embedder.device == "cpu"
    for profile in cfg.generator.profiles.values():
        assert profile.server_args == ()
