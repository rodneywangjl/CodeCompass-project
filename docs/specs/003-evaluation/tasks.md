# Tasks 003: Evaluation Framework

**Spec:** `docs/specs/003-evaluation/spec.md` | **Plan:** `docs/specs/003-evaluation/plan.md` | **Status:** Partial (2026-11-05)

Each task starts with its tests (Article IX.3): write them, run them red for the expected reason, stop for approval, then implement.

## S1: Question sets

**T1.1 Question-set check**
- Tests first: a valid core row and a valid SWE-QA row pass; each of rules R1-R10 (plan §1.2) is broken in its own test and reported with the question id; ground truth and citations are checked at `repo_commit`, so a range valid there passes even after the file shrinks in a later commit; a duplicate id across two files is reported; a non-JSON line raises `ValueError` with the line number; the command exits 0 for a clean set and 1, printing the problems, otherwise. Bug fix (2026-11-05): a `--repo` that is not a git repository raises `ValueError` and the command prints one `error:` line instead of one problem per question; a commit missing from the repository says "not in this git repository" and names the path; a short `repo_commit` asks for the full 40-character SHA.
- ACs: AC-1.1, AC-1.1a, AC-1.2, AC-2.1, AC-2.2. | Touches: `codecompass/eval/__init__.py`, `codecompass/eval/questions.py`, `tests/eval/__init__.py`, `tests/eval/test_question_set_t11.py`. | Depends on: none.

## S4: Retrieval ablations

**T4.1 Hit-rate maths**
- Tests first: `file_hit` is true when a ground-truth path is in the first k chunks and false when it only appears at rank k+1; `line_hit` needs the same path and an overlapping range (touching ranges count, a range ending one line before does not); a ranked list shorter than k is used as it is; `hit_rates` gives the rate overall and per set, category and complexity; questions with no ground truth are left out of `n` and counted as excluded; a `whole_file` question counts for the file rate but not in `line_n`; an empty group has rate `None`.
- ACs: AC-4.1, AC-4.4, AC-4.5. | Touches: `codecompass/eval/hitrate.py`, `tests/eval/test_hitrate_t41.py`. | Depends on: none.

**T4.2 Retrieval runner**
- Tests first (fixture repo, stub embedder and stub re-ranker): each of the four setups records a ranked list per answerable question using the pipeline's functions; unanswerable questions are skipped; a mismatch between the index commit and `repo_commit` stops the run with a clear error; the results file is written under `--out` with every `meta` field of plan §2.2; without `--sent` the `sent` figure is recorded as not measured and no server is contacted; `--index-dir` and `--config` are used instead of the defaults; `--reported` refuses a working tree with uncommitted changes; nothing under `codecompass/online` or `codecompass/offline` is changed.
- ACs: AC-4.2, AC-4.3, AC-6.1, AC-6.2, AC-6.4. | Touches: `codecompass/eval/retrieval_run.py`, `tests/eval/test_retrieval_run_t42.py`. | Depends on: T4.1.
