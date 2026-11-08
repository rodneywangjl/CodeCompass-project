"""Retrieval ablations runner (Spec 003 AC-4.1-4.5, AC-6.1, AC-6.2, AC-6.4; Plan 003 §2.2).

Usage:
    python -m codecompass.eval.retrieval_run FILE [FILE ...] --repo PATH
        [--config TOML] [--index-dir DIR] [--sent] [--reported] [--out DIR]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from codecompass.eval.hitrate import hit_rates
from codecompass.eval.questions import _Repo, check_question_set, load_question_set
from codecompass.offline import _base_dir, open_index
from codecompass.offline.meta import index_path_for
from codecompass.online import _default_generator, _default_reranker
from codecompass.online.agent.harness import system_prompt, user_message
from codecompass.online.config import check_mode, load_online_config
from codecompass.online.context import RetrievedChunk, chunk_budget, fit_chunks
from codecompass.online.generator.profiles import resolve_profile
from codecompass.online.retrieval.hybrid import (
    embed_question,
    keyword_search,
    retrieve,
    vector_search,
)
from codecompass.online.retrieval.reranker import rerank_chunks

DEFAULT_KS = {
    "vector": [1, 5, 10],
    "bm25": [1, 5, 10],
    "rrf": [1, 5, 10],
    "rrf+rerank": [1, 5],
}

SCORE_NOTE = (
    "vector and bm25 'score' is the rank position (10 = first); "
    "those functions return no similarity score"
)


def _check_clean_git(cc_dir: Path) -> tuple[str, bool, str | None]:
    if not (cc_dir / ".git").exists():
        return "unknown", False, None
    r_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cc_dir, capture_output=True, text=True
    )
    commit = r_commit.stdout.strip() if r_commit.returncode == 0 else "unknown"
    r_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=cc_dir, capture_output=True, text=True
    )
    clean = r_status.returncode == 0 and not r_status.stdout.strip()
    r_tag = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        cwd=cc_dir,
        capture_output=True,
        text=True,
    )
    tag = r_tag.stdout.strip() if r_tag.returncode == 0 else None
    return commit, clean, tag


def _compute_whole_file(repo_helper: _Repo, commit: str, truth: list[dict]) -> bool:
    if not truth:
        return False
    for entry in truth:
        lines = repo_helper.line_count(commit, entry["path"])
        if not (entry["start_line"] == 1 and lines is not None and entry["end_line"] == lines):
            return False
    return True


def run_retrieval(
    question_files: list[Path | str],
    repo_path: Path | str,
    *,
    config,
    index_dir: Path | str | None = None,
    embedder=None,
    reranker=None,
    generator=None,
    sent: bool = False,
    reported: bool = False,
    codecompass_dir: Path | str | None = None,
    config_path: Path | str | None = None,
    out_dir: Path | str = Path("eval/results"),
) -> Path:
    """Run retrieval ablations over the given question sets."""
    started_at = datetime.now(timezone.utc).isoformat()
    repo_path = Path(repo_path)
    out_dir = Path(out_dir)

    cc_dir = (
        Path(codecompass_dir)
        if codecompass_dir is not None
        else Path(__file__).resolve().parents[2]
    )

    if reported:
        if config_path is None:
            raise ValueError(
                "--reported needs --config so the official settings are recorded"
            )
        if not (cc_dir / ".git").exists():
            raise ValueError(
                f"--reported requires a git repository, but {cc_dir} has no .git"
            )
        r_status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=cc_dir, capture_output=True, text=True
        )
        if r_status.returncode != 0:
            raise ValueError(f"git status failed in {cc_dir}: {r_status.stderr}")
        if r_status.stdout.strip():
            raise ValueError(
                f"--reported refuses to run with uncommitted changes in {cc_dir}:\n"
                f"{r_status.stdout}"
            )

    if sent and getattr(config.retrieval, "docs_fallback", False):
        raise ValueError("--sent measures the docs_fallback-off path only")

    cc_commit, cc_clean, cc_tag = _check_clean_git(cc_dir)
    label = "reported" if reported else "dev"

    # 1. Load and check question sets
    all_rows = []
    question_files_meta = []
    for f in question_files:
        p = Path(f)
        rows = load_question_set(p)
        all_rows.extend(rows)
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        question_files_meta.append({"path": str(p), "sha256": sha})

    problems = check_question_set(all_rows, repo_path)
    if problems:
        raise ValueError(
            f"Question set check failed with {len(problems)} problem(s):\n"
            + "\n".join(problems)
        )

    # 2. Open index and verify commit match
    actual_index_dir = str(
        index_path_for(repo_path, _base_dir(config.offline, index_dir))
    )
    handles = open_index(
        repo_path, config=config.offline, index_dir=index_dir, embedder=embedder
    )
    try:
        indexed_commit = handles.meta.indexed_commit
        for row in all_rows:
            if row["repo_commit"] != indexed_commit:
                raise ValueError(
                    f"Index commit {indexed_commit[:7]} ({indexed_commit}) does not match "
                    f"question repo_commit {row['repo_commit'][:7]} ({row['repo_commit']})"
                )

        # 3. Setup reranker and generator if needed
        if reranker is None:
            reranker = _default_reranker(config)

        profile = None
        if sent:
            name, profile = resolve_profile(config)
            if generator is None:
                generator = _default_generator(config, profile)

        # 4. Process each question
        repo_helper = _Repo(repo_path)
        questions_out = []
        for row in all_rows:
            row_out = dict(row)
            truth = row.get("ground_truth_files", [])
            row_out["whole_file"] = _compute_whole_file(
                repo_helper, row["repo_commit"], truth
            )

            if not truth:
                row_out["ranked"] = {}
                questions_out.append(row_out)
                continue

            q_text = row["question"]

            # Vector top 10
            q_vec = embed_question(handles, q_text)
            vec_hits = vector_search(handles.vector, q_vec, 10)
            vec_recs = handles.vector.records_for_ids(vec_hits)
            vec_list = [
                {
                    "path": vec_recs[cid]["metadata"]["file_path"],
                    "start_line": vec_recs[cid]["metadata"]["start_line"],
                    "end_line": vec_recs[cid]["metadata"]["end_line"],
                    "score": float(10 - i),
                }
                for i, cid in enumerate(vec_hits)
                if cid in vec_recs
            ]

            # BM25 top 10
            kw_hits = keyword_search(handles.keyword, q_text, 10)
            kw_recs = handles.vector.records_for_ids(kw_hits)
            bm25_list = [
                {
                    "path": kw_recs[cid]["metadata"]["file_path"],
                    "start_line": kw_recs[cid]["metadata"]["start_line"],
                    "end_line": kw_recs[cid]["metadata"]["end_line"],
                    "score": float(10 - i),
                }
                for i, cid in enumerate(kw_hits)
                if cid in kw_recs
            ]

            # RRF shortlist
            shortlist = retrieve(handles, q_text, config=config.retrieval)
            rrf_recs = handles.vector.records_for_ids([cid for cid, _ in shortlist])
            rrf_list = [
                {
                    "path": rrf_recs[cid]["metadata"]["file_path"],
                    "start_line": rrf_recs[cid]["metadata"]["start_line"],
                    "end_line": rrf_recs[cid]["metadata"]["end_line"],
                    "score": float(score),
                }
                for cid, score in shortlist
                if cid in rrf_recs
            ]

            # RRF + Rerank
            retrieved_chunks = [
                RetrievedChunk.from_record(cid, rrf_recs[cid])
                for cid, _ in shortlist
                if cid in rrf_recs
            ]
            ranked_chunks = rerank_chunks(
                reranker, q_text, retrieved_chunks, len(retrieved_chunks)
            )
            rerank_list = [
                {
                    "path": c.path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "score": float(score),
                }
                for c, score in ranked_chunks
            ]

            ranked_dict = {
                "vector": vec_list,
                "bm25": bm25_list,
                "rrf": rrf_list,
                "rrf+rerank": rerank_list,
            }

            if sent:
                top_score = max((score for _, score in ranked_chunks), default=None)
                if (
                    top_score is None
                    or top_score < config.retrieval.min_top_score
                ):
                    sent_list = []
                else:
                    mode = (
                        check_mode(config.pipeline.mode)
                        if hasattr(config, "pipeline")
                        else "rag"
                    )
                    tools_on = mode == "rag_tools"
                    tools = (
                        config.tools
                        if tools_on
                        else dataclasses.replace(config.tools, max_verifier_rounds=0)
                    )
                    prefix = generator.count_tokens(
                        system_prompt(tools_enabled=tools_on)
                    ) + generator.count_tokens(
                        user_message(q_text, [], tools_enabled=tools_on)
                    )
                    budget = chunk_budget(profile, tools, prefix)
                    candidates = [
                        c for c, _ in ranked_chunks[:config.retrieval.final_k]
                    ]
                    sent_fitted = fit_chunks(candidates, budget, generator.count_tokens)
                    sent_score_map = {c.chunk_id: score for c, score in ranked_chunks}
                    sent_list = [
                        {
                            "path": c.path,
                            "start_line": c.start_line,
                            "end_line": c.end_line,
                            "score": float(sent_score_map.get(c.chunk_id, 0.0)),
                        }
                        for c in sent_fitted
                    ]
                ranked_dict["sent"] = sent_list

            row_out["ranked"] = ranked_dict
            questions_out.append(row_out)

        # 5. Summary maths
        ks = dict(DEFAULT_KS)
        if sent:
            ks["sent"] = ["all"]
        summary = hit_rates(questions_out, ks)

        # 6. Meta collection
        ended_at = datetime.now(timezone.utc).isoformat()
        meta_ks = dict(ks)
        if not sent:
            meta_ks["sent"] = None

        embedder_obj = getattr(handles, "embedder", embedder)
        embedder_meta = {
            "model_id": getattr(
                embedder_obj,
                "model_id",
                getattr(embedder_obj, "model", type(embedder_obj).__name__),
            ),
            "revision": getattr(embedder_obj, "revision", None),
            "device": getattr(embedder_obj, "device", None),
            "dtype": (
                str(getattr(embedder_obj, "dtype", None))
                if getattr(embedder_obj, "dtype", None)
                else None
            ),
        }

        reranker_meta = {
            "model_id": getattr(
                reranker,
                "model_id",
                getattr(reranker, "model_name", type(reranker).__name__),
            ),
            "revision": getattr(reranker, "revision", None),
            "device": getattr(reranker, "device", None),
            "dtype": (
                str(getattr(reranker, "dtype", None))
                if getattr(reranker, "dtype", None)
                else None
            ),
        }

        packages = {}
        for pkg in [
            "chromadb",
            "tantivy",
            "torch",
            "transformers",
            "sentence_transformers",
            "pydantic",
            "pytest",
        ]:
            try:
                packages[pkg] = importlib.metadata.version(pkg)
            except Exception:
                pass

        plan_sha = None
        plan_path = cc_dir / "docs" / "specs" / "003-evaluation" / "plan.md"
        if plan_path.exists():
            plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()

        repo_commit = all_rows[0]["repo_commit"] if all_rows else indexed_commit

        meta = {
            "codecompass_commit": cc_commit,
            "codecompass_clean": cc_clean,
            "codecompass_tag": cc_tag,
            "repo": str(repo_path),
            "repo_commit": repo_commit,
            "indexed_commit": indexed_commit,
            "index_dir": actual_index_dir,
            "embedder": embedder_meta,
            "reranker": reranker_meta,
            "retrieval": (
                dataclasses.asdict(config.retrieval)
                if dataclasses.is_dataclass(config.retrieval)
                else config.retrieval
            ),
            "chunking": (
                dataclasses.asdict(config.offline.chunking)
                if dataclasses.is_dataclass(config.offline.chunking)
                else config.offline.chunking
            ),
            "config_path": str(config_path) if config_path else None,
            "question_files": question_files_meta,
            "ks": meta_ks,
            "label": label,
            "score_note": SCORE_NOTE,
            "plan_sha": plan_sha,
            "dirty": not cc_clean,
            "packages": packages,
            "started_at": started_at,
            "ended_at": ended_at,
            "platform": platform.platform(),
            "python": sys.version,
        }

        results = {
            "meta": meta,
            "questions": questions_out,
            "summary": summary,
        }

        # 7. Write results file
        out_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        file_ts = now.strftime("%Y%m%dT%H%M%SZ")
        res_file = out_dir / f"retrieval-{file_ts}.json"
        if res_file.exists():
            res_file = out_dir / f"retrieval-{file_ts}_{now.microsecond:06d}.json"
        res_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        return res_file

    finally:
        handles.close()


def main(argv=None) -> int:
    """CLI entry point for retrieval ablations runner."""
    parser = argparse.ArgumentParser(
        prog="python -m codecompass.eval.retrieval_run",
        description="Run retrieval ablations over question sets (Spec 003 T4.2).",
    )
    parser.add_argument("files", nargs="+", type=Path, help="JSONL question files")
    parser.add_argument("--repo", required=True, type=Path, help="Path to repository")
    parser.add_argument("--config", type=Path, default=None, help="Path to config TOML")
    parser.add_argument("--index-dir", type=Path, default=None, help="Custom index directory")
    parser.add_argument("--sent", action="store_true", help="Measure sent figure with generator")
    parser.add_argument(
        "--reported", action="store_true", help="Reported run (clean git required)"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("eval/results"), help="Output directory"
    )

    args = parser.parse_args(argv)
    try:
        cfg = load_online_config(args.config) if args.config else load_online_config(None)
        res_path = run_retrieval(
            args.files,
            args.repo,
            config=cfg,
            index_dir=args.index_dir,
            embedder=None,
            reranker=None,
            generator=None,
            sent=args.sent,
            reported=args.reported,
            config_path=args.config,
            out_dir=args.out,
        )
        print(str(res_path))
        return 0
    except Exception as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
