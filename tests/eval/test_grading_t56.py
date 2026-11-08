"""T5.6 automatic labels and grading sheet tests (tests-first).

Contract under test (Spec AC-7.1-7.4, AC-8.1, AC-8.3, AC-8.5, AC-9.1, AC-10.1; Plan §3.6):
  codecompass.eval.grading:
  - is_abstention(answer) -> bool: NO_EVIDENCE / NO_INDEX, or no Sources section and
    "could not find" / "could not determine" (case-insensitive); None (an error) is not
  - labels(row) -> {"abstention", "format_slip", "uncited", "h1", "h1_strict"} for one
    result row of the LLM runner:
      format_slip: outcome G, sources present, set(unverified) == set(unreferenced) != {}
      uncited:     no sources, not an abstention (nothing fabricated, Article VI.3)
      h1:          outcome G, not an abstention, some unverified marker, not a slip
      h1_strict:   h1 or format_slip
    An errored row (answer None) has every label None.
  - citation_accuracy(rows) -> {"entries", "verified", "accuracy", "answers", "f", "f_share"}
    (micro average over Sources entries; errored rows left out; None when nothing to divide)
  - summary(results) -> per-run counts: n, errors, abstentions, format_slips, uncited, h1,
    h1_strict, plus citation_accuracy
  - load_results(path) reads .json or .json.gz
  - make_sheet(results_a, results_b, results_c, question_rows, *, seed, out_dir) -> Path:
      one row per subset question in (b) and (c), one per answerable subset question in (a);
      errored answers are skipped and listed in key.json; rows shuffled with `seed`;
      refuses results files whose run conditions differ (AC-5.3)
      writes sheet.csv, rows/<row id>.md and key.json
  - main(argv): --a --b --c FILE --questions FILE... --seed N --out DIR
"""

from __future__ import annotations

import copy
import csv
import gzip
import json
from pathlib import Path

import pytest

from codecompass.eval import grading as gr
from codecompass.online import NO_EVIDENCE, NO_INDEX

GRADER_COLUMNS = [f"{g}_{c}" for g in ("nicole", "kelsey") for c in ("h2", "h3", "score", "reason")]


# -- building blocks: runner-shaped result rows ---------------------------------------


def _src(marker, verified=True, path="src/flask/app.py"):
    return {"kind": "code", "marker": marker, "path": path, "start_line": 1, "end_line": 9,
            "commit": None, "subject": None, "author": None, "date": None,
            "verified": verified}


def _result(qid, *, outcome="F", sources=None, unverified=(), unreferenced=(),
            answer=None, error=None, category="architectural", in_subset=True,
            complexity="simple", set_="core"):
    sources = [_src(1)] if sources is None else sources
    if answer is None and error is None:
        answer = "Flask builds the app here [1].\n\nSources\n[1] src/flask/app.py, lines 1-9"
    failed = error is not None
    return {
        "id": qid, "set": set_, "category": category, "complexity": complexity,
        "in_subset": in_subset, "mode": None if failed else "rag",
        "answer": None if failed else answer,
        "raw_text": None if failed else answer,
        "citation_outcome": None if failed else outcome,
        "sources": None if failed else sources,
        "unverified": None if failed else list(unverified),
        "unreferenced": None if failed else list(unreferenced),
        "retrieved": [], "tool_calls": [], "round_limit_hit": False, "timings": {},
        "log_file": "/tmp/log.json",
        "messages": [] if failed else [
            {"messages": [{"role": "system", "content": "You answer questions."},
                          {"role": "user", "content": f"CONTEXT-FOR-{qid}\nQuestion?"}],
             "output": answer}],
        "error": error, "attempts": 2 if failed else 1,
    }


META = {"codecompass": {"commit": "c" * 40, "tag": "eval-v1", "dirty": False},
        "repo": {"path": "/r", "head_commit": "85c5d93"}, "index": {"indexed_commit": "85c5d93"},
        "config": {"sha256": "s"}, "embedder": {}, "reranker": {}, "generator": {"profile": "dev"},
        "server": {}, "host": {"hostname": "h"}, "docs_fallback": False, "label": "reported",
        "question_files": [], "subset": {"sha256": "x"}}


def _run(mode, rows):
    return {"meta": dict(copy.deepcopy(META), mode=mode), "questions": rows}


