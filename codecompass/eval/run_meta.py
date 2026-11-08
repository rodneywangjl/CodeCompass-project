"""Shared run details for evaluation results files (Spec 003 AC-5.3, AC-6.2; Plan §3.1).

``run_meta()`` records what produced a run: the CodeCompass and repository commits,
the index, the config file, the models and devices, the generator profile, the
running ``llama-server`` and the machine. Every key is always present and a value is
``None`` when it does not apply, so two results files can be compared key by key
before their figures are combined (AC-5.3). Both runners call it (§2.2, §3.5).

Standard library only. ``/props`` is read through this module's ``urlopen`` and the GPU
name through ``gpu_name()``, so tests can replace both (the required suite blocks
real sockets and needs no GPU).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from codecompass.offline import status
from codecompass.online.config import get_generator_profile, load_online_config

PROJECT_DIR = Path(__file__).resolve().parents[2]
PROPS_TIMEOUT_SECONDS = 10
GPU_QUERY_TIMEOUT_SECONDS = 10


def run_meta(config_path, repo_path, *, index_dir=None, profile=None, server_url=None,
             project_dir=None) -> dict:
    """Return the run details of plan §3.1 as plain, JSON-safe data."""
    config_path = Path(config_path)
    raw = config_path.read_bytes()  # a missing config file fails here, loudly
    config = load_online_config(config_path)
    index = status(repo_path, config=config.offline, index_dir=index_dir)
    index_base = index_dir if index_dir is not None else config.offline.index.dir
    return {
        "codecompass": _codecompass(Path(project_dir) if project_dir else PROJECT_DIR),
        "repo": {"path": str(repo_path), "head_commit": _git(repo_path, "rev-parse", "HEAD")},
        "index": {
            "dir": None if index_base is None else str(index_base),
            "state": index.state,
            "indexed_commit": index.indexed_commit,
            "embedder_model": index.embedder_model,
            "embedder_revision": index.embedder_revision,
        },
        "config": {
            "path": str(config_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "retrieval": _plain(dataclasses.asdict(config.retrieval)),
            "chunking": _plain(dataclasses.asdict(config.offline.chunking)),
        },
        "embedder": {
            "model": config.offline.embedder.model,
            "revision": config.offline.embedder.revision,
            "device": config.offline.embedder.device,
        },
        "reranker": {
            "model": config.reranker.model,
            "revision": config.reranker.revision,
            "device": config.reranker.device,
            "dtype": config.reranker.dtype,
        },
        "generator": _generator(config, profile),
        "server": _server(server_url),
        "host": {
            "hostname": socket.gethostname(),
            "gpu": gpu_name(),
            "python": platform.python_version(),
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def gpu_name() -> str | None:
    """The first GPU's name from ``nvidia-smi``, or None when there is none."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, check=True,
                             timeout=GPU_QUERY_TIMEOUT_SECONDS).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.strip().splitlines()[0].strip() if out.strip() else ""
    return first or None


def _codecompass(project_dir: Path) -> dict:
    """Commit, exact tag and dirty flag of the CodeCompass checkout (all None outside git)."""
    top = _git(project_dir, "rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != project_dir.resolve():
        return {"commit": None, "tag": None, "dirty": None}
    porcelain = _git(project_dir, "status", "--porcelain")
    return {
        "commit": _git(project_dir, "rev-parse", "HEAD"),
        "tag": _git(project_dir, "describe", "--tags", "--exact-match", "HEAD"),
        "dirty": bool(porcelain),
    }


def _generator(config, profile: str | None) -> dict:
    keys = ("profile", "model_id", "gguf_file", "gguf_checksum_pinned", "context_window",
            "temperature", "seed", "timeout_seconds", "max_verifier_rounds")
    if profile is None:
        return dict.fromkeys(keys)
    prof = get_generator_profile(config, profile)  # an unknown profile raises ValueError
    return {
        "profile": profile,
        "model_id": prof.model_id,
        "gguf_file": prof.gguf_file,
        "gguf_checksum_pinned": prof.gguf_checksum,
        "context_window": prof.context_window,
        "temperature": prof.temperature,
        "seed": prof.seed,
        "timeout_seconds": config.generator.timeout_seconds,
        "max_verifier_rounds": config.tools.max_verifier_rounds,
    }


def _server(server_url: str | None) -> dict:
    if server_url is None:
        return dict.fromkeys(("url", "build_info", "model_path", "n_ctx"))
    props_url = server_url.rstrip("/") + "/props"
    try:
        with urlopen(Request(props_url, method="GET"), timeout=PROPS_TIMEOUT_SECONDS) as resp:
            props = json.loads(resp.read())
    except (OSError, ValueError) as exc:  # URLError and HTTPError are OSErrors
        raise ValueError(f"could not read llama-server at {props_url}: {exc}") from exc
    return {
        "url": server_url,
        "build_info": props.get("build_info"),
        "model_path": props.get("model_path"),
        "n_ctx": props.get("default_generation_settings", {}).get("n_ctx"),
    }


def _git(cwd, *args: str) -> str | None:
    """Stripped stdout of a git command in *cwd*, or None if it fails."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _plain(value):
    """JSON-safe copy: tuples become lists and paths become strings."""
    return json.loads(json.dumps(value, default=str))
