"""T5.3 grading subset tests (tests-first).

Contract under test (Spec AC-5.1, AC-10.1; Plan 003 §3.3):
  - codecompass.eval.subset.select_subset(rows) -> list[str]: 20 question ids, sorted
  - in each answerable category: one `simple` and one `code-tracing` from `core`, and the
    same from `swe-qa`; each is the first of its (category, set, complexity) group in
    sha256(id) order; an empty group falls back to the next question in sha256 order from
    the same category and set
  - unanswerable: the first 4 core unanswerable questions in sha256(id) order
  - python -m codecompass.eval.subset FILE... --out PATH writes
    {"rule", "question_files": [{"path", "sha256"}], "ids"}
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import pytest

from codecompass.eval import subset as sub
from codecompass.eval.questions import load_question_set

ROOT = Path(__file__).resolve().parents[2]
QUESTION_FILES = sorted((ROOT / "eval" / "questions").glob("flask-*.jsonl"))
SUBSET_FILE = ROOT / "eval" / "questions" / "grading-subset.json"

ANSWERABLE = ("architectural", "design-rationale", "localisation", "runtime-behaviour")
SETS = ("core", "swe-qa")
TAGS = ("simple", "code-tracing")


def _h(qid: str) -> str:
    return hashlib.sha256(qid.encode()).hexdigest()


def _row(qid, category, set_, complexity, question="q?"):
    return {"id": qid, "category": category, "set": set_, "complexity": complexity,
            "question": question, "reference_answer": "a"}


def _synthetic() -> list[dict]:
    """3 questions in every (answerable category, set, tag) group, plus 8 core unanswerable."""
    rows = []
    for cat in ANSWERABLE:
        for set_ in SETS:
            for tag in TAGS:
                for i in range(3):
                    rows.append(_row(f"{set_}-{cat}-{tag}-{i}", cat, set_, tag))
    rows += [_row(f"core-unanswerable-{i}", "unanswerable", "core", "simple") for i in range(8)]
    return rows


def _by_id(rows):
    return {r["id"]: r for r in rows}


# -- size and balance (AC-5.1) --------------------------------------------------------


def test_twenty_sorted_unique_ids():
    ids = sub.select_subset(_synthetic())
    assert len(ids) == 20
    assert ids == sorted(set(ids))


def test_four_per_category():
    rows = _synthetic()
    picked = _by_id(rows)
    counts = Counter(picked[i]["category"] for i in sub.select_subset(rows))
    assert counts == {c: 4 for c in (*ANSWERABLE, "unanswerable")}


def test_each_answerable_category_has_one_of_each_tag_from_each_set():
    rows = _synthetic()
    picked = [_by_id(rows)[i] for i in sub.select_subset(rows)]
    for cat in ANSWERABLE:
        cells = Counter((r["set"], r["complexity"]) for r in picked if r["category"] == cat)
        assert cells == {(s, t): 1 for s in SETS for t in TAGS}, cat


def test_each_pick_is_first_in_sha256_order_of_its_group():
    rows = _synthetic()
    ids = set(sub.select_subset(rows))
    for cat in ANSWERABLE:
        for set_ in SETS:
            for tag in TAGS:
                group = [r["id"] for r in rows
                         if (r["category"], r["set"], r["complexity"]) == (cat, set_, tag)]
                assert min(group, key=_h) in ids, (cat, set_, tag)


# -- determinism: ids only, not order or text ----------------------------------------


def test_same_result_whatever_the_input_order():
    rows = _synthetic()
    expected = sub.select_subset(rows)
    for seed in range(5):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)
        assert sub.select_subset(shuffled) == expected


def test_changing_question_text_does_not_change_the_pick():
    rows = _synthetic()
    expected = sub.select_subset(rows)
    edited = [dict(r, question=r["question"] + " (reworded)", reference_answer="other")
              for r in rows]
    assert sub.select_subset(edited) == expected


# -- fallback when a group is empty --------------------------------------------------


def test_empty_group_falls_back_to_next_in_same_category_and_set():
    rows = [r for r in _synthetic()
            if (r["category"], r["set"], r["complexity"])
            != ("architectural", "core", "code-tracing")]
    ids = sub.select_subset(rows)
    assert len(ids) == 20
    core_arch = [r["id"] for r in rows
                 if (r["category"], r["set"]) == ("architectural", "core")]
    expected_two = sorted(core_arch, key=_h)[:2]
    picked_core_arch = [i for i in ids if i in core_arch]
    assert sorted(picked_core_arch) == sorted(expected_two)


# -- unanswerable controls (AC-5.1) --------------------------------------------------


def test_unanswerable_are_the_first_four_core_in_sha256_order():
    rows = _synthetic()
    ids = set(sub.select_subset(rows))
    core_un = [r["id"] for r in rows if r["category"] == "unanswerable"]
    assert {i for i in ids if i.startswith("core-unanswerable")} == set(
        sorted(core_un, key=_h)[:4])


def test_unanswerable_from_swe_qa_is_never_picked():
    rows = _synthetic() + [_row(f"swe-qa-unanswerable-{i}", "unanswerable", "swe-qa", "simple")
                           for i in range(8)]
    ids = sub.select_subset(rows)
    assert not [i for i in ids if i.startswith("swe-qa-unanswerable")]


# -- the real frozen set and the committed file -------------------------------------


@pytest.fixture(scope="module")
def frozen_rows():
    assert len(QUESTION_FILES) == 3, QUESTION_FILES
    return [row for p in QUESTION_FILES for row in load_question_set(p)]


def test_frozen_set_gives_8_simple_8_code_tracing_4_unanswerable(frozen_rows):
    picked = [_by_id(frozen_rows)[i] for i in sub.select_subset(frozen_rows)]
    assert len(picked) == 20
    answerable = [r for r in picked if r["category"] != "unanswerable"]
    assert Counter(r["complexity"] for r in answerable) == {"simple": 8, "code-tracing": 8}
    assert Counter(r["set"] for r in answerable) == {"core": 8, "swe-qa": 8}
    assert sum(r["category"] == "unanswerable" for r in picked) == 4


def test_committed_subset_file_matches_the_rule(frozen_rows):
    """A hand edit of grading-subset.json, or a change to the question files, fails here."""
    data = json.loads(SUBSET_FILE.read_text(encoding="utf-8"))
    assert data["ids"] == sub.select_subset(frozen_rows)
    recorded = {Path(f["path"]).name: f["sha256"] for f in data["question_files"]}
    # Line endings normalised to LF: the same on Windows (CRLF checkout) and Linux
    # (approved test change, 2026-11-08).
    assert recorded == {p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                        for p in QUESTION_FILES}


# -- command line ---------------------------------------------------------------------


def test_cli_writes_the_subset_file(tmp_path, capsys, frozen_rows):
    out = tmp_path / "subset.json"
    code = sub.main([*map(str, QUESTION_FILES), "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"rule", "question_files", "ids"}
    assert data["ids"] == sub.select_subset(frozen_rows)
    assert len(data["question_files"]) == 3
    assert "20" in capsys.readouterr().out


def test_cli_reports_a_missing_question_file(tmp_path, capsys):
    code = sub.main([str(tmp_path / "missing.jsonl"), "--out", str(tmp_path / "s.json")])
    assert code == 1
    assert "error" in capsys.readouterr().out
    assert not (tmp_path / "s.json").exists()
