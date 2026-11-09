"""T6.2 report figures (tests-first).

Contract under test (Spec AC-4.x, AC-7.1, AC-9.1-9.6, AC-10.2, AC-10.3, AC-11.1;
Plan 003 §4.2, §4.4):
  codecompass.eval.report:
  - figures(merged, key, results, retrieval=None) -> dict, refusing (ValueError) an
    unsettled final cell or rows that do not match the key; `results` is the three run
    dicts in any order (matched by meta["mode"])
      hallucination / hallucination_strict: per mode (rag, rag_tools) "overall" and "by"
        category / complexity / set, each {"n", "hallucinated", "rate"}
      verification_gain: {"overall", "by"}: rate(rag) - rate(rag_tools)
      quality: per mode {"overall", "by"} with {"n", "mean", "counts"}
      paired: {"overall", "by_complexity"} with {"n", "better", "same", "worse",
               "fixed", "new"} ((c) vs (b) per question)
      contamination: {"core", "swe-qa"} {"n", "mean"}, "difference", "flagged" (>= 0.5)
      automatic: per mode, grading.summary(run)
      latency: per mode {"n", "median_total", "max_total", "median_stage"}
      hit_rates: the retrieval file's summary, or None
      failure_candidates: [{"row_id", "question_id", "mode", "why", "log_file"}]
  - write_report(report, out_dir) writes report.json, report.md, failure-candidates.md
  - main(["figures", --merged, --key, --results A B C, [--retrieval], --out DIR])
"""

from __future__ import annotations

import csv
import json

import pytest

from codecompass.eval import report as rp

MODES = ("rag", "rag_tools")


def _mrow(rid, qid, *, category="architectural", complexity="simple", set_="core",
          h1="no", slip="no", h2="no", h3="n/a", score="2", reason=""):
    """A settled row of sheet-merged.csv."""
    return {"row_id": rid, "question_id": qid, "category": category, "complexity": complexity,
            "set": set_, "abstention": "no", "format_slip": slip, "uncited": "no", "h1": h1,
            "file": f"{rid}.md", "agree": "yes", "final_h2": h2, "final_h3": h3,
            "final_score": score, "final_reason": reason, "note": ""}


def _fixture():
    """q0 code-tracing, q1 simple, q2 unanswerable (b, c); a-rows: 2 core, 2 swe-qa."""
    rows = [
        # rag (b)
        _mrow("R01", "q0", complexity="code-tracing", h2="yes", score="0", reason="unsupported"),
        _mrow("R02", "q1", score="1"),
        _mrow("R03", "q2", category="unanswerable", h3="yes", score="0", reason="unsupported"),
        # rag_tools (c)
        _mrow("R04", "q0", complexity="code-tracing", score="2"),
        _mrow("R05", "q1", h1="yes", score="1"),
        _mrow("R06", "q2", category="unanswerable", h3="no", score="2"),
        # no_retrieval (a): contamination rows
        _mrow("R07", "q0", h2="n/a", h3="n/a", slip="n/a", h1="n/a", score="1"),
        _mrow("R08", "q1", h2="n/a", h3="n/a", slip="n/a", h1="n/a", score="1"),
        _mrow("R09", "s0", set_="swe-qa", h2="n/a", h3="n/a", slip="n/a", h1="n/a", score="2"),
        _mrow("R10", "s1", set_="swe-qa", h2="n/a", h3="n/a", slip="n/a", h1="n/a",
              score="1"),
    ]
    modes = ["rag"] * 3 + ["rag_tools"] * 3 + ["no_retrieval"] * 4
    key = {"seed": 20261109, "skipped": [],
           "rows": {r["row_id"]: {"question_id": r["question_id"], "mode": m}
                    for r, m in zip(rows, modes)}}
    return rows, key


def _q(qid, *, total, error=None, outcome="F", sources=None, slip=False):
    sources = [{"marker": 1, "verified": not slip}] if sources is None else sources
    return {"id": qid, "set": "core", "category": "architectural", "complexity": "simple",
            "in_subset": True, "mode": "x",
            "answer": None if error else "A [1].\n\nSources\n[1] a.py, lines 1-2",
            "citation_outcome": None if error else outcome,
            "sources": None if error else sources,
            "unverified": None if error else ([1] if slip else []),
            "unreferenced": None if error else ([1] if slip else []),
            "timings": None if error else {"retrieval": 1.0, "generation": total - 1.0,
                                           "total": total},
            "log_file": f"/logs/{qid}.json", "error": error, "attempts": 1}