def _questions():
    rows = []
    for i, cat in enumerate(["architectural", "localisation", "unanswerable"]):
        rows.append({"id": f"q{i}", "set": "core", "category": cat, "complexity": "simple",
                     "question": f"Question {i}?", "reference_answer": f"Reference {i}.",
                     "reference_citations": [{"path": "src/flask/app.py", "lines": "1-9"}]})
    rows.append({"id": "q9", "set": "core", "category": "architectural",
                 "complexity": "simple", "question": "Not in the subset?",
                 "reference_answer": "r", "reference_citations": []})
    return rows


def _runs():
    def rows():
        return [_result("q0"), _result("q1", category="localisation"),
                _result("q2", category="unanswerable", sources=[], answer=NO_EVIDENCE,
                        outcome="G"),
                _result("q9", in_subset=False)]
    return _run("no_retrieval", rows()), _run("rag", rows()), _run("rag_tools", rows())


# -- abstention (AC-7.4) --------------------------------------------------------------


def test_pipeline_refusals_are_abstentions():
    assert gr.is_abstention(NO_EVIDENCE)
    assert gr.is_abstention(NO_EVIDENCE + "\n\nClosest matches found:\n- src/flask/app.py")
    assert gr.is_abstention(NO_INDEX + " Indexing failed: locked")


def test_could_not_find_without_sources_is_an_abstention():
    assert gr.is_abstention("I could not determine why from the code shown.")
    assert gr.is_abstention("I Could Not Find where that is configured.")


def test_an_answer_with_sources_is_not_an_abstention():
    assert not gr.is_abstention(
        "I could not find more, but it is here [1].\n\nSources\n[1] src/a.py, lines 1-2")
    assert not gr.is_abstention("Flask builds the app in app.py.")
    assert not gr.is_abstention(None)


# -- labels: slip, uncited, H1 (AC-7.2, AC-7.3) ---------------------------------------


def test_a_verified_answer_has_no_flags():
    assert gr.labels(_result("q")) == {"abstention": False, "format_slip": False,
                                       "uncited": False, "h1": False, "h1_strict": False}


def test_no_markers_at_all_is_a_slip_not_h1():
    row = _result("q", outcome="G", sources=[_src(1, False), _src(2, False)],
                  unverified=[1, 2], unreferenced=[1, 2])
    assert gr.labels(row) == {"abstention": False, "format_slip": True, "uncited": False,
                              "h1": False, "h1_strict": True}


def test_some_markers_missing_is_a_slip_not_h1():
    row = _result("q", outcome="G", sources=[_src(1), _src(2, False)],
                  unverified=[2], unreferenced=[2])
    labels = gr.labels(row)
    assert labels["format_slip"] and not labels["h1"] and labels["h1_strict"]


def test_an_entry_matching_nothing_is_h1_even_with_unreferenced_ones():
    row = _result("q", outcome="G", sources=[_src(1, False), _src(2, False)],
                  unverified=[1, 2], unreferenced=[2])
    labels = gr.labels(row)
    assert labels["h1"] and labels["h1_strict"] and not labels["format_slip"]


def test_a_marker_with_no_entry_is_h1():
    row = _result("q", outcome="G", sources=[_src(1)], unverified=[2], unreferenced=[])
    assert gr.labels(row)["h1"] is True


def test_an_answer_citing_nothing_is_uncited_not_h1():
    """Article VI.3: nothing was fabricated; graders judge its claims under H2."""
    row = _result("q", outcome="G", sources=[], answer="Flask builds the app in app.py.")
    assert gr.labels(row) == {"abstention": False, "format_slip": False, "uncited": True,
                              "h1": False, "h1_strict": False}


def test_an_abstention_is_never_h1():
    row = _result("q", outcome="G", sources=[], answer=NO_EVIDENCE)
    labels = gr.labels(row)
    assert labels["abstention"] and not labels["h1"] and not labels["h1_strict"]
    assert not labels["uncited"]


def test_an_errored_row_has_no_labels():
    row = _result("q", error={"type": "TimeoutError", "message": "x"})
    assert gr.labels(row) == dict.fromkeys(
        ("abstention", "format_slip", "uncited", "h1", "h1_strict"))


# -- citation accuracy and summary (AC-7.1, AC-9.1) -----------------------------------


