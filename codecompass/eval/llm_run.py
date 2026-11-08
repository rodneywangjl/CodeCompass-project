"""LLM runner: every question through ``ask()`` in one configuration (Spec 003 AC-5.2-5.5,
AC-6.1-6.4; Plan 003 §3.5).

Usage:
    python -m codecompass.eval.llm_run FILE [FILE ...] --repo PATH --config TOML
        --mode {no_retrieval,rag,rag_tools} [--subset PATH] [--index-dir DIR]
        [--profile dev] [--reported] [--out DIR] [--resume FILE]

Before any question it checks the mode, the config file, the question set, the
repository and index commits, and (``--reported``) a clean checkout. The models are
created once and passed to every ``ask()`` call, each with a fresh RecordingGenerator so
the full context is kept (§13 C8). A failing question is retried once, then recorded
with its error. The results file is rewritten after every question, so a run can be
resumed with ``--resume``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from codecompass.eval.questions import check_question_set, load_question_set
from codecompass.eval.recording import RecordingGenerator
from codecompass.eval.run_meta import run_meta
from codecompass.eval.subset import file_sha256
from codecompass.online import ask
from codecompass.online import _default_generator, _default_reranker  # ask()'s own defaults
from codecompass.online.config import check_mode, load_online_config
from codecompass.online.generator.profiles import resolve_profile

DEFAULT_SUBSET = Path("eval/questions/grading-subset.json")
DEFAULT_OUT = Path("eval/results")
ATTEMPTS = 2  # the first try and one retry (AC-5.5)
RUN_META_GROUPS = ("codecompass", "repo", "index", "config", "embedder", "reranker",
                   "generator", "server")  # compared on --resume; "host" may differ


def run_llm(question_files, repo_path, *, config_path, mode, subset_path=DEFAULT_SUBSET,
            profile="dev", index_dir=None, generator=None, reranker=None, embedder=None,
            reported=False, project_dir=None, out_dir=DEFAULT_OUT, resume=None) -> Path:
    """Run every question in *mode* and return the results file's path (plan §3.5)."""
    started_at = _now()
    check_mode(mode)  # an unknown mode raises ValueError
    config_path = Path(config_path)
    if not config_path.is_file():  # load_online_config would silently use the defaults
        raise ValueError(f"config file not found: {config_path}")
    config = load_online_config(config_path)
    config = dataclasses.replace(config, pipeline=dataclasses.replace(config.pipeline, mode=mode))
    profile_name, model = resolve_profile(config, profile)

    files = [Path(f) for f in question_files]
    rows = [row for path in files for row in load_question_set(path)]
    problems = check_question_set(rows, repo_path)
    if problems:
        raise ValueError(f"the question set has {len(problems)} problem(s):\n"
                         + "\n".join(problems))
    subset_path = Path(subset_path)
    subset_ids = set(json.loads(subset_path.read_text(encoding="utf-8"))["ids"])

    meta = run_meta(config_path, repo_path, index_dir=index_dir, profile=profile_name,
                    server_url=None if generator is not None else config.generator.server_url,
                    project_dir=project_dir)
    _check_conditions(meta, rows, reported)
    meta.update({
        "mode": mode,
        "docs_fallback": config.retrieval.docs_fallback,
        "label": "reported" if reported else "dev",
        "question_files": [{"path": str(p), "sha256": file_sha256(p)} for p in files],
        "subset": {"path": str(subset_path), "sha256": file_sha256(subset_path)},
        "started_at": started_at,
        "ended_at": None,
    })

    done: dict[str, dict] = {}
    if resume is not None:
        out_path = Path(resume)
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        _check_resume(previous["meta"], meta, mode)
        meta = previous["meta"]
        done = {q["id"]: q for q in previous["questions"]}
    else:
        out_path = _new_path(Path(out_dir), mode)

    inner = generator if generator is not None else _default_generator(config, model)
    reranker = reranker if reranker is not None else _default_reranker(config)

    def write() -> None:
        meta["ended_at"] = _now()
        ordered = [done[r["id"]] for r in rows if r["id"] in done]
        _write_json(out_path, {"meta": meta, "questions": ordered})

    write()
    for row in rows:
        if row["id"] in done:
            continue
        done[row["id"]] = _run_question(row, repo_path, config=config, profile=profile_name,
                                        index_dir=index_dir, inner=inner, reranker=reranker,
                                        embedder=embedder,
                                        in_subset=row["id"] in subset_ids)
        write()
    return out_path


