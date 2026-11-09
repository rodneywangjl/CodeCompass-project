"""Report figures from the graded sheets (Spec 003 AC-8.4, AC-9; Plan 003 §4).

Two steps, with people settling disagreements in between:

    python -m codecompass.eval.report merge --sheet DIR/sheet.csv \
        --nicole sheet-nicole.csv --kelsey sheet-kelsey.csv --out DIR/sheet-merged.csv

    python -m codecompass.eval.report figures --merged DIR/sheet-merged.csv --key DIR/key.json \
        --results NO_RETRIEVAL.json RAG.json RAG_TOOLS.json [--retrieval RETRIEVAL.json] --out DIR

``merge`` takes each grader's columns only from that grader's own copy, checks every value,
measures agreement (AC-8.4) and pre-fills the final columns where both agree. ``figures``
reads the settled final values and the key, and writes every report figure with its n
(AC-9). No significance tests (AC-9.5). Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from codecompass.eval.grading import (GRADER_FIELDS, GRADERS, SHEET_COLUMNS, load_results,
                                      summary)

NA = "n/a"
YES_NO = {"yes", "no"}
SCORES = {"0", "1", "2"}
REASONS = {"unsupported", "fabricated-citation", "abstained", "wrong-but-grounded"}
FINAL_COLUMNS = ["final_h2", "final_h3", "final_score", "final_reason", "note"]
MERGED_COLUMNS = [*SHEET_COLUMNS, "agree", *FINAL_COLUMNS]
GRADER_COLUMNS = {f"{g}_{f}" for g in GRADERS for f in GRADER_FIELDS}
PREFILLED = [c for c in SHEET_COLUMNS if c not in GRADER_COLUMNS]


def read_sheet(path) -> list[dict]:
    """A grading sheet (or a grader's copy, or a merged sheet) as a list of rows."""
    # utf-8-sig: Excel's "CSV UTF-8" starts the file with a byte-order mark, which would
    # otherwise become part of the first header ("﻿row_id")
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def merge(base: list[dict], nicole: list[dict], kelsey: list[dict]) -> list[dict]:
    """Both graders' columns, checked, with final columns pre-filled where they agree."""
    copies = {"nicole": nicole, "kelsey": kelsey}
    for grader, rows in copies.items():
        _check_same_rows(base, rows, grader)
    _check_nothing_empty(base, copies)

    merged = []
    for i, base_row in enumerate(base):
        row = {c: base_row.get(c, "") for c in SHEET_COLUMNS}
        for grader, rows in copies.items():
            row.update(_grades(base_row, rows[i], grader))
        merged.append(_with_final(row))
    return merged


def agreement(rows: list[dict]) -> dict:
    """Agreement between the two graders, per field, with n (AC-8.4, plan §4.4)."""
    def pairs(field, keep):
        return [(r[f"nicole_{field}"], r[f"kelsey_{field}"]) for r in rows if keep(r)]

    applies = {
        "score": lambda r: True,
        "h2": lambda r: r["nicole_h2"] != NA,
        "h3": lambda r: r["nicole_h3"] != NA,
        "reason": lambda r: r["nicole_score"] == "0" and r["kelsey_score"] == "0",
    }
    fields = {}
    for field, keep in applies.items():
        p = pairs(field, keep)
        agree = sum(a == b for a, b in p)
        fields[field] = {"n": len(p), "agree": agree, "share": agree / len(p) if p else None}
    kappa = {}
    for field in ("score", "h2"):
        p = pairs(field, applies[field])
        kappa[field] = {"n": len(p),
                        "kappa": cohen_kappa([a for a, _ in p], [b for _, b in p])}
    return {"fields": fields, "kappa": kappa,
            "disagreements": [r["row_id"] for r in rows if r.get("agree") == "no"]}


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters; None when undefined (no rows, or chance agreement 1)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    if abs(1 - expected) < 1e-12:
        return None
    return (observed - expected) / (1 - expected)


def _check_same_rows(base: list[dict], rows: list[dict], grader: str) -> None:
    ids = [r["row_id"] for r in base]
    got = [r.get("row_id") for r in rows]
    if got != ids:
        raise ValueError(f"the row ids in {grader}'s sheet do not match sheet.csv "
                         f"(expected {len(ids)} rows in the same order)")
    for base_row, row in zip(base, rows):
        for col in PREFILLED:
            if row.get(col, "") != base_row.get(col, ""):
                raise ValueError(f"{base_row['row_id']}: {grader} changed the pre-filled "
                                 f"column {col!r}")


def _check_nothing_empty(base: list[dict], copies: dict) -> None:
    for grader, rows in copies.items():
        empty = []
        for base_row, row in zip(base, rows):
            for field in ("h2", "h3", "score"):
                col = f"{grader}_{field}"
                if base_row[col] != NA and not row.get(col, "").strip():
                    empty.append(base_row["row_id"])
                    break
        if empty:
            raise ValueError(f"{grader} has not graded rows {', '.join(empty)}")


def _grades(base_row: dict, row: dict, grader: str) -> dict:
    rid = base_row["row_id"]
    values = {}
    for field in GRADER_FIELDS:
        col = f"{grader}_{field}"
        value = row.get(col, "").strip().lower()
        if base_row[col] == NA:
            if value != NA:
                raise ValueError(f"{rid}: {col} must stay {NA!r}, got {value!r}")
        elif field in ("h2", "h3") and value not in YES_NO:
            raise ValueError(f"{rid}: {col} must be yes or no, got {value!r}")
        elif field == "score" and value not in SCORES:
            raise ValueError(f"{rid}: {col} must be 0, 1 or 2, got {value!r}")
        values[col] = value
    reason, score = values[f"{grader}_reason"], values[f"{grader}_score"]
    if score == "0" and reason not in REASONS:
        raise ValueError(f"{rid}: a score of 0 needs a reason ({', '.join(sorted(REASONS))}), "
                         f"got {reason!r}")
    if score != "0" and reason:
        raise ValueError(f"{rid}: {grader} gave a reason for a score of {score}; only a 0 has one")
    if "yes" in (values[f"{grader}_h2"], values[f"{grader}_h3"]) and score != "0":
        raise ValueError(f"{rid}: {grader} marked H2 or H3 yes, so the score must be 0 (§5.2)")
    return values


def _with_final(row: dict) -> dict:
    agree = True
    for field in GRADER_FIELDS:
        a, b = row[f"nicole_{field}"], row[f"kelsey_{field}"]
        if a == b:
            row[f"final_{field}"] = a
        else:
            row[f"final_{field}"] = ""
            agree = False
    row["agree"] = "yes" if agree else "no"
    row["note"] = ""
    return {c: row[c] for c in MERGED_COLUMNS}


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


# -- figures (plan §4.2) -----------------------------------------------------------------

MODES = ("no_retrieval", "rag", "rag_tools")
COMPARED = ("rag", "rag_tools")  # (b) and (c): hallucination and Verification Gain
GROUPS = ("category", "complexity", "set")
CONTAMINATION_FLAG = 0.5  # plan §4.4: fixed on 2026-11-09, before anyone saw the results


def figures(merged: list[dict], key: dict, results: list[dict], retrieval: dict | None = None
            ) -> dict:
    """Every report figure, each with its n, from the settled sheet (plan §4.2)."""
    _check_settled(merged, key)
    runs = {r["meta"].get("mode"): r for r in results}
    missing = [m for m in MODES if m not in runs]
    if missing:
        raise ValueError(f"results files missing for: {', '.join(missing)}")
    rows = [dict(r, mode=key["rows"][r["row_id"]]["mode"]) for r in merged]
    by_mode = {m: [r for r in rows if r["mode"] == m] for m in MODES}

    def hallucinated(strict):
        # strict also counts format slips, except a slip the graders settled as an abstention:
        # an abstention is never hallucinated (§5.2, AC-7.2, AC-7.4)
        return lambda r: (r["h1"] == "yes" or r["final_h2"] == "yes" or r["final_h3"] == "yes"
                          or (strict and r["format_slip"] == "yes"
                              and r["final_reason"] != "abstained"))

    hall = {m: _grouped(by_mode[m], _rate(hallucinated(False))) for m in COMPARED}
    strict = {m: _grouped(by_mode[m], _rate(hallucinated(True))) for m in COMPARED}
    return {
        "hallucination": hall,
        "hallucination_strict": strict,
        "verification_gain": _gain(hall["rag"], hall["rag_tools"]),
        "quality": {m: _grouped(by_mode[m], _quality) for m in COMPARED},
        "paired": _paired(by_mode["rag"], by_mode["rag_tools"], hallucinated(False)),
        "contamination": _contamination(by_mode["no_retrieval"]),
        "automatic": {m: summary(runs[m]) for m in MODES},
        "latency": {m: _latency(runs[m]) for m in MODES},
        "hit_rates": retrieval.get("summary") if retrieval else None,
        "failure_candidates": _candidates(rows, runs),
        "skipped": key.get("skipped", []),
        "meta": {m: runs[m].get("meta", {}) for m in MODES},
    }


def write_report(report: dict, out_dir) -> Path:
    """report.json, report.md (tables for the slides) and failure-candidates.md."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(_markdown(report), encoding="utf-8")
    lines = ["# Failure-example candidates (AC-9.6)", "",
             "Rows with H1, H2 or H3. Choose 3-5 by hand for the report.", "",
             "| Row | Question | Configuration | Why | Audit log |", "|---|---|---|---|---|"]
    lines += [f"| {c['row_id']} | {c['question_id']} | {c['mode']} | {', '.join(c['why'])} | "
              f"{c['log_file']} |" for c in report["failure_candidates"]]
    (out / "failure-candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _check_settled(merged: list[dict], key: dict) -> None:
    ids = [r["row_id"] for r in merged]
    if set(ids) != set(key.get("rows", {})) or len(ids) != len(set(ids)):
        raise ValueError("the merged sheet's rows do not match key.json")
    for r in merged:
        for col in ("final_h2", "final_h3", "final_score"):
            if not r.get(col, "").strip():
                raise ValueError(f"{r['row_id']}: {col} is not settled yet")
        if r["final_score"] == "0" and not r.get("final_reason", "").strip():
            raise ValueError(f"{r['row_id']}: final_reason is not settled yet")


def _rate(pred):
    def stats(rows):
        hit = sum(1 for r in rows if pred(r))
        return {"n": len(rows), "hallucinated": hit, "rate": hit / len(rows) if rows else None}
    return stats


def _quality(rows):
    scores = [int(r["final_score"]) for r in rows]
    return {"n": len(scores), "mean": sum(scores) / len(scores) if scores else None,
            "counts": {s: sum(1 for x in scores if str(x) == s) for s in ("0", "1", "2")}}


def _grouped(rows, stats):
    return {"overall": stats(rows),
            "by": {g: {v: stats([r for r in rows if r[g] == v])
                       for v in sorted({r[g] for r in rows})} for g in GROUPS}}


def _gain(b, c):
    def diff(x, y):
        return None if x is None or y is None else x["rate"] - y["rate"] \
            if x["rate"] is not None and y["rate"] is not None else None
    by = {}
    for g in GROUPS:
        values = sorted(set(b["by"][g]) | set(c["by"][g]))
        by[g] = {v: diff(b["by"][g].get(v), c["by"][g].get(v)) for v in values}
    return {"overall": diff(b["overall"], c["overall"]), "by": by}


def _paired(b_rows, c_rows, hallucinated):
    b = {r["question_id"]: r for r in b_rows}
    c = {r["question_id"]: r for r in c_rows}

    def tally(qids):
        t = {"n": 0, "better": 0, "same": 0, "worse": 0, "fixed": 0, "new": 0}
        for q in qids:
            sb, sc = int(b[q]["final_score"]), int(c[q]["final_score"])
            t["n"] += 1
            t["better" if sc > sb else "worse" if sc < sb else "same"] += 1
            hb, hc = hallucinated(b[q]), hallucinated(c[q])
            t["fixed"] += hb and not hc
            t["new"] += hc and not hb
        return t

    common = [q for q in b if q in c]
    tags = sorted({b[q]["complexity"] for q in common})
    return {"overall": tally(common),
            "by_complexity": {t: tally([q for q in common if b[q]["complexity"] == t])
                              for t in tags}}


def _contamination(a_rows):
    def mean(set_):
        scores = [int(r["final_score"]) for r in a_rows if r["set"] == set_]
        return {"n": len(scores), "mean": sum(scores) / len(scores) if scores else None}
    core, swe = mean("core"), mean("swe-qa")
    diff = (swe["mean"] - core["mean"]
            if core["mean"] is not None and swe["mean"] is not None else None)
    return {"core": core, "swe-qa": swe, "difference": diff,
            "flagged": diff is not None and diff >= CONTAMINATION_FLAG - 1e-9,
            "threshold": CONTAMINATION_FLAG}


def _latency(run):
    done = [q for q in run["questions"] if q.get("error") is None and q.get("timings")]
    totals = [q["timings"]["total"] for q in done if "total" in q["timings"]]
    stages = sorted({s for q in done for s in q["timings"] if s != "total"})
    return {"n": len(totals),
            "median_total": statistics.median(totals) if totals else None,
            "max_total": max(totals) if totals else None,
            "median_stage": {s: statistics.median([q["timings"][s] for q in done
                                                   if s in q["timings"]]) for s in stages}}


def _candidates(rows, runs):
    out = []
    for r in rows:
        why = [label for label, hit in (("H1", r["h1"] == "yes"), ("H2", r["final_h2"] == "yes"),
                                        ("H3", r["final_h3"] == "yes")) if hit]
        if not why:
            continue
        log = next((q.get("log_file") for q in runs[r["mode"]]["questions"]
                    if q["id"] == r["question_id"]), None)
        out.append({"row_id": r["row_id"], "question_id": r["question_id"], "mode": r["mode"],
                    "why": why, "log_file": log})
    return out


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def _num(x, digits=2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _markdown(rep: dict) -> str:
    out = ["# Evaluation report (Spec 003)", "",
           "Every figure states its n. No significance tests (AC-9.5).", ""]
    out += ["## Hallucination rate (AC-9.1)", "",
            "Hallucinated = H1 or H2 or H3. Abstentions count in n; errors are left out.", "",
            "| Group | rag | rag_tools | strict (slips as H1): rag | rag_tools |",
            "|---|---|---|---|---|"]
    h, s = rep["hallucination"], rep["hallucination_strict"]

    def cell(st):
        return f"{_pct(st['rate'])} ({st['hallucinated']}/{st['n']}), n = {st['n']}"
    out.append(f"| overall | {cell(h['rag']['overall'])} | {cell(h['rag_tools']['overall'])} | "
               f"{cell(s['rag']['overall'])} | {cell(s['rag_tools']['overall'])} |")
    for g in GROUPS:
        for v in sorted(set(h["rag"]["by"][g]) | set(h["rag_tools"]["by"][g])):
            cells = [cell(x["by"][g][v]) if v in x["by"][g] else "—"
                     for x in (h["rag"], h["rag_tools"], s["rag"], s["rag_tools"])]
            out.append(f"| {g}: {v} | " + " | ".join(cells) + " |")
    vg = rep["verification_gain"]
    out += ["", "## Verification Gain (AC-9.2)", "",
            "rate(rag) − rate(rag_tools); positive means the tools help.", "",
            "| Group | Verification Gain |", "|---|---|", f"| overall | {_num(vg['overall'])} |"]
    out += [f"| {g}: {v} | {_num(x)} |" for g in GROUPS for v, x in vg["by"][g].items()]
    out += ["", "## Quality (AC-9.3)", "", "| Group | rag mean (0/1/2) | rag_tools mean (0/1/2) |",
            "|---|---|---|"]
    q = rep["quality"]

    def qcell(st):
        c = st["counts"]
        return f"{_num(st['mean'])} ({c['0']}/{c['1']}/{c['2']}), n = {st['n']}"
    out.append(f"| overall | {qcell(q['rag']['overall'])} | {qcell(q['rag_tools']['overall'])} |")
    for g in GROUPS:
        for v in sorted(set(q["rag"]["by"][g]) | set(q["rag_tools"]["by"][g])):
            cells = [qcell(x["by"][g][v]) if v in x["by"][g] else "—"
                     for x in (q["rag"], q["rag_tools"])]
            out.append(f"| {g}: {v} | " + " | ".join(cells) + " |")
    p = rep["paired"]
    out += ["", "## Paired comparison, rag_tools vs rag (AC-9.4)", "",
            "| Group | n | better | same | worse | hallucination fixed | new |",
            "|---|---|---|---|---|---|---|"]
    for name, t in [("overall", p["overall"]), *p["by_complexity"].items()]:
        out.append(f"| {name} | n = {t['n']} | {t['better']} | {t['same']} | {t['worse']} | "
                   f"{t['fixed']} | {t['new']} |")
    c = rep["contamination"]
    out += ["", "## Contamination check, no_retrieval (AC-10.2)", "",
            f"- core: mean {_num(c['core']['mean'])}, n = {c['core']['n']}",
            f"- swe-qa: mean {_num(c['swe-qa']['mean'])}, n = {c['swe-qa']['n']}",
            f"- difference (swe-qa − core): {_num(c['difference'])}; flagged at ≥ "
            f"{c['threshold']} (fixed before the results): **{'yes' if c['flagged'] else 'no'}**",
            "- The two sets differ in style and difficulty, so a gap suggests memorisation but "
            "does not prove it."]
    out += ["", "## Citation accuracy and automatic labels, all questions (AC-7.1, AC-10.3)", "",
            "| Configuration | n | errors | accuracy (verified/entries) | F share | abstentions | "
            "format slips | uncited | H1 | strict H1 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m, a in rep["automatic"].items():
        ca = a["citation_accuracy"]
        out.append(f"| {m} | n = {a['n']} | {a['errors']} | {_pct(ca['accuracy'])} "
                   f"({ca['verified']}/{ca['entries']}) | {_pct(ca['f_share'])} | "
                   f"{a['abstentions']} | {a['format_slips']} | {a['uncited']} | {a['h1']} | "
                   f"{a['h1_strict']} |")
    out += ["", "## Latency (AC-11.1)", "",
            "| Configuration | n | median total (s) | max total (s) | median per stage (s) |",
            "|---|---|---|---|---|"]
    for m, lat in rep["latency"].items():
        stages = ", ".join(f"{k} {_num(v)}" for k, v in lat["median_stage"].items())
        out.append(f"| {m} | n = {lat['n']} | {_num(lat['median_total'])} | "
                   f"{_num(lat['max_total'])} | {stages} |")
    if rep.get("hit_rates") is not None:
        out += ["", "## Hit rate@k (AC-4.x)", "", "See `report.json` → `hit_rates` "
                "(copied from the retrieval results file, with n)."]
    if rep.get("skipped"):
        out += ["", f"Skipped (errored) answers, left out of the graded figures: "
                f"{len(rep['skipped'])}."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codecompass.eval.report",
                                     description="Report figures from the graded sheets "
                                                 "(Spec 003 S6).")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge", help="merge the two graders' copies and measure agreement")
    m.add_argument("--sheet", required=True, type=Path, help="the original sheet.csv")
    m.add_argument("--nicole", required=True, type=Path, help="Nicole's graded copy")
    m.add_argument("--kelsey", required=True, type=Path, help="Kelsey's graded copy")
    m.add_argument("--out", required=True, type=Path, help="merged sheet to write")
    f = sub.add_parser("figures", help="compute the report figures from the settled sheet")
    f.add_argument("--merged", required=True, type=Path, help="the settled sheet-merged.csv")
    f.add_argument("--key", required=True, type=Path, help="key.json from the grading folder")
    f.add_argument("--results", required=True, nargs=3, type=Path,
                   help="the three LLM results files (any order)")
    f.add_argument("--retrieval", type=Path, default=None, help="retrieval results file")
    f.add_argument("--out", required=True, type=Path, help="report folder to write")
    args = parser.parse_args(argv)
    try:
        if args.command == "merge":
            merged = merge(read_sheet(args.sheet), read_sheet(args.nicole),
                           read_sheet(args.kelsey))
            _write_csv(args.out, merged, MERGED_COLUMNS)
            (args.out.parent / "agreement.json").write_text(
                json.dumps(agreement(merged), indent=2), encoding="utf-8")
        else:
            key = json.loads(args.key.read_text(encoding="utf-8"))
            runs = [load_results(p) for p in args.results]
            retrieval = load_results(args.retrieval) if args.retrieval else None
            write_report(figures(read_sheet(args.merged), key, runs, retrieval), args.out)
    except Exception as e:  # noqa: BLE001 - every failure becomes one error line
        print(f"error: {e}")
        return 1
    print(str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
