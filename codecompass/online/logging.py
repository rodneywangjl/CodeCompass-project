"""Per-query audit log: build, time and persist (Article V.4, Spec US7)."""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("ensure_current", "retrieval", "reranking", "generation", "tool_execution",
          "citation_check")


def new_log(question: str, *, profile_name: str, profile, mode: str, tools) -> dict:
    """The fields every query records, whatever path it takes (AC-7.1, AC-5.8)."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "profile": profile_name,
        "model_id": profile.model_id,
        "cache_prompt": profile.cache_prompt,
        "mode": mode,
        "max_verifier_rounds": tools.max_verifier_rounds,
        "index": {},
        "retrieved": [],
        "tool_calls": [],
        "generator_calls": 0,
        "round_limit_hit": False,
        "citation": {},
        "timings": {stage: 0.0 for stage in STAGES},
    }


@contextmanager
def timed(log: dict, stage: str):
    """Add the time spent in the block to log["timings"][stage]."""
    start = time.perf_counter()
    try:
        yield
    finally:
        log["timings"][stage] += time.perf_counter() - start


class TimedGenerator:
    """Wraps a generator so generation time lands in the audit log."""

    def __init__(self, generator, log: dict) -> None:
        self._generator, self._log = generator, log

    def generate(self, messages: list[dict], *, on_text=None) -> str:
        with timed(self._log, "generation"):
            return self._generator.generate(messages)

    def count_tokens(self, text: str) -> int:
        return self._generator.count_tokens(text)


def write_log(log: dict, directory) -> Path:
    """Write *log* as JSON to a UTC-timestamped file under *directory* (AC-7.2)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{stamp}-{uuid.uuid4().hex[:8]}.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
