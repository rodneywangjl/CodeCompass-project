"""Exclusion rules and the cheap-first classify pipeline (AC-6.x, O6)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass

DEFAULT_EXCLUDE_PATTERNS = (
    ".env*",
    "id_rsa*", "id_ed25519*", "*.pem", "*.key", "*.crt", "*.cert",
    "*.lock", "package-lock.json",
    "*.min.js", "*.min.css",
)
DEFAULT_EXCLUDE_DIRS = (
    "node_modules", "build", "dist", "target", "venv",
    ".venv", "__pycache__", ".git",
)


@dataclass(frozen=True)
class Decision:
    included: bool
    reason: str  # "include" | "excluded:pattern:<p>" | "excluded:dir:<d>" | ...


def decide(path: str, cfg, get_size=None, get_head=None) -> Decision:
    """Cheap-first: path rules, then size, then binary sniff, then non-code."""
    normpath = path.replace("\\", "/")
    name = normpath.rsplit("/", 1)[-1]
    for pat in cfg.exclude_patterns:
        if fnmatch.fnmatchcase(name, pat):
            return Decision(False, f"excluded:pattern:{pat}")
    for part in normpath.split("/"):
        if part in cfg.exclude_dirs:
            return Decision(False, f"excluded:dir:{part}")
    if get_size is not None and get_size() > cfg.max_file_bytes:
        return Decision(False, "too-large")
    if get_head is not None and b"\x00" in get_head():
        return Decision(False, "binary")
    ext = "." + normpath.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in {e.lower() for e in cfg.source_extensions}:
        return Decision(False, "non-code")
    return Decision(True, "include")


def decide_for_source(path: str, cfg, source, sha: str) -> Decision:
    """Wire :func:`decide` to a git source with lazy size/content reads (O6)."""
    return decide(
        path, cfg,
        get_size=lambda: source.blob_size(sha, path),
        get_head=lambda: source.read_blob(sha, path)[:8192],
    )


def classify_all(paths, cfg, source=None, sha=None) -> tuple:
    """Decide many paths; returns (decisions, counts-by-reason)."""
    from collections import Counter
    decisions = []
    counts: Counter = Counter()
    for path in paths:
        d = decide_for_source(path, cfg, source, sha) if source is not None \
            else decide(path, cfg)
        decisions.append(d)
        counts[d.reason] += 1
    return decisions, counts
