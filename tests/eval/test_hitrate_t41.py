"""T4.1 hit-rate maths tests (tests-first).

Contract under test (Spec 003 AC-4.1, AC-4.4, AC-4.5; Plan 003 §2.1):
  - a ranked list is chunks in rank order: {"path", "start_line", "end_line", "score"}
  - k counts chunks, not files; k = "all" means the whole list (used for "sent")
  - file_hit(ranked, truth, k): a ground-truth path is among the first k chunks
  - line_hit(ranked, truth, k): same path AND overlapping lines
    (start <= truth_end and truth_start <= end)
  - hit_rates(rows, ks) -> {"excluded": [ids], "setups": {setup: {k: groups}}},
    groups = {"overall": stats, "set": {..}, "category": {..}, "complexity": {..}},
    stats = {"n", "file_hits", "file_rate", "line_n", "line_hits", "line_rate"}
  - a row with whole_file = True (ground truth is a whole file) counts for the
    file figures but not in line_n / line_hits
  - questions without ground truth are excluded from n and listed in "excluded";
    a group with n = 0 has rates None
"""

import pytest

from codecompass.eval.hitrate import file_hit, hit_rates, line_hit


def chunk(path, start, end, score=0.5):
    return {"path": path, "start_line": start, "end_line": end, "score": score}


def truth(path, start, end):
    return {"path": path, "start_line": start, "end_line": end}


RANKED = [chunk("src/a.py", 1, 40), chunk("src/b.py", 10, 30), chunk("src/c.py", 5, 9),
          chunk("src/d.py", 100, 150), chunk("src/e.py", 1, 20), chunk("src/f.py", 1, 20)]


# 1. a ground-truth file at rank k is a hit at k, not at k-1
def test_file_hit_at_rank_k_but_not_before():
    t = [truth("src/e.py", 1, 5)]  # rank 5
    assert file_hit(RANKED, t, 5) is True
    assert file_hit(RANKED, t, 4) is False


# 2. off-by-one: the chunk just after the top k does not count
def test_file_hit_ignores_rank_k_plus_one():
    t = [truth("src/f.py", 1, 5)]  # rank 6
    assert file_hit(RANKED, t, 5) is False
    assert file_hit(RANKED, t, 10) is True


# 3. any of several ground-truth files is enough
def test_file_hit_any_of_several_truth_files():
    t = [truth("src/zzz.py", 1, 5), truth("src/b.py", 500, 600)]
    assert file_hit(RANKED, t, 2) is True


# 4. a list shorter than k is used as it is (no crash, no padding)
def test_short_list_is_used_as_it_is():
    short = RANKED[:2]
    assert file_hit(short, [truth("src/b.py", 1, 5)], 10) is True
    assert file_hit(short, [truth("src/c.py", 1, 5)], 10) is False
    assert file_hit([], [truth("src/a.py", 1, 5)], 5) is False


# 5. k = "all" uses the whole list (the "sent" figure)
def test_k_all_uses_the_whole_list():
    assert file_hit(RANKED, [truth("src/f.py", 1, 5)], "all") is True
    assert line_hit(RANKED, [truth("src/f.py", 1, 5)], "all") is True


# 6. line_hit: right file but no overlapping lines is a file hit, not a line hit
def test_line_hit_needs_overlapping_lines():
    t = [truth("src/b.py", 200, 250)]  # b.py chunk is 10-30
    assert file_hit(RANKED, t, 5) is True
    assert line_hit(RANKED, t, 5) is False


# 7. touching ranges overlap; a range ending one line before does not
def test_line_hit_touching_counts_one_line_before_does_not():
    assert line_hit([chunk("src/x.py", 20, 30)], [truth("src/x.py", 10, 20)], 1) is True
    assert line_hit([chunk("src/x.py", 1, 20)], [truth("src/x.py", 20, 25)], 1) is True
    assert line_hit([chunk("src/x.py", 1, 9)], [truth("src/x.py", 10, 20)], 1) is False
    assert line_hit([chunk("src/x.py", 21, 30)], [truth("src/x.py", 10, 20)], 1) is False


# 8. a chunk inside the truth range, and a truth range inside the chunk, both overlap
def test_line_hit_containment_both_ways():
    assert line_hit([chunk("src/x.py", 12, 14)], [truth("src/x.py", 10, 20)], 1) is True
    assert line_hit([chunk("src/x.py", 1, 100)], [truth("src/x.py", 10, 20)], 1) is True


# 9. overlapping lines in a DIFFERENT file are not a line hit
def test_line_hit_needs_the_same_path():
    assert line_hit([chunk("src/other.py", 10, 20)], [truth("src/x.py", 10, 20)], 1) is False


def row(qid, *, set_="core", category="localisation", complexity="simple",
        gt=None, ranked=None, whole_file=False):
    return {"id": qid, "set": set_, "category": category, "complexity": complexity,
            "ground_truth_files": gt if gt is not None else [],
            "whole_file": whole_file, "ranked": ranked or {}}


