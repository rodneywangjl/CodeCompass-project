"""Automatic labels and the blind grading sheet (Spec 003 AC-7.1-7.4, AC-8.1, AC-8.3,
AC-8.5, AC-9.1, AC-10.1; Plan 003 §3.6).

Reads the LLM runner's results files. It pre-fills only what is deterministic
(abstention, format slip, uncited, H1) and never fills in H2, H3 or the quality score,
which are human judgements (AC-8.5). The configuration is replaced by an opaque row id.

Usage:
    python -m codecompass.eval.grading --a NO_RETRIEVAL.json --b RAG.json --c RAG_TOOLS.json
        --questions FILE [FILE ...] --seed N [--out eval/results]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

from codecompass.eval.questions import load_question_set
from codecompass.online import NO_EVIDENCE, NO_INDEX

SLOTS = (("a", "no_retrieval"), ("b", "rag"), ("c", "rag_tools"))
CONDITIONS = ("codecompass", "repo", "index", "config", "embedder", "reranker", "generator",
              "server", "docs_fallback", "label", "question_files", "subset")
LABELS = ("abstention", "format_slip", "uncited", "h1", "h1_strict")
GRADERS = ("nicole", "kelsey")
GRADER_FIELDS = ("h2", "h3", "score", "reason")
SHEET_COLUMNS = ["row_id", "question_id", "category", "complexity", "set", "abstention",
                 "format_slip", "uncited", "h1", "file",
                 *[f"{g}_{f}" for g in GRADERS for f in GRADER_FIELDS]]
DEFAULT_OUT = Path("eval/results")

_SOURCES_HEADING = re.compile(r"(?mi)^\s*sources\s*:?\s*$")
_COULD_NOT = re.compile(r"could not (find|determine)", re.IGNORECASE)


def is_abstention(answer: str | None) -> bool:
    """A refusal to answer (AC-7.4); a pre-fill the grader confirms. None is an error."""
    if answer is None:
        return False
    if NO_EVIDENCE in answer or NO_INDEX in answer:
        return True
    return not _SOURCES_HEADING.search(answer) and bool(_COULD_NOT.search(answer))


def labels(row: dict) -> dict:
    """Deterministic labels for one result row; all None when the question errored."""
    if row.get("error") is not None or row.get("answer") is None:
        return dict.fromkeys(LABELS)
    abstained = is_abstention(row["answer"])
    sources = row.get("sources") or []
    unverified = set(row.get("unverified") or [])
    unreferenced = set(row.get("unreferenced") or [])
    flagged = row.get("citation_outcome") == "G"
    slip = (flagged and bool(sources) and bool(unverified) and unverified == unreferenced
            and not abstained)
    h1 = flagged and not abstained and bool(unverified) and not slip
    return {"abstention": abstained, "format_slip": slip,
            "uncited": not sources and not abstained, "h1": h1, "h1_strict": h1 or slip}


def citation_accuracy(rows: list[dict]) -> dict:
    """Verified Sources entries / all entries (micro average), and the share of F answers."""
    answered = [r for r in rows if r.get("error") is None and r.get("answer") is not None]
    entries = sum(len(r.get("sources") or []) for r in answered)
    verified = sum(bool(s.get("verified")) for r in answered for s in r.get("sources") or [])
    f = sum(r.get("citation_outcome") == "F" for r in answered)
    return {"entries": entries, "verified": verified,
            "accuracy": verified / entries if entries else None,
            "answers": len(answered), "f": f,
            "f_share": f / len(answered) if answered else None}


def summary(results: dict) -> dict:
    """Automatic counts for one run, over every question in it (AC-7.1, AC-9.1)."""
    rows = results["questions"]
    answered = [r for r in rows if r.get("error") is None and r.get("answer") is not None]
    marks = [labels(r) for r in answered]
    return {
        "mode": results["meta"].get("mode"),
        "n": len(answered),
        "errors": len(rows) - len(answered),
        "abstentions": sum(m["abstention"] for m in marks),
        "format_slips": sum(m["format_slip"] for m in marks),
        "uncited": sum(m["uncited"] for m in marks),
        "h1": sum(m["h1"] for m in marks),
        "h1_strict": sum(m["h1_strict"] for m in marks),
        "citation_accuracy": citation_accuracy(rows),
    }


def load_results(path) -> dict:
    """A results file, plain or gzip-compressed (.json.gz)."""
    path = Path(path)
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def make_sheet(results_a: dict, results_b: dict, results_c: dict, question_rows: list[dict],
               *, seed: int, out_dir) -> Path:
    """Write sheet.csv, rows/<row id>.md and key.json into *out_dir* (plan §3.6)."""
    runs = dict(zip((mode for _, mode in SLOTS), (results_a, results_b, results_c)))
    _check_runs(runs)
    questions = {q["id"]: q for q in question_rows}

    entries, skipped = [], []
    for mode, results in runs.items():
        for q in results["questions"]:
            if not q.get("in_subset"):
                continue
            if mode == "no_retrieval" and q["category"] == "unanswerable":
                continue  # (a) is graded for the contamination check: answerable only
            if q.get("error") is not None or q.get("answer") is None:
                skipped.append({"question_id": q["id"], "mode": mode, "error": q.get("error")})
                continue
            entries.append((mode, q))
    random.Random(seed).shuffle(entries)

    out_dir = Path(out_dir)
    (out_dir / "rows").mkdir(parents=True, exist_ok=True)
    key_rows, sheet = {}, []
    for n, (mode, q) in enumerate(entries, 1):
        row_id = f"R{n:02d}"
        file_name = f"{row_id}.md"
        marks = labels(q)
        contamination = mode == "no_retrieval"
        line = {"row_id": row_id, "question_id": q["id"], "category": q["category"],
                "complexity": q["complexity"], "set": q["set"],
                "abstention": _yes(marks["abstention"]),
                "format_slip": "n/a" if contamination else _yes(marks["format_slip"]),
                "uncited": _yes(marks["uncited"]),
                "h1": "n/a" if contamination else _yes(marks["h1"]),
                "file": file_name}
        for grader in GRADERS:
            line[f"{grader}_h2"] = "n/a" if contamination else ""
            line[f"{grader}_h3"] = ("n/a" if contamination or q["category"] != "unanswerable"
                                    else "")
            line[f"{grader}_score"] = ""
            line[f"{grader}_reason"] = ""
        sheet.append(line)
        key_rows[row_id] = {"question_id": q["id"], "mode": mode}
        reference = questions.get(q["id"], {})
        (out_dir / "rows" / file_name).write_text(_row_markdown(row_id, q, reference, line),
                                                  encoding="utf-8")

    with (out_dir / "sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(sheet)
    (out_dir / "key.json").write_text(
        json.dumps({"seed": seed, "rows": key_rows, "skipped": skipped}, indent=2),
        encoding="utf-8")
    return out_dir


def _check_runs(runs: dict) -> None:
    """Right run in each slot, and the same conditions in all three (AC-5.3)."""
    for slot, mode in SLOTS:
        got = runs[mode]["meta"].get("mode")
        if got != mode:
            raise ValueError(f"--{slot} must be a {mode!r} run, got {got!r}")
    base = runs["rag"]["meta"]
    for mode, results in runs.items():
        for key in CONDITIONS:
            if results["meta"].get(key) != base.get(key):
                raise ValueError(f"the {mode!r} run differs from the 'rag' run in {key!r}; "
                                 "runs under different conditions cannot be combined")


def _yes(value) -> str:
    return "yes" if value else "no"


def _row_markdown(row_id: str, q: dict, reference: dict, line: dict) -> str:
    """Everything a grader reads for one row. It never names the configuration."""
    out = [f"# {row_id}", "",
           f"- Question id: {q['id']}",
           f"- Category: {q['category']} | Tag: {q['complexity']} | Set: {q['set']}",
           f"- Pre-filled: abstention {line['abstention']}, format slip {line['format_slip']}, "
           f"uncited {line['uncited']}, H1 {line['h1']}",
           "", "## Question", "", reference.get("question", "(not found)"),
           "", "## Reference answer", "", reference.get("reference_answer", "(not found)"),
           "", "## Reference citations", ""]
    for c in reference.get("reference_citations") or []:
        out.append(f"- {c.get('path')}, lines {c.get('lines')}")
    out += ["", "## System answer (as shown to the user)", "", _fence(q["answer"]),
            "", f"## Citation check: outcome {q.get('citation_outcome')}", ""]
    for s in q.get("sources") or []:
        where = (f"commit {s.get('commit')}" if s.get("kind") == "commit"
                 else f"{s.get('path')}, lines {s.get('start_line')}-{s.get('end_line')}")
        out.append(f"- [{s.get('marker')}] {where}: "
                   f"{'verified' if s.get('verified') else 'NOT verified'}")
    out += ["", "## Full context sent to the generator", "",
            "(The system prompt left out: it is the same fixed text for every answer of a "
            "configuration, and would reveal which one.)", ""]
    for i, call in enumerate(q.get("messages") or [], 1):
        out += [f"### Call {i}", ""]
        for message in call.get("messages", []):
            if message.get("role") == "system":
                continue  # hides the configuration (AC-8.3)
            out += [f"#### {message.get('role')}", "", _fence(message.get("content", "")), ""]
        out += ["#### Generator output", "", _fence(call.get("output", "")), ""]
    return "\n".join(out) + "\n"


def _fence(text) -> str:
    return f"~~~~text\n{text}\n~~~~"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codecompass.eval.grading",
                                     description="Build the blind grading sheet and the "
                                                 "automatic counts (Spec 003 T5.6).")
    parser.add_argument("--a", required=True, type=Path, help="no_retrieval results file")
    parser.add_argument("--b", required=True, type=Path, help="rag results file")
    parser.add_argument("--c", required=True, type=Path, help="rag_tools results file")
    parser.add_argument("--questions", required=True, nargs="+", type=Path,
                        help="the frozen JSONL question files")
    parser.add_argument("--seed", required=True, type=int, help="shuffle seed")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="results directory")
    args = parser.parse_args(argv)
    try:
        runs = [load_results(p) for p in (args.a, args.b, args.c)]
        questions = [row for p in args.questions for row in load_question_set(p)]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder = make_sheet(*runs, questions, seed=args.seed,
                            out_dir=args.out / f"grading-{stamp}")
        counts = {r["meta"]["mode"]: summary(r) for r in runs}
        (folder / "summary.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - every failure becomes one error line
        print(f"error: {e}")
        return 1
    print(str(folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
