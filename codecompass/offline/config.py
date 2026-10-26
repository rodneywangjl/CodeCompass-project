"""Config loader: ``codecompass.toml`` -> typed :class:`Config` (FR-17).

All model names, thresholds, sizes, and paths live here as defaults that a
config file can override. Nothing outside this module may name a model.
"""

from __future__ import annotations

import os
import pathlib
import tomllib
from dataclasses import dataclass, field

from codecompass.offline.exclusions import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_PATTERNS,
)

DEFAULT_EMBEDDER_MODEL = "jinaai/jina-embeddings-v2-base-code"
# Pinned upstream revision (resolved 2026-10-04); trust_remote_code loads code
# from the repo, so the revision must stay pinned (Article VIII.1).
DEFAULT_EMBEDDER_REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
DEFAULT_EMBEDDER_DIMENSION = 768
DEFAULT_TARGET_TOKENS = 512
DEFAULT_HARD_MAX_TOKENS = 8192  # embedder input limit (constitution VIII.1)
DEFAULT_LOCK_TIMEOUT_SECONDS = 120  # spec C8


def _default_index_base() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or "~\\AppData\\Local"
        return str(pathlib.Path(base).expanduser() / "codecompass")
    if __import__("sys").platform == "darwin":
        return str(pathlib.Path("~/Library/Application Support/codecompass").expanduser())
    data_home = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    return str(pathlib.Path(data_home).expanduser() / "codecompass")


@dataclass(frozen=True)
class IndexConfig:
    dir: str | None = None


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = DEFAULT_TARGET_TOKENS
    hard_max_tokens: int = DEFAULT_HARD_MAX_TOKENS
    batch_files: int = 50


@dataclass(frozen=True)
class FilesConfig:
    max_file_bytes: int = 1_048_576
    source_extensions: tuple = (
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
        ".c", ".h", ".cpp", ".hpp", ".go", ".rs", ".rb",
        ".php", ".swift", ".kt", ".cs", ".scala", ".sh",
    )
    exclude_patterns: tuple = DEFAULT_EXCLUDE_PATTERNS
    exclude_dirs: tuple = DEFAULT_EXCLUDE_DIRS


@dataclass(frozen=True)
class LanguagesConfig:
    treesitter: tuple = ("python", "javascript", "typescript", "tsx", "java")


@dataclass(frozen=True)
class EmbedderConfig:
    model: str = DEFAULT_EMBEDDER_MODEL
    revision: str = DEFAULT_EMBEDDER_REVISION
    dimension: int = DEFAULT_EMBEDDER_DIMENSION
    device: str = "cpu"
    batch_size: int = 32


@dataclass(frozen=True)
class LockConfig:
    timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS


@dataclass(frozen=True)
class Config:
    index: IndexConfig = field(default_factory=IndexConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    languages: LanguagesConfig = field(default_factory=LanguagesConfig)
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    lock: LockConfig = field(default_factory=LockConfig)


_KNOWN_KEYS: dict[str, set[str]] = {
    "index": {"dir"},
    "chunking": {"target_tokens", "hard_max_tokens", "batch_files"},
    "files": {"max_file_bytes", "source_extensions", "exclude_patterns", "exclude_dirs"},
    "languages": {"treesitter"},
    "embedder": {"model", "revision", "dimension", "device", "batch_size"},
    "lock": {"timeout_seconds"},
}


def load_config(path: str | pathlib.Path | None) -> Config:
    """Load *path* (or defaults when missing) into a validated :class:`Config`."""
    raw: dict = {}
    anchor: pathlib.Path | None = None
    if path is not None:
        p = pathlib.Path(path)
        anchor = p.parent
        if p.exists():
            with p.open("rb") as fh:
                raw = tomllib.load(fh)
    return config_from_dict(raw, anchor=anchor)


def config_from_dict(raw: dict, *, anchor: pathlib.Path | None = None) -> Config:
    """Validate parsed TOML *raw* into a :class:`Config`.

    Relative paths resolve against *anchor* (the config file's directory),
    or the working directory when it is None.
    """
    for section, values in raw.items():
        if section not in _KNOWN_KEYS:
            raise ValueError(f"unknown config section: {section!r}")
        if not isinstance(values, dict):
            raise ValueError(f"config section {section!r} must be a table")
        for key in values:
            if key not in _KNOWN_KEYS[section]:
                raise ValueError(f"unknown config key: {section}.{key}")

    index_raw = raw.get("index", {})
    index_dir = index_raw.get("dir")
    if index_dir is None:
        index_dir = _default_index_base()
    elif not os.path.isabs(index_dir):
        base = anchor if anchor is not None else pathlib.Path.cwd()
        index_dir = str(base / index_dir)

    chunking = ChunkingConfig(
        **{k: v for k, v in raw.get("chunking", {}).items()}
    ) if "chunking" in raw else ChunkingConfig()
    if chunking.target_tokens > chunking.hard_max_tokens:
        raise ValueError(
            f"target_tokens ({chunking.target_tokens}) exceeds "
            f"hard_max_tokens ({chunking.hard_max_tokens})"
        )

    files_raw = raw.get("files", {})
    for seq_key in ("source_extensions", "exclude_patterns", "exclude_dirs"):
        if seq_key in files_raw:
            files_raw[seq_key] = tuple(files_raw[seq_key])
    languages_raw = raw.get("languages", {})
    if "treesitter" in languages_raw:
        languages_raw["treesitter"] = tuple(languages_raw["treesitter"])

    return Config(
        index=IndexConfig(dir=index_dir),
        chunking=chunking,
        files=FilesConfig(**files_raw) if files_raw else FilesConfig(),
        languages=LanguagesConfig(**languages_raw) if languages_raw else LanguagesConfig(),
        embedder=EmbedderConfig(**raw["embedder"]) if "embedder" in raw else EmbedderConfig(),
        lock=LockConfig(**raw["lock"]) if "lock" in raw else LockConfig(),
    )
