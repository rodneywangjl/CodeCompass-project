"""Grading subset: which questions are graded by hand (Spec 003 AC-5.1, AC-10.1; Plan §3.3).

All questions run in every configuration; only this subset is graded. The rule picks by
``sha256(id)`` so that nobody chooses the questions and there is no seed to re-try:

* in each answerable category, one ``simple`` and one ``code-tracing`` question from
  ``core`` and the same from ``swe-qa``, each the first of its group in sha256 order; if a
  group is empty, the next question in sha256 order from the same category and set;
* the first 4 core unanswerable questions in sha256 order.

Usage:
    python -m codecompass.eval.subset FILE [FILE ...] --out eval/questions/grading-subset.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from codecompass.eval.questions import load_question_set

RULE = "plan 003 §3.3"
UNANSWERABLE = "unanswerable"
SETS = ("core", "swe-qa")
TAGS = ("simple", "code-tracing")
PER_SET = len(TAGS)
UNANSWERABLE_PICKS = 4


def _order(qid: str) -> str:
    return hashlib.sha256(qid.encode("utf-8")).hexdigest()


def select_subset(rows: list[dict]) -> list[str]:
    """The grading subset's question ids, sorted (plan §3.3)."""
    chosen: list[str] = []
    categories = sorted({r["category"] for r in rows} - {UNANSWERABLE})
    for category in categories:
        for set_ in SETS:
            pool = sorted((r for r in rows if r["category"] == category and r["set"] == set_),
                          key=lambda r: _order(r["id"]))
            picks: list[str] = []
            for tag in TAGS:
                first = next((r["id"] for r in pool if r["complexity"] == tag), None)
                if first is not None:
                    picks.append(first)
            for r in pool:  # fallback for an empty group: next in sha256 order
                if len(picks) >= PER_SET:
                    break
                if r["id"] not in picks:
                    picks.append(r["id"])
            chosen.extend(picks)
    unanswerable = sorted((r["id"] for r in rows
                           if r["category"] == UNANSWERABLE and r["set"] == "core"), key=_order)
    chosen.extend(unanswerable[:UNANSWERABLE_PICKS])
    return sorted(chosen)


def file_sha256(path: Path) -> str:
    """SHA-256 with line endings normalised to LF, so Windows and Linux checkouts agree."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codecompass.eval.subset",
                                     description="Choose the grading subset (Spec 003 T5.3).")
    parser.add_argument("files", nargs="+", type=Path, help="JSONL question files")
    parser.add_argument("--out", required=True, type=Path, help="subset file to write")
    args = parser.parse_args(argv)
    try:
        rows = [row for path in args.files for row in load_question_set(path)]
    except (OSError, ValueError) as e:
        print(f"error: {e}")
        return 1
    ids = select_subset(rows)
    data = {
        "rule": RULE,
        "question_files": [{"path": p.as_posix(), "sha256": file_sha256(p)} for p in args.files],
        "ids": ids,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    by_id = {r["id"]: r for r in rows}
    counts = Counter((by_id[i]["category"], by_id[i]["complexity"]) for i in ids)
    for (category, tag), n in sorted(counts.items()):
        print(f"{category:20} {tag:13} {n}")
    print(f"{len(ids)} questions chosen; written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
