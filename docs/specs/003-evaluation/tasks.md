# Tasks 003: Evaluation Framework

**Spec:** `docs/specs/003-evaluation/spec.md` | **Plan:** `docs/specs/003-evaluation/plan.md` | **Status:** Partial (2026-11-05)

Each task starts with its tests (Article IX.3): write them, run them red for the expected reason, stop for approval, then implement.

## S1: Question sets

**T1.1 Question-set check**
- Tests first: a valid core row and a valid SWE-QA row pass; each of rules R1-R10 (plan §1.2) is broken in its own test and reported with the question id; ground truth and citations are checked at `repo_commit`, so a range valid there passes even after the file shrinks in a later commit; a duplicate id across two files is reported; a non-JSON line raises `ValueError` with the line number; the command exits 0 for a clean set and 1, printing the problems, otherwise. Bug fix (2026-11-05): a `--repo` that is not a git repository raises `ValueError` and the command prints one `error:` line instead of one problem per question; a commit missing from the repository says "not in this git repository" and names the path; a short `repo_commit` asks for the full 40-character SHA.
- ACs: AC-1.1, AC-1.1a, AC-1.2, AC-2.1, AC-2.2. | Touches: `codecompass/eval/__init__.py`, `codecompass/eval/questions.py`, `tests/eval/__init__.py`, `tests/eval/test_question_set_t11.py`. | Depends on: none.
