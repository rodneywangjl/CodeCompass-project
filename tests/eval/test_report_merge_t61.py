"""T6.1 merge the two graders' sheets and measure agreement (tests-first).

Contract under test (Spec AC-8.4, §5.1-5.2; Plan 003 §4.1, §4.4):
  codecompass.eval.report:
  - read_sheet(path) -> list[dict]
  - merge(base, nicole, kelsey) -> list[dict]: base row order and columns; nicole_* only from
    nicole's file, kelsey_* only from kelsey's; refuses (ValueError naming the row) a changed
    row id or pre-filled cell, an empty grader cell, an n/a cell changed, a bad value, a 0
    without a reason (or a reason on a non-zero score), and H2/H3 "yes" with a non-zero score.
    Adds "agree" and final_h2, final_h3, final_score, final_reason, note; each final cell is
    filled where both graders agree on that field, n/a where it does not apply, else empty.
  - agreement(rows) -> {"fields": {field: {"n", "agree", "share"}}, "kappa": {"score", "h2"},
    "disagreements": [row ids]}; reason is compared only where both gave a 0
  - cohen_kappa(a, b) -> float | None (None when undefined)
  - main(["merge", --sheet, --nicole, --kelsey, --out]) writes the merged CSV and
    agreement.json next to it, prints the CSV path; "error: ..." and 1 on failure
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from codecompass.eval import report as rp
from codecompass.eval.grading import SHEET_COLUMNS

FINAL = ["final_h2", "final_h3", "final_score", "final_reason", "note"]


def _base_rows():
    """R01 answerable (b/c), R02 unanswerable (b/c), R03 contamination row from (a), R04."""
    def row(rid, qid, category, h2, h3):
        r = {"row_id": rid, "question_id": qid, "category": category, "complexity": "simple",
             "set": "core", "abstention": "no", "format_slip": "no", "uncited": "no",
             "h1": "no", "file": f"{rid}.md"}
        for g in ("nicole", "kelsey"):
            r.update({f"{g}_h2": h2, f"{g}_h3": h3, f"{g}_score": "", f"{g}_reason": ""})
        return r
    rows = [row("R01", "q0", "architectural", "", "n/a"),
            row("R02", "q2", "unanswerable", "", ""),
            row("R03", "q0", "architectural", "n/a", "n/a"),
            row("R04", "q1", "localisation", "", "n/a")]
    rows[2].update(format_slip="n/a", h1="n/a")
    return rows


NICOLE = {"R01": ("no", "n/a", "2", ""), "R02": ("no", "no", "2", ""),
          "R03": ("n/a", "n/a", "1", ""), "R04": ("yes", "n/a", "0", "unsupported")}
KELSEY = {"R01": ("no", "n/a", "1", ""), "R02": ("no", "no", "2", ""),
          "R03": ("n/a", "n/a", "1", ""), "R04": ("yes", "n/a", "0", "fabricated-citation")}


def _filled(grades: dict, who: str, *, also_other: dict | None = None, other: str = ""):
    rows = _base_rows()
    for r in rows:
        h2, h3, score, reason = grades[r["row_id"]]
        r.update({f"{who}_h2": h2, f"{who}_h3": h3, f"{who}_score": score,
                  f"{who}_reason": reason})
        if also_other:
            o = also_other[r["row_id"]]
            r.update({f"{other}_h2": o[0], f"{other}_h3": o[1], f"{other}_score": o[2],
                      f"{other}_reason": o[3]})
    return rows


def _write(path: Path, rows) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def _merge(nicole=None, kelsey=None):
    return rp.merge(_base_rows(), nicole or _filled(NICOLE, "nicole"),
                    kelsey or _filled(KELSEY, "kelsey"))


# -- reading --------------------------------------------------------------------------


def test_read_sheet_round_trips_a_grading_sheet(tmp_path):
    rows = rp.read_sheet(_write(tmp_path / "sheet.csv", _base_rows()))
    assert rows == _base_rows()


def test_read_sheet_accepts_a_byte_order_mark(tmp_path):
    """Excel's "CSV UTF-8" adds a BOM; the first header must still read as row_id
    (bug found in review of #53: merge failed with "row ids do not match")."""
    plain = _write(tmp_path / "sheet.csv", _base_rows())
    excel = tmp_path / "sheet-excel.csv"
    excel.write_bytes(b"\xef\xbb\xbf" + plain.read_bytes())
    rows = rp.read_sheet(excel)
    assert list(rows[0])[0] == "row_id"
    assert rows == _base_rows()
    nic = tmp_path / "sheet-nicole.csv"
    nic.write_bytes(b"\xef\xbb\xbf" + _write(tmp_path / "n.csv",
                                             _filled(NICOLE, "nicole")).read_bytes())
    merged = rp.merge(_base_rows(), rp.read_sheet(nic), _filled(KELSEY, "kelsey"))
    assert [r["row_id"] for r in merged] == ["R01", "R02", "R03", "R04"]


# -- each grader's columns only from their own file -----------------------------------


def test_each_graders_columns_come_only_from_their_own_file():
    sneaky = _filled(KELSEY, "kelsey", also_other={k: ("yes", "yes", "0", "unsupported")
                                                    for k in KELSEY}, other="nicole")
    merged = _merge(kelsey=sneaky)
    assert [r["nicole_score"] for r in merged] == ["2", "2", "1", "0"]
    assert [r["kelsey_score"] for r in merged] == ["1", "2", "1", "0"]
    assert [r["row_id"] for r in merged] == ["R01", "R02", "R03", "R04"]


# -- refusals -------------------------------------------------------------------------


def test_a_changed_prefilled_cell_is_refused():
    bad = _filled(NICOLE, "nicole")
    bad[1]["h1"] = "yes"
    with pytest.raises(ValueError, match="R02"):
        _merge(nicole=bad)


def test_a_missing_or_reordered_row_is_refused():
    bad = _filled(NICOLE, "nicole")
    with pytest.raises(ValueError, match="row"):
        _merge(nicole=bad[:3])
    with pytest.raises(ValueError, match="row"):
        _merge(nicole=[bad[1], bad[0], bad[2], bad[3]])


def test_an_empty_grader_cell_is_refused_with_its_row():
    bad = _filled(KELSEY, "kelsey")
    bad[3]["kelsey_score"] = ""
    with pytest.raises(ValueError, match="R04"):
        _merge(kelsey=bad)


def test_an_na_cell_must_stay_na():
    bad = _filled(NICOLE, "nicole")
    bad[2]["nicole_h2"] = "no"  # R03 is a contamination row: H2 does not apply
    with pytest.raises(ValueError, match="R03"):
        _merge(nicole=bad)


@pytest.mark.parametrize("field,value", [("h2", "maybe"), ("score", "3"), ("score", "1.5"),
                                         ("reason", "lazy")])
def test_an_invalid_value_is_refused(field, value):
    bad = _filled(NICOLE, "nicole")
    bad[3][f"nicole_{field}"] = value
    with pytest.raises(ValueError, match="R04"):
        _merge(nicole=bad)


def test_a_zero_needs_a_reason_and_a_non_zero_has_none():
    no_reason = _filled(NICOLE, "nicole")
    no_reason[3]["nicole_reason"] = ""
    with pytest.raises(ValueError, match="R04"):
        _merge(nicole=no_reason)
    stray = _filled(NICOLE, "nicole")
    stray[0]["nicole_reason"] = "unsupported"
    with pytest.raises(ValueError, match="R01"):
        _merge(nicole=stray)


def test_h2_or_h3_yes_requires_score_zero():
    bad = _filled(NICOLE, "nicole")
    bad[0]["nicole_h2"] = "yes"  # score stays 2
    with pytest.raises(ValueError, match="R01"):
        _merge(nicole=bad)
    bad = _filled(NICOLE, "nicole")
    bad[1]["nicole_h3"] = "yes"  # unanswerable, score stays 2
    with pytest.raises(ValueError, match="R02"):
        _merge(nicole=bad)


def test_values_are_read_case_and_space_insensitively():
    loose = _filled(NICOLE, "nicole")
    loose[3].update(nicole_h2=" Yes ", nicole_reason=" Unsupported")
    merged = _merge(nicole=loose)
    assert merged[3]["nicole_h2"] == "yes" and merged[3]["nicole_reason"] == "unsupported"


# -- final columns --------------------------------------------------------------------


def test_final_cells_are_prefilled_only_where_both_agree():
    merged = _merge()
    assert list(merged[0]) == [*SHEET_COLUMNS, "agree", *FINAL]
    r01, r02, r03, r04 = merged
    assert (r01["agree"], r01["final_score"], r01["final_h2"], r01["final_h3"]) == (
        "no", "", "no", "n/a")                       # scores differ, H2 agrees
    assert (r02["agree"], r02["final_score"], r02["final_h2"], r02["final_h3"],
            r02["final_reason"]) == ("yes", "2", "no", "no", "")
    assert (r03["agree"], r03["final_h2"], r03["final_h3"], r03["final_score"]) == (
        "yes", "n/a", "n/a", "1")
    assert (r04["agree"], r04["final_score"], r04["final_h2"], r04["final_reason"]) == (
        "no", "0", "yes", "")                        # both 0, reasons differ
    assert all(r["note"] == "" for r in merged)


# -- agreement (AC-8.4, plan §4.4) ----------------------------------------------------


def test_agreement_shares_with_n():
    a = rp.agreement(_merge())
    assert a["fields"]["score"] == {"n": 4, "agree": 3, "share": 3 / 4}
    assert a["fields"]["h2"] == {"n": 3, "agree": 3, "share": 1.0}     # R03 is n/a
    assert a["fields"]["h3"] == {"n": 1, "agree": 1, "share": 1.0}     # unanswerable only
    assert a["fields"]["reason"] == {"n": 1, "agree": 0, "share": 0.0}  # both gave 0: R04
    assert a["disagreements"] == ["R01", "R04"]


def test_agreement_with_nothing_to_compare_is_none():
    rows = [r for r in _merge() if r["row_id"] != "R02"]
    assert rp.agreement(rows)["fields"]["h3"] == {"n": 0, "agree": 0, "share": None}


def test_cohen_kappa_matches_a_hand_worked_example():
    # observed 4/6; expected (3/6)^2 + (2/6)^2 + (1/6)^2 = 7/18; kappa = 5/11
    a = ["2", "2", "1", "0", "2", "1"]
    b = ["2", "1", "1", "0", "2", "2"]
    assert rp.cohen_kappa(a, b) == pytest.approx(5 / 11)
    assert rp.cohen_kappa(["1", "2"], ["1", "2"]) == pytest.approx(1.0)


def test_cohen_kappa_is_none_when_undefined():
    assert rp.cohen_kappa(["2", "2", "2"], ["2", "2", "2"]) is None
    assert rp.cohen_kappa([], []) is None


def test_agreement_reports_kappa_for_score_and_h2():
    k = rp.agreement(_merge())["kappa"]
    assert set(k) == {"score", "h2"}
    assert k["score"]["n"] == 4 and k["h2"]["n"] == 3
    assert k["h2"]["kappa"] == pytest.approx(1.0)


# -- command line ---------------------------------------------------------------------


def test_main_merge_writes_the_merged_sheet_and_agreement(tmp_path, capsys):
    base = _write(tmp_path / "sheet.csv", _base_rows())
    nic = _write(tmp_path / "sheet-nicole.csv", _filled(NICOLE, "nicole"))
    kel = _write(tmp_path / "sheet-kelsey.csv", _filled(KELSEY, "kelsey"))
    out = tmp_path / "sheet-merged.csv"
    code = rp.main(["merge", "--sheet", str(base), "--nicole", str(nic), "--kelsey", str(kel),
                    "--out", str(out)])
    assert code == 0
    assert capsys.readouterr().out.strip() == str(out)
    assert len(rp.read_sheet(out)) == 4
    agreement = json.loads((tmp_path / "agreement.json").read_text(encoding="utf-8"))
    assert agreement["fields"]["score"]["agree"] == 3


def test_main_merge_reports_an_error(tmp_path, capsys):
    base = _write(tmp_path / "sheet.csv", _base_rows())
    code = rp.main(["merge", "--sheet", str(base), "--nicole", str(base), "--kelsey",
                    str(base), "--out", str(tmp_path / "m.csv")])
    assert code == 1
    assert capsys.readouterr().out.startswith("error:")
    assert not (tmp_path / "m.csv").exists()