def _results():
    runs = []
    for mode, totals in (("no_retrieval", [2.0, 4.0]), ("rag", [5.0, 7.0, 9.0]),
                         ("rag_tools", [10.0, 20.0, 30.0])):
        qs = [_q(f"q{i}", total=t) for i, t in enumerate(totals)]
        runs.append({"meta": {"mode": mode}, "questions": qs})
    runs[2]["questions"].append(_q("q9", total=0, error={"type": "TimeoutError",
                                                         "message": "x"}))
    return runs


def _report(**kw):
    rows, key = _fixture()
    return rp.figures(rows, key, kw.pop("results", _results()), **kw)


# -- refusals -------------------------------------------------------------------------


def test_an_unsettled_final_cell_is_refused():
    rows, key = _fixture()
    rows[1]["final_score"] = ""
    with pytest.raises(ValueError, match="R02"):
        rp.figures(rows, key, _results())
    rows, key = _fixture()
    rows[0]["final_reason"] = ""          # a 0 needs its reason settled too
    with pytest.raises(ValueError, match="R01"):
        rp.figures(rows, key, _results())


def test_rows_that_do_not_match_the_key_are_refused():
    rows, key = _fixture()
    del key["rows"]["R10"]
    with pytest.raises(ValueError, match="key"):
        rp.figures(rows, key, _results())


# -- hallucination and Verification Gain (AC-9.1, AC-9.2) ----------------------------


def test_hallucination_rate_counts_h1_h2_or_h3_once_per_answer():
    h = _report()["hallucination"]
    assert h["rag"]["overall"] == {"n": 3, "hallucinated": 2, "rate": 2 / 3}       # H2, H3
    assert h["rag_tools"]["overall"] == {"n": 3, "hallucinated": 1, "rate": 1 / 3}  # H1


def test_unanswerable_counts_overall_and_as_its_own_group():
    h = _report()["hallucination"]["rag"]["by"]["category"]
    assert h["unanswerable"] == {"n": 1, "hallucinated": 1, "rate": 1.0}
    assert h["architectural"] == {"n": 2, "hallucinated": 1, "rate": 0.5}


def test_strict_h1_also_counts_format_slips():
    rows, key = _fixture()
    rows[4]["h1"], rows[4]["format_slip"] = "no", "yes"      # R05: a slip, not H1
    r = rp.figures(rows, key, _results())
    assert r["hallucination"]["rag_tools"]["overall"]["hallucinated"] == 0
    assert r["hallucination_strict"]["rag_tools"]["overall"]["hallucinated"] == 1


def test_verification_gain_is_rag_minus_rag_tools():
    vg = _report()["verification_gain"]
    assert vg["overall"] == pytest.approx(2 / 3 - 1 / 3)
    assert vg["by"]["complexity"]["code-tracing"] == pytest.approx(1.0 - 0.0)


def test_groups_cover_category_complexity_and_set():
    by = _report()["hallucination"]["rag"]["by"]
    assert set(by) == {"category", "complexity", "set"}
    assert by["set"]["core"]["n"] == 3


# -- quality and the paired comparison (AC-9.3, AC-9.4) ------------------------------


def test_quality_mean_and_counts():
    q = _report()["quality"]
    assert q["rag"]["overall"] == {"n": 3, "mean": pytest.approx(1 / 3),
                                   "counts": {"0": 2, "1": 1, "2": 0}}
    assert q["rag_tools"]["overall"]["mean"] == pytest.approx(5 / 3)


def test_paired_comparison_by_question_and_tag():
    p = _report()["paired"]
    assert p["overall"] == {"n": 3, "better": 2, "same": 1, "worse": 0, "fixed": 2, "new": 1}
    assert p["by_complexity"]["code-tracing"] == {"n": 1, "better": 1, "same": 0, "worse": 0,
                                                  "fixed": 1, "new": 0}


# -- contamination (AC-10.2, plan §4.4) ----------------------------------------------


