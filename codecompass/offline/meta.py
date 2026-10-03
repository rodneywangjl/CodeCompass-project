"""meta.json persistence with atomic writes and compatibility checks (AC-5.x)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from codecompass.offline.models import (
    SCHEMA_VERSION,
    EmbedderIdentity,
    IndexMeta,
)

FILENAME = "meta.json"


class MetaError(Exception):
    """Base class for index metadata failures."""


class SchemaMismatchError(MetaError):
    """Index schema version is unknown or older than expected."""


class EmbedderMismatchError(MetaError):
    """Embedder identity differs from the one that built the index."""


def repo_id(repo_path) -> str:
    """Stable repository identifier for the index directory (spec C4)."""
    return hashlib.sha1(str(Path(repo_path).resolve()).encode()).hexdigest()[:16]


def index_path_for(repo_path, base_dir) -> Path:
    """Per-repository index directory: base / stable repo id."""
    return Path(base_dir) / repo_id(repo_path)


def config_fingerprint(config) -> str:
    """Short hash of the content-affecting configuration (T7.6)."""
    material = json.dumps({
        "chunking": [config.chunking.target_tokens, config.chunking.hard_max_tokens],
        "files": [config.files.max_file_bytes, list(config.files.source_extensions),
                  list(config.files.exclude_patterns), list(config.files.exclude_dirs)],
        "embedder": [config.embedder.model, config.embedder.revision,
                     config.embedder.dimension],
    }, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def default_meta(identity: EmbedderIdentity, fingerprint: str = "") -> IndexMeta:    return IndexMeta(
        schema_version=SCHEMA_VERSION,
        embedder=identity,
        indexed_commit=None,
        last_run_at=None,
        config_fingerprint=fingerprint,
        in_progress=None,
    )


def _to_dict(meta: IndexMeta) -> dict:
    return {
        "schema_version": meta.schema_version,
        "embedder": {
            "model": meta.embedder.model,
            "revision": meta.embedder.revision,
            "dimension": meta.embedder.dimension,
        },
        "indexed_commit": meta.indexed_commit,
        "last_run_at": meta.last_run_at,
        "config_fingerprint": meta.config_fingerprint,
        "in_progress": meta.in_progress,
    }


def write_meta(index_dir, meta: IndexMeta) -> None:
    """Write meta.json atomically (temp file in the same directory + rename)."""
    directory = Path(index_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(directory), prefix="meta.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(_to_dict(meta), fh, indent=2, sort_keys=True)
        os.replace(tmp, directory / FILENAME)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def check_compatible(meta: IndexMeta, configured: EmbedderIdentity) -> None:
    """Refuse an index built with a different embedder (Article II.4, AC-5.3)."""
    found = meta.embedder
    if (found.model, found.revision, found.dimension) != (
            configured.model, configured.revision, configured.dimension):
        raise EmbedderMismatchError(
            f"embedder mismatch: index built with "
            f"{found.model}@{found.revision} dim {found.dimension}, "
            f"configured {configured.model}@{configured.revision} "
            f"dim {configured.dimension}")


def read_meta(index_dir) -> IndexMeta:
    """Read meta.json, refusing unknown schema versions (AC-5.4)."""
    raw = json.loads((Path(index_dir) / FILENAME).read_text(encoding="utf-8"))
    found = raw.get("schema_version")
    if found != SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"unknown schema version: found {found}, expected {SCHEMA_VERSION}")
    emb = raw.get("embedder", {})
    return IndexMeta(
        schema_version=found,
        embedder=EmbedderIdentity(
            model=emb.get("model", ""), revision=emb.get("revision", ""),
            dimension=emb.get("dimension", 0)),
        indexed_commit=raw.get("indexed_commit"),
        last_run_at=raw.get("last_run_at"),
        config_fingerprint=raw.get("config_fingerprint", ""),
        in_progress=raw.get("in_progress"),
    )
