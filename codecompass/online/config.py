"""Online pipeline configuration loader (Spec 002, Plan §7).

All retrieval parameters, model profiles, and tool settings are defined here
with defaults that a `codecompass.toml` file can override.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import tomllib
from dataclasses import dataclass, field
from typing import Any

from codecompass.offline.config import Config as OfflineConfig, load_config as load_offline_config

# Retrieval defaults (Article IV.2, Plan §7)
DEFAULT_VECTOR_K = 50
DEFAULT_KEYWORD_K = 50
DEFAULT_RRF_CONSTANT = 60
DEFAULT_RERANK_K = 50
DEFAULT_FINAL_K = 8

# Verifier tools defaults (Article V.1, Plan §7)
MAX_VERIFIER_ROUNDS = 3
DEFAULT_GIT_LOG_LIMIT = 20
DEFAULT_GIT_BLAME_TIMEOUT = 30
DEFAULT_GIT_LOG_TIMEOUT = 30
DEFAULT_ALLOWED_TOOLS = ("git_blame", "git_log")

# Generator & Re-ranker defaults (Article VIII.1, VIII.2, Plan §7)
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_SERVER_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_GENERATION_RESERVE_TOKENS = 1024
DEFAULT_STOP_TOKENS = ("<|im_end|>", "<|endoftext|>")


@dataclass(frozen=True)
class RetrievalConfig:
    """Parameters for hybrid retrieval and RRF merge (FR-4)."""
    vector_k: int = DEFAULT_VECTOR_K
    keyword_k: int = DEFAULT_KEYWORD_K
    rrf_constant: int = DEFAULT_RRF_CONSTANT
    rerank_k: int = DEFAULT_RERANK_K
    final_k: int = DEFAULT_FINAL_K


@dataclass(frozen=True)
class RerankerConfig:
    """Cross-encoder re-ranking configuration."""
    model: str = DEFAULT_RERANKER_MODEL
    device: str = "cpu"


@dataclass(frozen=True)
class ModelProfile:
    """Configuration profile for a generator model (Article VIII.4)."""
    model_id: str
    gguf_file: str = ""
    gguf_checksum: str = ""
    quantisation: str = "Q4_K_M"
    context_window: int = 32768
    temperature: float = 0.1
    max_tokens: int = 2048
    stop_tokens: tuple[str, ...] = DEFAULT_STOP_TOKENS


@dataclass(frozen=True)
class GeneratorConfig:
    """Generator settings and model profiles."""
    default_profile: str = "dev"
    server_url: str = DEFAULT_SERVER_URL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    generation_reserve_tokens: int = DEFAULT_GENERATION_RESERVE_TOKENS
    profiles: dict[str, ModelProfile] = field(default_factory=lambda: {
        "dev": ModelProfile(model_id="Qwen2.5-Coder-14B-Instruct"),
        "prod": ModelProfile(model_id="Qwen2.5-Coder-32B-Instruct"),
    })


@dataclass(frozen=True)
class ToolsConfig:
    """Verifier tool settings (Article V)."""
    max_verifier_rounds: int = MAX_VERIFIER_ROUNDS
    git_log_limit: int = DEFAULT_GIT_LOG_LIMIT
    git_blame_timeout: int = DEFAULT_GIT_BLAME_TIMEOUT
    git_log_timeout: int = DEFAULT_GIT_LOG_TIMEOUT
    allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS


@dataclass(frozen=True)
class LoggingConfig:
    """Audit logging configuration (Article V.4, AC-7.2)."""
    query_log_dir: str = ""


@dataclass(frozen=True)
class OnlineConfig:
    """Merged configuration for online retrieval and offline stores."""
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    offline: OfflineConfig = field(default_factory=OfflineConfig)


_OFFLINE_SECTIONS = {"index", "chunking", "files", "languages", "embedder", "lock"}
_ONLINE_SECTIONS = {"retrieval", "reranker", "generator", "tools", "logging"}


def get_generator_profile(config: OnlineConfig, profile_name: str | None = None) -> ModelProfile:
    """Resolve a generator profile by name, respecting GENERATOR_PROFILE env var (AC-5.1, AC-5.9).

    Raises:
        ValueError: Loud error if the requested profile name is not found.
    """
    if profile_name is None:
        profile_name = os.environ.get("GENERATOR_PROFILE") or config.generator.default_profile

    if profile_name not in config.generator.profiles:
        raise ValueError(f"unknown generator profile: {profile_name!r}")

    return config.generator.profiles[profile_name]


def _filter_offline_toml(raw: dict[str, Any]) -> str:
    """Convert offline-only sections back to TOML text for the offline loader."""
    lines: list[str] = []
    for section in sorted(_OFFLINE_SECTIONS):
        if section in raw and isinstance(raw[section], dict):
            lines.append(f"[{section}]")
            for k, v in raw[section].items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, (list, tuple)):
                    formatted = ", ".join(f'"{x}"' if isinstance(x, str) else str(x) for x in v)
                    lines.append(f"{k} = [{formatted}]")
                elif isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
            lines.append("")
    return "\n".join(lines)


def load_online_config(path: str | pathlib.Path | None) -> OnlineConfig:
    """Load and merge `codecompass.toml` into a validated :class:`OnlineConfig`."""
    raw: dict[str, Any] = {}
    if path is not None:
        p = pathlib.Path(path)
        if p.exists():
            with p.open("rb") as fh:
                raw = tomllib.load(fh)

    # 1. Retrieval
    retrieval_raw = raw.get("retrieval", {})
    retrieval = RetrievalConfig(**retrieval_raw)

    # 2. Reranker
    reranker_raw = raw.get("reranker", {})
    reranker = RerankerConfig(**reranker_raw)

    # 3. Generator
    generator_raw = raw.get("generator", {})
    gen_kwargs = {k: v for k, v in generator_raw.items() if k != "profiles"}

    profiles = {
        "dev": ModelProfile(model_id="Qwen2.5-Coder-14B-Instruct"),
        "prod": ModelProfile(model_id="Qwen2.5-Coder-32B-Instruct"),
    }
    if "profiles" in generator_raw and isinstance(generator_raw["profiles"], dict):
        for pname, pvals in generator_raw["profiles"].items():
            if isinstance(pvals, dict):
                p_kwargs = dict(pvals)
                if "stop_tokens" in p_kwargs:
                    p_kwargs["stop_tokens"] = tuple(p_kwargs["stop_tokens"])
                profiles[pname] = ModelProfile(**p_kwargs)

    generator = GeneratorConfig(profiles=profiles, **gen_kwargs)

    # 4. Tools
    tools_raw = dict(raw.get("tools", {}))
    if "allowed_tools" in tools_raw:
        tools_raw["allowed_tools"] = tuple(tools_raw["allowed_tools"])
    tools = ToolsConfig(**tools_raw)

    # 5. Logging
    logging_raw = raw.get("logging", {})
    logging = LoggingConfig(**logging_raw)

    # 6. Offline config merge
    offline_keys = [k for k in raw if k in _OFFLINE_SECTIONS]
    if offline_keys:
        offline_toml = _filter_offline_toml(raw)
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tf:
            tf.write(offline_toml)
            temp_path = tf.name
        try:
            offline_cfg = load_offline_config(temp_path)
        finally:
            pathlib.Path(temp_path).unlink(missing_ok=True)
    else:
        offline_cfg = load_offline_config(None)

    return OnlineConfig(
        retrieval=retrieval,
        reranker=reranker,
        generator=generator,
        tools=tools,
        logging=logging,
        offline=offline_cfg,
    )