def _check_conditions(meta: dict, rows: list[dict], reported: bool) -> None:
    """Refuse before any question when the conditions are not the agreed ones."""
    if reported and meta["codecompass"]["dirty"] is not False:
        raise ValueError("--reported refuses to run: CodeCompass has uncommitted changes "
                         "or is not a git checkout")
    head = meta["repo"]["head_commit"]
    indexed = meta["index"]["indexed_commit"]
    for commit in sorted({r["repo_commit"] for r in rows}):
        if head != commit:
            raise ValueError(f"repo HEAD {head} is not the questions' repo_commit {commit}; "
                             f"check out {commit} first")
        if indexed != commit:
            raise ValueError(f"the index commit {indexed} is not the questions' repo_commit "
                             f"{commit}; build the index at {commit} first")


def _check_resume(previous: dict, current: dict, mode: str) -> None:
    if previous.get("mode") != mode:
        raise ValueError(f"--resume file is a {previous.get('mode')!r} run, not {mode!r}")
    for group in RUN_META_GROUPS:
        if previous.get(group) != current.get(group):
            raise ValueError(f"--resume file was run under different conditions ({group})")


def _run_question(row, repo_path, *, config, profile, index_dir, inner, reranker, embedder,
                  in_subset) -> dict:
    record = {"id": row["id"], "set": row["set"], "category": row["category"],
              "complexity": row["complexity"], "in_subset": in_subset}
    result, error, rec = None, None, None
    attempts = 0
    for attempts in range(1, ATTEMPTS + 1):
        rec = RecordingGenerator(inner)
        try:
            result = ask(repo_path, row["question"], config=config, profile=profile,
                         index_dir=index_dir, generator=rec, reranker=reranker,
                         embedder=embedder)
            error = None
            break
        except Exception as exc:  # recorded and retried once (AC-5.5); Ctrl-C still stops
            error = {"type": type(exc).__name__, "message": str(exc)}
    record.update(_result_fields(result, rec))
    record.update({"error": error, "attempts": attempts})
    return record


def _result_fields(result, rec: RecordingGenerator) -> dict:
    messages = rec.calls if rec is not None else []
    if result is None:
        return {"mode": None, "answer": None, "raw_text": None, "citation_outcome": None,
                "sources": None, "unverified": None, "unreferenced": None, "retrieved": None,
                "tool_calls": None, "round_limit_hit": None, "timings": None,
                "log_file": None, "messages": messages}
    log = result.audit_log
    citation = log.get("citation", {})
    return {
        "mode": log.get("mode"),
        "answer": result.answer,
        "raw_text": messages[-1]["output"] if messages else None,
        "citation_outcome": result.citation_outcome,
        "sources": [dataclasses.asdict(s) for s in result.sources],
        "unverified": list(citation.get("unverified", [])),
        "unreferenced": list(citation.get("unreferenced", [])),
        "retrieved": log.get("retrieved", []),
        "tool_calls": log.get("tool_calls", []),
        "round_limit_hit": log.get("round_limit_hit"),
        "timings": log.get("timings", {}),
        "log_file": log.get("log_file"),
        "messages": messages,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_path(out_dir: Path, mode: str) -> Path:
    now = datetime.now(timezone.utc)
    path = out_dir / f"llm-{mode}-{now:%Y%m%dT%H%M%SZ}.json"
    if path.exists():
        path = out_dir / f"llm-{mode}-{now:%Y%m%dT%H%M%SZ}_{now.microsecond:06d}.json"
    return path


def _write_json(path: Path, data: dict) -> None:
    """Write via a temporary file, so an interrupted write never leaves a broken file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codecompass.eval.llm_run",
                                     description="Run every question through ask() in one "
                                                 "configuration (Spec 003 T5.5).")
    parser.add_argument("files", nargs="+", type=Path, help="JSONL question files")
    parser.add_argument("--repo", required=True, type=Path, help="repository under test")
    parser.add_argument("--config", required=True, type=Path, help="evaluation config TOML")
    parser.add_argument("--mode", required=True, help="no_retrieval, rag or rag_tools")
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET,
                        help=f"grading subset file (default {DEFAULT_SUBSET})")
    parser.add_argument("--index-dir", type=Path, default=None, help="index directory")
    parser.add_argument("--profile", default="dev", help="generator profile (default dev)")
    parser.add_argument("--reported", action="store_true",
                        help="reported run: needs a clean git checkout")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="results directory")
    parser.add_argument("--resume", type=Path, default=None, help="results file to continue")
    args = parser.parse_args(argv)
    try:
        path = run_llm(args.files, args.repo, config_path=args.config, mode=args.mode,
                       subset_path=args.subset, profile=args.profile,
                       index_dir=args.index_dir, reported=args.reported, out_dir=args.out,
                       resume=args.resume)
    except Exception as e:  # noqa: BLE001 - every failure becomes one error line
        print(f"error: {e}")
        return 1
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
