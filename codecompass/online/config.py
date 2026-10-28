"""Online pipeline configuration loader (Spec 002, Plan §7).

All retrieval parameters, model profiles, and tool settings are defined here
with defaults that a `codecompass.toml` file can override.
"""

from __future__ import annotations

import os
import pathlib
import tomllib
from dataclasses import dataclass, field
from typing import Any

from codecompass.offline.config import Config as OfflineConfig, config_from_dict

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
DEFAULT_MAX_TOOL_OUTPUT_TOKENS = 768

# Generator & Re-ranker defaults (Article VIII.1, VIII.2, Plan §7)
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
# Pinned upstream revision (resolved 2026-10-26; Article VIII.1, VII.6).
DEFAULT_RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
DEFAULT_SERVER_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_GENERATION_RESERVE_TOKENS = 1024
DEFAULT_STOP_TOKENS = ("<|im_end|>", "<|endoftext|>")
DEFAULT_SEED = 42
BACKEND = "llama.cpp"  # the only backend (Article VIII.2, VIII.4)


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
    revision: str = DEFAULT_RERANKER_REVISION
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
    backend: str = BACKEND
    server_args: tuple[str, ...] = ()
    seed: int = DEFAULT_SEED
    cache_prompt: bool = True

    def __post_init__(self) -> None:
        if self.backend != BACKEND:
            raise ValueError(f"profile {self.model_id!r}: backend must be {BACKEND!r}, "
                             f"got {self.backend!r} (Article VIII.2)")


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
    max_tool_output_tokens: int = DEFAULT_MAX_TOOL_OUTPUT_TOKENS


# Evaluation configurations (Article VII.2-VII.3, Plan D17)
PIPELINE_MODES = ("rag_tools", "rag", "no_retrieval")


@dataclass(frozen=True)
class PipelineConfig:
    """Which Article VII.2 configuration ask() runs; rag_tools is the product."""
    mode: str = "rag_tools"


def check_mode(mode: str) -> str:
    """Fail loudly on an unknown pipeline.mode (AC-10.1)."""
    if mode not in PIPELINE_MODES:
        raise ValueError(f"pipeline.mode must be one of {', '.join(PIPELINE_MODES)}; "
                         f"got {mode!r}")
    return mode


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
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    offline: OfflineConfig = field(default_factory=OfflineConfig)


_OFFLINE_SECTIONS = {"index", "chunking", "files", "languages", "embedder", "lock"}
_ONLINE_SECTIONS = {"retrieval", "reranker", "generator", "tools", "logging", "pipeline"}


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


def load_online_config(path: str | pathlib.Path | None) -> OnlineConfig:
    """Load and merge `codecompass.toml` into a validated :class:`OnlineConfig`."""
    raw: dict[str, Any] = {}
    anchor: pathlib.Path | None = None
    if path is not None:
        p = pathlib.Path(path)
        anchor = p.parent
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
                for key in ("stop_tokens", "server_args"):
                    if key in p_kwargs:
                        p_kwargs[key] = tuple(p_kwargs[key])
                profiles[pname] = ModelProfile(**p_kwargs)

    generator = GeneratorConfig(profiles=profiles, **gen_kwargs)

    # 4. Tools
    tools_raw = dict(raw.get("tools", {}))
    rounds = tools_raw.get("max_verifier_rounds", MAX_VERIFIER_ROUNDS)
    if type(rounds) is not int or rounds < 0:
        raise ValueError(f"tools.max_verifier_rounds must be a non-negative integer "
                         f"so the loop stays bounded (Article V.1); got {rounds!r}")
    if "allowed_tools" in tools_raw:
        tools_raw["allowed_tools"] = tuple(tools_raw["allowed_tools"])
        extra = sorted(set(tools_raw["allowed_tools"]) - set(DEFAULT_ALLOWED_TOOLS))
        if extra:
            raise ValueError(f"tools.allowed_tools may only switch tools off, not add "
                             f"them (Article V.2); not allowed: {', '.join(extra)}")
    tools = ToolsConfig(**tools_raw)

    # 5. Logging
    logging_raw = raw.get("logging", {})
    logging = LoggingConfig(**logging_raw)
    pipeline = PipelineConfig(**raw.get("pipeline", {}))
    check_mode(pipeline.mode)

    # 6. Offline config merge: pass the parsed sections straight through, so
    # values are never re-serialised and relative paths keep the file's anchor.
    offline_cfg = config_from_dict(
        {k: v for k, v in raw.items() if k in _OFFLINE_SECTIONS}, anchor=anchor)

    return OnlineConfig(
        retrieval=retrieval,
        reranker=reranker,
        generator=generator,
        tools=tools,
        logging=logging,
        pipeline=pipeline,
        offline=offline_cfg,
    )
