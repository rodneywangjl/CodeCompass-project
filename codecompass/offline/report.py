"""Run report rendering: dict, human-readable text, JSON file (AC-7.1, AC-7.2)."""

from __future__ import annotations

import json
from pathlib import Path


def to_dict(report) -> dict:
    return {
        "mode": report.mode,
        "note": report.note,
        "from_commit": report.from_commit,
        "to_commit": report.to_commit,
        "files_added": report.files_added,
        "files_modified": report.files_modified,
        "files_deleted": report.files_deleted,
        "files_renamed": report.files_renamed,
        "files_skipped": report.files_skipped,
        "skipped_by_rule": dict(report.skipped_by_rule),
        "files_non_code": report.files_non_code,
        "files_fallback": report.files_fallback,
        "chunks_added": report.chunks_added,
        "chunks_removed": report.chunks_removed,
        "embedder_model": report.embedder_model,
        "embedder_revision": report.embedder_revision,
        "schema_version": report.schema_version,
        "elapsed_seconds": report.elapsed_seconds,
        "timings": dict(report.timings),
    }


def to_text(report) -> str:
    lines = [
        f"mode: {report.mode}",
        f"commit: {report.from_commit} -> {report.to_commit}",
    ]
    if report.note:
        lines.append(f"note: {report.note}")
    lines.append(
        "files: "
        f"added={report.files_added} modified={report.files_modified} "
        f"deleted={report.files_deleted} renamed={report.files_renamed} "
        f"skipped={report.files_skipped} non_code={report.files_non_code} "
        f"fallback={report.files_fallback}")
    if report.skipped_by_rule:
        lines.append("skipped by rule: " + ", ".join(
            f"{rule}={n}" for rule, n in sorted(report.skipped_by_rule.items())))
    lines.append(
        f"chunks: added={report.chunks_added} removed={report.chunks_removed}")
    lines.append(
        f"embedder: {report.embedder_model}@{report.embedder_revision} "
        f"(schema {report.schema_version})")
    if report.timings:
        lines.append("timings: " + ", ".join(
            f"{stage}={seconds:.3f}s"
            for stage, seconds in sorted(report.timings.items())))
    lines.append(f"elapsed: {report.elapsed_seconds:.3f}s")
    return "\n".join(lines) + "\n"


def write_json(report, path) -> Path:
    """Write the machine-readable report file, creating parents as needed."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_dict(report), indent=2, sort_keys=True),
                   encoding="utf-8")
    return out
