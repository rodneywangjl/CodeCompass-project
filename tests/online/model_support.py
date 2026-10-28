"""Shared setup for model-marked tests (T13.x): real llama-server, local only."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from codecompass.online.config import LoggingConfig, load_online_config
from codecompass.online.generator.llama import LlamaServerGenerator
from codecompass.online.generator.profiles import resolve_profile

ROOT = Path(__file__).resolve().parents[2]
# A 14B prompt prefill can take minutes on a 16 GB laptop (MODEL-SETUP.md §5).
GENERATION_TIMEOUT = 900


def real_config(tmp_path, offline=None):
    """The repo's codecompass.toml (pinned profiles), logs under tmp_path."""
    cfg = load_online_config(ROOT / "codecompass.toml")
    cfg = dataclasses.replace(
        cfg, logging=LoggingConfig(query_log_dir=str(tmp_path / "queries")),
        generator=dataclasses.replace(cfg.generator, timeout_seconds=GENERATION_TIMEOUT))
    return dataclasses.replace(cfg, offline=offline) if offline else cfg


def real_generator(cfg) -> LlamaServerGenerator:
    """The active profile's generator; skip if no server is running at all."""
    _, profile = resolve_profile(cfg)
    gen = LlamaServerGenerator(profile, server_url=cfg.generator.server_url,
                               timeout_seconds=GENERATION_TIMEOUT)
    if not gen.health_check():  # a running but mismatched server raises instead
        pytest.skip(f"no llama-server at {cfg.generator.server_url}; start one as in "
                    "MODEL-SETUP.md and set GENERATOR_PROFILE to match it")
    return gen