def test_citation_accuracy_is_a_micro_average_over_entries():
    rows = [_result("a", sources=[_src(1), _src(2)]),
            _result("b", outcome="G", sources=[_src(1, False)], unverified=[1]),
            _result("c", outcome="G", sources=[], answer="no citations"),
            _result("d", error={"type": "E", "message": "x"})]
    acc = gr.citation_accuracy(rows)
    assert acc == {"entries": 3, "verified": 2, "accuracy": 2 / 3,
                   "answers": 3, "f": 1, "f_share": 1 / 3}


def test_citation_accuracy_with_nothing_to_divide_is_none():
    acc = gr.citation_accuracy([_result("a", error={"type": "E", "message": "x"})])
    assert acc["accuracy"] is None and acc["f_share"] is None


def test_summary_counts_each_label_and_leaves_errors_out():
    rows = [_result("a"),
            _result("b", outcome="G", sources=[_src(1, False)], unverified=[1],
                    unreferenced=[1]),
            _result("c", outcome="G", sources=[_src(1, False)], unverified=[1]),
            _result("d", outcome="G", sources=[], answer=NO_EVIDENCE),
            _result("e", outcome="G", sources=[], answer="Plain claim."),
            _result("f", error={"type": "E", "message": "x"})]
    s = gr.summary(_run("rag", rows))
    assert {k: s[k] for k in ("n", "errors", "abstentions", "format_slips", "uncited",
                              "h1", "h1_strict")} == {
        "n": 5, "errors": 1, "abstentions": 1, "format_slips": 1, "uncited": 1,
        "h1": 1, "h1_strict": 2}
    assert s["mode"] == "rag"
    assert s["citation_accuracy"]["entries"] == 3


# -- loading results ------------------------------------------------------------------


def test_load_results_reads_json_and_gzip(tmp_path):
    data = _run("rag", [_result("q0")])
    plain = tmp_path / "r.json"
    plain.write_text(json.dumps(data), encoding="utf-8")
    packed = tmp_path / "r.json.gz"
    with gzip.open(packed, "wt", encoding="utf-8") as fh:
        json.dump(data, fh)
    assert gr.load_results(plain) == gr.load_results(packed) == data


# -- the grading sheet (AC-8.1, AC-8.3, AC-8.5, AC-10.1) ------------------------------


def _sheet(tmp_path, runs=None, seed=7):
    a, b, c = runs or _runs()
    return gr.make_sheet(a, b, c, _questions(), seed=seed, out_dir=tmp_path / "grading")


