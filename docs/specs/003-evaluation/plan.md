# Plan 003: Evaluation Framework

**Spec:** `docs/specs/003-evaluation/spec.md` | **Status:** Partial (2026-11-05): only §1, the question-set check, is planned so far. The runner, metrics, grading sheet and report follow once the team confirms Spec 003 §13.

> This plan says **how** the parts of Spec 003 are built. It is written one section at a time, as each part is needed.

---

## 1. Question-set check (AC-1.1, AC-1.1a, AC-1.2, AC-2.1, AC-2.2)

A deterministic check that a question-set file is in the agreed format and that every reference exists at the pinned repository commit. It is run on each question file before it is frozen, and again on the combined set.

### 1.1 Module and entry point

- `codecompass/eval/questions.py`
  - `FIELDS`: the twelve field names, in order: `id`, `set`, `category`, `complexity`, `question`, `reference_answer`, `reference_citations`, `ground_truth_files`, `source`, `ai_assisted`, `repo_commit`, `original_id`.
  - `load_question_set(path) -> list[dict]`: reads a JSONL file (UTF-8, one object per line, blank lines ignored). A line that is not valid JSON raises `ValueError` naming the file and line number.
  - `check_question_set(rows, repo_path) -> list[str]`: returns one human-readable problem per failed rule, each starting with the question id; an empty list means the set passes. It never raises for a bad row, but raises `ValueError` ("<path> is not a git repository") when `repo_path` is not a git repository at all, so a wrong `--repo` gives one clear error instead of one per question.
  - `main(argv) -> int`: `python -m codecompass.eval.questions FILE [FILE ...] --repo PATH`. Loads every file, checks them as one set (so ids must be unique across files), prints each problem, and returns 0 if there are none, 1 otherwise. If `--repo` is not a git repository it prints a single `error:` line and returns 1.
- Standard library only (`json`, `re`, `subprocess`), no new dependency (Spec 003 §10).

### 1.2 Rules

| # | Rule | Source |
|---|---|---|
| R1 | A row has exactly `FIELDS`, in that order | Agreed format |
| R2 | `id` is unique across all checked rows | AC-1.1 |
| R3 | `set` is `core`, `swe-qa` or `fastapi-heldout`; `source` is `hand-written` or `swe-qa` | Agreed format |
| R4 | `category` is one of the five categories; `complexity` is `simple` or `code-tracing` | AC-1.1, US3 |
| R5 | `question` and `reference_answer` are non-empty strings | AC-1.1 |
| R6 | `ai_assisted` is a boolean | AC-1.5, AC-2.5 |
| R7 | `repo_commit` is a full 40-character hex SHA (otherwise: "must be the full 40-character commit SHA") that exists in the repository (otherwise: "is not in this git repository (<path>); is --repo the right repository?") | AC-1.2 |
| R8 | `ground_truth_files` is empty exactly when `category` is `unanswerable`; each entry is a `.py` file that exists **at `repo_commit`**, with `1 <= start_line <= end_line <=` its line count | AC-1.1, AC-1.1a, AC-1.2, AC-2.2 |
| R9 | Each code citation (`path`, `lines` as `"a-b"`) exists at `repo_commit` with a valid range; each commit citation (`commit`) is `repo_commit` or one of its ancestors | AC-1.2 |
| R10 | `original_id` is `null` for `source = hand-written` and a positive integer for `source = swe-qa` | AC-2.1 |

### 1.3 Design decisions

- **Files are read at `repo_commit`, not from the working tree** (`git show <commit>:<path>` through `subprocess`, no shell). The check gives the same answer whatever is checked out, so a moved branch or a local edit cannot hide a stale reference.
- **Citations may point at non-code files** (for example a README), because graders read them; **ground truth may not** (AC-1.1a), because the index does not contain them.
- **Category counts (8 per category, 40 core) are not checked here.** They apply only to the combined, frozen set; a separate task adds them.

## 2. Later sections

Runner, retrieval ablations, results files, grading sheet and report: to be planned after Spec 003 §13 is confirmed.