def test_contamination_compares_core_and_swe_qa():
    c = _report()["contamination"]
    assert c["core"] == {"n": 2, "mean": 1.0}
    assert c["swe-qa"] == {"n": 2, "mean": 1.5}
    assert c["difference"] == pytest.approx(0.5)
    assert c["flagged"] is True                      # exactly 0.5 is flagged


def test_contamination_below_the_threshold_is_not_flagged():
    rows, key = _fixture()
    rows[8]["final_score"] = "1"                     # swe-qa now 1.0, core 1.0: difference 0
    r = rp.figures(rows, key, _results())
    assert r["contamination"]["difference"] == pytest.approx(0.0)
    assert r["contamination"]["flagged"] is False


# -- automatic counts, latency, hit rates (AC-7.1, AC-10.3, AC-11.1, AC-4.x) --------


def test_automatic_counts_come_from_every_question_in_each_run():
    auto = _report()["automatic"]
    assert set(auto) == {"no_retrieval", "rag", "rag_tools"}
    assert auto["rag_tools"]["n"] == 3 and auto["rag_tools"]["errors"] == 1
    assert auto["rag"]["citation_accuracy"]["accuracy"] == 1.0


def test_latency_median_max_and_stage_medians_without_errors():
    lat = _report()["latency"]
    assert lat["rag"] == {"n": 3, "median_total": 7.0, "max_total": 9.0,
                          "median_stage": {"retrieval": 1.0, "generation": 6.0}}
    assert lat["rag_tools"]["n"] == 3 and lat["rag_tools"]["max_total"] == 30.0


def test_results_are_matched_by_mode_not_by_order():
    assert _report(results=list(reversed(_results())))["latency"]["rag"]["median_total"] == 7.0


def test_hit_rates_are_copied_from_the_retrieval_file():
    retrieval = {"summary": {"setups": {"rrf": {"10": {"overall": {"n": 80}}}}}}
    assert _report(retrieval=retrieval)["hit_rates"] == retrieval["summary"]
    assert _report()["hit_rates"] is None


# -- failure candidates (AC-9.6) and output files ------------------------------------


def test_failure_candidates_are_the_h1_h2_h3_rows():
    cands = _report()["failure_candidates"]
    assert [(c["row_id"], c["mode"], c["why"]) for c in cands] == [
        ("R01", "rag", ["H2"]), ("R03", "rag", ["H3"]), ("R05", "rag_tools", ["H1"])]
    assert cands[0]["question_id"] == "q0" and cands[0]["log_file"] == "/logs/q0.json"


def test_write_report_writes_json_markdown_and_candidates(tmp_path):
    report = _report()
    rp.write_report(report, tmp_path / "out")
    data = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert data["verification_gain"]["overall"] == pytest.approx(1 / 3)
    md = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    for heading in ("Hallucination rate", "Verification Gain", "Quality", "Paired",
                    "Contamination", "Citation accuracy", "Latency"):
        assert heading in md
    assert "n = 3" in md or "n=3" in md
    assert "R01" in (tmp_path / "out" / "failure-candidates.md").read_text(encoding="utf-8")


def test_main_figures_writes_the_report(tmp_path, capsys):
    rows, key = _fixture()
    merged = tmp_path / "sheet-merged.csv"
    with merged.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (tmp_path / "key.json").write_text(json.dumps(key), encoding="utf-8")
    paths = []
    for run in _results():
        p = tmp_path / f"llm-{run['meta']['mode']}.json"
        p.write_text(json.dumps(run), encoding="utf-8")
        paths.append(str(p))
    out = tmp_path / "report"
    code = rp.main(["figures", "--merged", str(merged), "--key", str(tmp_path / "key.json"),
                    "--results", *paths, "--out", str(out)])
    assert code == 0
    assert capsys.readouterr().out.strip() == str(out)
    assert (out / "report.json").is_file() and (out / "report.md").is_file()


def test_main_figures_reports_an_error(tmp_path, capsys):
    code = rp.main(["figures", "--merged", str(tmp_path / "x.csv"), "--key",
                    str(tmp_path / "k.json"), "--results", "a", "b", "c",
                    "--out", str(tmp_path / "o")])
    assert code == 1 and capsys.readouterr().out.startswith("error:")