def _read_csv(folder):
    with (folder / "sheet.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _key(folder):
    return json.loads((folder / "key.json").read_text(encoding="utf-8"))


def test_rows_cover_subset_in_b_and_c_and_answerable_subset_in_a(tmp_path):
    folder = _sheet(tmp_path)
    key = _key(folder)["rows"]
    pairs = sorted((v["question_id"], v["mode"]) for v in key.values())
    assert pairs == sorted([("q0", "no_retrieval"), ("q1", "no_retrieval"),
                            ("q0", "rag"), ("q1", "rag"), ("q2", "rag"),
                            ("q0", "rag_tools"), ("q1", "rag_tools"), ("q2", "rag_tools")])
    assert len(_read_csv(folder)) == 8


def test_sheet_columns_and_empty_grader_columns(tmp_path):
    """Graders fill every column; only H2/H3 that cannot apply are pre-filled n/a."""
    folder = _sheet(tmp_path)
    rows = _read_csv(folder)
    modes = {k: v["mode"] for k, v in _key(folder)["rows"].items()}
    assert list(rows[0]) == ["row_id", "question_id", "category", "complexity", "set",
                             "abstention", "format_slip", "uncited", "h1", "file",
                             *GRADER_COLUMNS]
    for r in rows:
        for col in GRADER_COLUMNS:
            if modes[r["row_id"]] == "no_retrieval" and col.endswith(("_h2", "_h3")):
                assert r[col] == "n/a", (r["row_id"], col)
            elif col.endswith("_h3") and r["category"] != "unanswerable":
                assert r[col] == "n/a", (r["row_id"], col)
            else:
                assert r[col] == "", (r["row_id"], col)


def test_no_retrieval_rows_have_no_h1_or_slip_label(tmp_path):
    folder = _sheet(tmp_path)
    modes = {k: v["mode"] for k, v in _key(folder)["rows"].items()}
    for r in _read_csv(folder):
        if modes[r["row_id"]] == "no_retrieval":
            assert (r["h1"], r["format_slip"]) == ("n/a", "n/a")
        else:
            assert r["h1"] in ("yes", "no") and r["format_slip"] in ("yes", "no")


def test_the_mode_is_hidden_from_the_sheet_and_row_files(tmp_path):
    folder = _sheet(tmp_path)
    texts = [(folder / "sheet.csv").read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in (folder / "rows").glob("*.md")]
    for text in texts:
        for word in ("no_retrieval", "rag_tools", '"rag"', "mode"):
            assert word not in text


def test_each_row_file_has_question_reference_answer_and_full_context(tmp_path):
    folder = _sheet(tmp_path)
    for r in _read_csv(folder):
        md = (folder / "rows" / r["file"]).read_text(encoding="utf-8")
        i = r["question_id"][1:]
        assert f"Question {i}?" in md and f"Reference {i}." in md
        assert "src/flask/app.py" in md
        assert f"CONTEXT-FOR-{r['question_id']}" in md


def test_row_files_leave_out_the_system_prompt(tmp_path):
    """The system prompt differs when tools are on, so it would reveal the configuration
    (AC-8.3); it is the same fixed text for every row of a mode, so graders lose nothing."""
    folder = _sheet(tmp_path)
    for p in (folder / "rows").glob("*.md"):
        md = p.read_text(encoding="utf-8")
        assert "You answer questions." not in md
        assert "#### system" not in md
        assert "system prompt left out" in md


def test_same_seed_same_order_other_seed_other_order(tmp_path):
    def order(folder):
        key = _key(folder)["rows"]
        return [(key[r["row_id"]]["question_id"], key[r["row_id"]]["mode"])
                for r in _read_csv(folder)]
    first = order(_sheet(tmp_path / "1", seed=7))
    assert order(_sheet(tmp_path / "2", seed=7)) == first
    assert any(order(_sheet(tmp_path / f"s{s}", seed=s)) != first for s in range(8, 14))
    assert [r["row_id"] for r in _read_csv(tmp_path / "1" / "grading")] == [
        f"R{n:02d}" for n in range(1, 9)]


def test_errored_answers_are_skipped_and_listed(tmp_path):
    a, b, c = _runs()
    c["questions"][0] = _result("q0", error={"type": "TimeoutError", "message": "x"})
    folder = _sheet(tmp_path, runs=(a, b, c))
    assert len(_read_csv(folder)) == 7
    assert _key(folder)["skipped"] == [{"question_id": "q0", "mode": "rag_tools",
                                        "error": {"type": "TimeoutError", "message": "x"}}]


def test_runs_under_different_conditions_are_refused(tmp_path):
    a, b, c = _runs()
    c["meta"]["codecompass"]["commit"] = "d" * 40
    with pytest.raises(ValueError, match="codecompass"):
        _sheet(tmp_path, runs=(a, b, c))


def test_runs_in_the_wrong_slot_are_refused(tmp_path):
    a, b, c = _runs()
    with pytest.raises(ValueError, match="rag_tools"):
        _sheet(tmp_path, runs=(a, c, b))


# -- command line ---------------------------------------------------------------------


def test_main_writes_the_sheet_and_a_summary(tmp_path, capsys):
    paths = {}
    for name, data in zip(("a", "b", "c"), _runs()):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data), encoding="utf-8")
    qfile = tmp_path / "q.jsonl"
    qfile.write_text("\n".join(json.dumps(r) for r in _questions()) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    code = gr.main(["--a", str(paths["a"]), "--b", str(paths["b"]), "--c", str(paths["c"]),
                    "--questions", str(qfile), "--seed", "7", "--out", str(out)])
    assert code == 0
    folder = Path(capsys.readouterr().out.strip())
    assert (folder / "sheet.csv").is_file() and (folder / "key.json").is_file()
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert set(summary) == {"no_retrieval", "rag", "rag_tools"}
    assert summary["rag"]["n"] == 4


def test_main_reports_an_error(tmp_path, capsys):
    code = gr.main(["--a", str(tmp_path / "x.json"), "--b", str(tmp_path / "y.json"),
                    "--c", str(tmp_path / "z.json"), "--questions", str(tmp_path / "q.jsonl"),
                    "--seed", "7", "--out", str(tmp_path / "out")])
    assert code == 1
    assert capsys.readouterr().out.startswith("error:")