ROWS = [
    # hit at 1 (file and line)
    row("q1", category="localisation", complexity="simple",
        gt=[truth("src/a.py", 1, 10)],
        ranked={"vector": [chunk("src/a.py", 1, 40), chunk("src/b.py", 1, 5)]}),
    # file hit at 2, but the lines do not overlap
    row("q2", category="localisation", complexity="code-tracing",
        gt=[truth("src/a.py", 500, 600)],
        ranked={"vector": [chunk("src/b.py", 1, 5), chunk("src/a.py", 1, 40)]}),
    # miss
    row("q3", set_="swe-qa", category="architectural", complexity="code-tracing",
        gt=[truth("src/z.py", 1, 10)],
        ranked={"vector": [chunk("src/a.py", 1, 40)]}),
    # unanswerable: no ground truth, must be excluded
    row("q4", category="unanswerable", complexity="simple", gt=[],
        ranked={"vector": [chunk("src/a.py", 1, 40)]}),
]


# 10. overall rates per setup and k, unanswerable excluded
def test_hit_rates_overall():
    out = hit_rates(ROWS, {"vector": [1, 5]})
    k1 = out["setups"]["vector"][1]["overall"]
    k5 = out["setups"]["vector"][5]["overall"]
    assert k1 == {"n": 3, "file_hits": 1, "file_rate": pytest.approx(1 / 3),
                  "line_n": 3, "line_hits": 1, "line_rate": pytest.approx(1 / 3)}
    assert k5 == {"n": 3, "file_hits": 2, "file_rate": pytest.approx(2 / 3),
                  "line_n": 3, "line_hits": 1, "line_rate": pytest.approx(1 / 3)}


# 11. questions without ground truth are listed as excluded, not counted
def test_hit_rates_lists_excluded_questions():
    out = hit_rates(ROWS, {"vector": [5]})
    assert out["excluded"] == ["q4"]


# 12. grouped by set, category and complexity
def test_hit_rates_groups():
    g = hit_rates(ROWS, {"vector": [5]})["setups"]["vector"][5]
    assert g["set"]["core"]["n"] == 2 and g["set"]["core"]["file_hits"] == 2
    assert g["set"]["swe-qa"]["n"] == 1 and g["set"]["swe-qa"]["file_hits"] == 0
    assert g["category"]["localisation"]["file_rate"] == pytest.approx(1.0)
    assert g["category"]["architectural"]["file_rate"] == pytest.approx(0.0)
    assert g["complexity"]["simple"]["n"] == 1
    assert g["complexity"]["code-tracing"]["n"] == 2
    assert g["complexity"]["code-tracing"]["file_hits"] == 1


# 13. a group whose questions are all excluded has n = 0 and rates None
def test_empty_group_has_none_rates():
    g = hit_rates(ROWS, {"vector": [5]})["setups"]["vector"][5]
    empty = g["category"]["unanswerable"]
    assert empty == {"n": 0, "file_hits": 0, "file_rate": None,
                     "line_n": 0, "line_hits": 0, "line_rate": None}


# 14. no questions at all: overall rates are None, no division by zero
def test_no_questions_gives_none_not_an_error():
    out = hit_rates([], {"vector": [1]})
    assert out["excluded"] == []
    assert out["setups"]["vector"][1]["overall"]["file_rate"] is None


# 15. setups are scored independently, and "all" works as a k
def test_hit_rates_several_setups_and_k_all():
    rows = [row("q1", gt=[truth("src/a.py", 1, 10)],
                ranked={"bm25": [chunk("src/b.py", 1, 5)],
                        "sent": [chunk("src/b.py", 1, 5), chunk("src/a.py", 1, 10)]})]
    out = hit_rates(rows, {"bm25": [1], "sent": ["all"]})
    assert out["setups"]["bm25"][1]["overall"]["file_hits"] == 0
    assert out["setups"]["sent"]["all"]["overall"]["file_hits"] == 1


# 16. whole-file ground truth: counts for the file rate, not for the line rate
def test_whole_file_question_is_left_out_of_line_figures():
    rows = [row("q1", gt=[truth("src/a.py", 1, 10)],
                ranked={"vector": [chunk("src/a.py", 1, 40)]}),
            row("q2", set_="swe-qa", gt=[truth("src/cli.py", 1, 1127)], whole_file=True,
                ranked={"vector": [chunk("src/cli.py", 600, 640)]})]
    s = hit_rates(rows, {"vector": [1]})["setups"]["vector"][1]["overall"]
    assert s["n"] == 2 and s["file_hits"] == 2
    assert s["line_n"] == 1 and s["line_hits"] == 1
    assert s["line_rate"] == pytest.approx(1.0)


# 17. mixed ground truth (one whole-file entry + a real range): the line hit uses only the
#     real ranges, so a chunk that only overlaps the whole-file entry is not a line hit
def test_line_hit_uses_only_real_ranges_when_ground_truth_is_mixed():
    gt = [truth("src/cli.py", 1, 1127), truth("src/a.py", 10, 20)]
    real = [truth("src/a.py", 10, 20)]
    only_whole = row("q1", gt=gt, ranked={"vector": [chunk("src/cli.py", 600, 640)]})
    only_whole["line_truth"] = real
    real_hit = row("q2", gt=gt, ranked={"vector": [chunk("src/a.py", 15, 16)]})
    real_hit["line_truth"] = real
    s = hit_rates([only_whole, real_hit], {"vector": [1]})["setups"]["vector"][1]["overall"]
    assert s["n"] == 2 and s["file_hits"] == 2
    assert s["line_n"] == 2 and s["line_hits"] == 1
