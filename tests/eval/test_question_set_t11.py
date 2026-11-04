"""T1.1 question-set check tests (tests-first).

Contract under test (Spec 003 AC-1.1, AC-1.1a, AC-1.2, AC-2.1, AC-2.2; Plan 003 §1):
  - check_question_set(rows, repo_path) -> list of problems, each starting with
    the question id; [] means the set passes
  - rules R1-R10 (plan §1.2): exact fields in order, unique ids, allowed values,
    non-empty text, boolean ai_assisted, a real repo_commit, .py ground truth
    that exists at repo_commit and is empty exactly for unanswerable questions,
    citations that exist at repo_commit, original_id null or a positive integer
  - files are read at repo_commit, not from the working tree
  - load_question_set(path) reads JSONL; a non-JSON line raises ValueError with
    its line number
  - main([FILE ..., "--repo", PATH]) exits 0 for a clean set, 1 otherwise
"""

import json
import subprocess

import pytest

from codecompass.eval import questions as q

MOD_V1 = "".join(f"line {i}\n" for i in range(1, 11))  # 10 lines
MOD_V2 = "line 1\nline 2\nline 3\n"                     # shrinks to 3 lines


def _git(repo, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A two-commit repo: mod.py has 10 lines at `first`, 3 lines at `second`."""
    path = tmp_path / "repo"
    (path / "src" / "pkg").mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "src" / "pkg" / "mod.py").write_text(MOD_V1)
    (path / "README.md").write_text("# Readme\n\nDonate here.\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "first")
    first = _git(path, "rev-parse", "HEAD")
    (path / "src" / "pkg" / "mod.py").write_text(MOD_V2)
    _git(path, "commit", "-q", "-am", "second")
    second = _git(path, "rev-parse", "HEAD")
    return {"path": path, "first": first, "second": second}


def core_row(commit, **over):
    row = {
        "id": "core-architectural-01", "set": "core", "category": "architectural",
        "complexity": "simple", "question": "Where is mod defined?",
        "reference_answer": "In src/pkg/mod.py.",
        "reference_citations": [{"path": "src/pkg/mod.py", "lines": "2-9"}],
        "ground_truth_files": [{"path": "src/pkg/mod.py", "start_line": 2, "end_line": 9}],
        "source": "hand-written", "ai_assisted": True,
        "repo_commit": commit, "original_id": None,
    }
    row.update(over)
    return row


def swe_row(commit, **over):
    row = core_row(commit, id="swe-qa-flask-01", set="swe-qa", source="swe-qa", original_id=1)
    row.update(over)
    return row


def unanswerable_row(commit, **over):
    row = core_row(commit, id="core-unanswerable-01", category="unanswerable",
                   reference_answer="This isn't in the repository.",
                   reference_citations=[], ground_truth_files=[])
    row.update(over)
    return row


def problems_for(repo, *rows):
    return q.check_question_set(list(rows), repo["path"])


# --- valid sets ------------------------------------------------------------

def test_valid_core_swe_qa_and_unanswerable_rows_pass(repo):
    c = repo["first"]
    assert problems_for(repo, core_row(c), swe_row(c), unanswerable_row(c)) == []


def test_fields_constant_is_the_agreed_order():
    assert q.FIELDS == ["id", "set", "category", "complexity", "question", "reference_answer",
                        "reference_citations", "ground_truth_files", "source", "ai_assisted",
                        "repo_commit", "original_id"]


# --- R1 fields ---------------------------------------------------------------

def test_missing_field_is_reported(repo):
    row = core_row(repo["first"])
    del row["original_id"]
    problems = problems_for(repo, row)
    assert problems and problems[0].startswith("core-architectural-01")


def test_fields_out_of_order_are_reported(repo):
    row = core_row(repo["first"])
    reordered = {"set": row.pop("set"), **row}
    assert problems_for(repo, reordered)


# --- R2 unique ids -----------------------------------------------------------

def test_duplicate_id_is_reported(repo):
    c = repo["first"]
    problems = problems_for(repo, core_row(c), core_row(c))
    assert any("duplicate" in p.lower() for p in problems)


# --- R3 / R4 allowed values ----------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("set", "extra"), ("source", "ai"), ("category", "performance"), ("complexity", "hard"),
])
def test_values_outside_the_allowed_lists_are_reported(repo, field, value):
    problems = problems_for(repo, core_row(repo["first"], **{field: value}))
    assert problems and all(p.startswith("core-architectural-01") for p in problems)


# --- R5 / R6 text and flag ----------------------------------------------------

@pytest.mark.parametrize("field", ["question", "reference_answer"])
def test_empty_text_is_reported(repo, field):
    assert problems_for(repo, core_row(repo["first"], **{field: "   "}))


def test_ai_assisted_must_be_a_boolean(repo):
    assert problems_for(repo, core_row(repo["first"], ai_assisted="yes"))


# --- R7 repo_commit ------------------------------------------------------------

def test_short_or_unknown_repo_commit_is_reported(repo):
    assert problems_for(repo, core_row(repo["first"][:7]))
    assert problems_for(repo, core_row("0" * 40))


# --- R8 ground truth -------------------------------------------------------------

def test_ground_truth_must_be_a_py_file(repo):
    row = core_row(repo["first"], ground_truth_files=[
        {"path": "README.md", "start_line": 1, "end_line": 1}])
    assert problems_for(repo, row)


def test_ground_truth_file_must_exist(repo):
    row = core_row(repo["first"], ground_truth_files=[
        {"path": "src/pkg/missing.py", "start_line": 1, "end_line": 1}])
    assert problems_for(repo, row)


@pytest.mark.parametrize("start,end", [(0, 3), (5, 4), (2, 11)])
def test_ground_truth_range_must_be_inside_the_file(repo, start, end):
    row = core_row(repo["first"], ground_truth_files=[
        {"path": "src/pkg/mod.py", "start_line": start, "end_line": end}])
    assert problems_for(repo, row)


def test_answerable_question_needs_ground_truth(repo):
    assert problems_for(repo, core_row(repo["first"], ground_truth_files=[]))


def test_unanswerable_question_must_have_no_ground_truth(repo):
    row = unanswerable_row(repo["first"], ground_truth_files=[
        {"path": "src/pkg/mod.py", "start_line": 1, "end_line": 2}])
    assert problems_for(repo, row)


def test_files_are_read_at_repo_commit_not_the_working_tree(repo):
    # Lines 2-9 exist at `first` (10 lines) but not at `second` (3 lines),
    # and the working tree is at `second`.
    assert problems_for(repo, core_row(repo["first"])) == []
    assert problems_for(repo, core_row(repo["second"]))


# --- R9 citations ---------------------------------------------------------------

def test_code_citation_may_point_at_a_non_code_file(repo):
    row = core_row(repo["first"], reference_citations=[
        {"path": "src/pkg/mod.py", "lines": "2-9"}, {"path": "README.md", "lines": "1-3"}])
    assert problems_for(repo, row) == []


def test_code_citation_with_a_bad_range_is_reported(repo):
    row = core_row(repo["first"], reference_citations=[{"path": "README.md", "lines": "1-99"}])
    assert problems_for(repo, row)


def test_commit_citation_must_be_in_the_history_of_repo_commit(repo):
    ok = core_row(repo["second"], ground_truth_files=[
        {"path": "src/pkg/mod.py", "start_line": 1, "end_line": 3}],
        reference_citations=[{"commit": repo["first"][:7]}])
    assert problems_for(repo, ok) == []
    later = core_row(repo["first"], reference_citations=[{"commit": repo["second"][:7]}])
    assert problems_for(repo, later)


# --- R10 original_id ----------------------------------------------------------------

def test_original_id_is_null_for_hand_written_and_positive_for_swe_qa(repo):
    c = repo["first"]
    assert problems_for(repo, core_row(c, original_id=3))
    assert problems_for(repo, swe_row(c, original_id=None))
    assert problems_for(repo, swe_row(c, original_id=0))


# --- loading and the command ------------------------------------------------------------

def test_load_question_set_reads_jsonl_and_skips_blank_lines(tmp_path, repo):
    path = tmp_path / "set.jsonl"
    path.write_text(json.dumps(core_row(repo["first"])) + "\n\n", encoding="utf-8")
    assert q.load_question_set(path) == [core_row(repo["first"])]


def test_load_question_set_names_the_bad_line(tmp_path):
    path = tmp_path / "set.jsonl"
    path.write_text('{"id": "a"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="2"):
        q.load_question_set(path)


def test_command_exits_0_for_a_clean_set_and_1_otherwise(tmp_path, repo, capsys):
    c = repo["first"]
    good = tmp_path / "good.jsonl"
    good.write_text(json.dumps(core_row(c)) + "\n", encoding="utf-8")
    assert q.main([str(good), "--repo", str(repo["path"])]) == 0

    other = tmp_path / "other.jsonl"
    other.write_text(json.dumps(core_row(c)) + "\n", encoding="utf-8")  # same id again
    assert q.main([str(good), str(other), "--repo", str(repo["path"])]) == 1
    assert "core-architectural-01" in capsys.readouterr().out


# --- the repository itself (bug fix: a wrong --repo gave one confusing error per question) ---

@pytest.mark.parametrize("kind", ["missing", "not-git"])
def test_a_path_that_is_not_a_git_repository_is_one_clear_error(tmp_path, repo, kind):
    path = tmp_path / "nowhere"
    if kind == "not-git":
        path.mkdir()
    with pytest.raises(ValueError, match="not a git repository"):
        q.check_question_set([core_row(repo["first"])], path)


def test_command_with_a_wrong_repo_path_prints_one_error_and_exits_1(tmp_path, repo, capsys):
    good = tmp_path / "good.jsonl"
    rows = [core_row(repo["first"]), swe_row(repo["first"])]
    good.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert q.main([str(good), "--repo", str(tmp_path / "nowhere")]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 and "not a git repository" in lines[0]
    assert "core-architectural-01" not in lines[0]


def test_a_commit_missing_from_the_repo_says_it_is_not_in_this_repository(repo):
    problems = problems_for(repo, core_row("0" * 40))
    assert problems and "not in this git repository" in problems[0]
    assert str(repo["path"]) in problems[0]


def test_a_short_repo_commit_asks_for_the_full_sha(repo):
    problems = problems_for(repo, core_row(repo["first"][:7]))
    assert problems and "full 40-character" in problems[0]
