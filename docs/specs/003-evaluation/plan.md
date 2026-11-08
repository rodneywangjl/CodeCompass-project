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

## 2. Retrieval ablations (AC-4.1–4.5, AC-6.1, AC-6.2, AC-6.4)

Measures how often the right file is in the top k, for each retrieval setup, without generating answers. Nothing in `codecompass/online` or `codecompass/offline` changes (FR-3, §13 C4).

### 2.1 Hit-rate maths: `codecompass/eval/hitrate.py`

- A **ranked list** is a list of chunks in rank order, each `{"path", "start_line", "end_line", "score"}`.
- **k counts chunks, not files** (decision 2026-11-08): retrieval returns chunks and the pipeline sends chunks. A list shorter than k is used as it is.
- `file_hit(ranked, truth, k) -> bool`: at least one of the first k chunks has the same `path` as a `ground_truth_files` entry (AC-4.4 headline).
- `line_hit(ranked, truth, k) -> bool`: at least one of the first k chunks has the same path **and** overlaps a ground-truth line range (`start <= truth_end and truth_start <= end`) (AC-4.4 secondary).
- `hit_rates(rows, ks) -> dict`: for each setup and k, `{"n", "file_hits", "file_rate", "line_hits", "line_rate"}` overall and grouped by `set`, `category` and `complexity` (AC-4.5). A question with no ground truth (unanswerable controls, and the 2 SWE-QA questions without a `.py` file) is left out of `n` and counted under `excluded` (AC-4.1, AC-2.2). A group with `n = 0` has rate `None`, never a division by zero.
- Standard library only.

### 2.2 Runner: `codecompass/eval/retrieval_run.py`

- `python -m codecompass.eval.retrieval_run FILE [FILE ...] --repo PATH [--config TOML] [--index-dir DIR] [--sent] [--reported] [--out DIR]`
- Opens the index with `open_index`, as `ask()` does, and for each question with ground truth records four ranked lists, using the pipeline's own functions and the configured retrieval settings:
  - `vector`: `vector_search(handles.vector, embed_question(handles, q), 10)`
  - `bm25`: `keyword_search(handles.keyword, q, 10)`
  - `rrf`: `retrieve(handles, q, config=config.retrieval)` (the re-rank shortlist)
  - `rrf+rerank`: `rerank_chunks(reranker, q, <rrf chunks>, len(<rrf chunks>))`
  - Chunk ids become paths and line ranges through `handles.vector.records_for_ids`.
- k values (AC-4.2): `vector`, `bm25`, `rrf` at 1, 5, 10; `rrf+rerank` at 1, 5 and `sent`.
- `sent` (only with `--sent`): the re-ranked chunks after `fit_chunks(chunk_budget(...))`, the same budgeting `ask()` applies, counting tokens through `llama-server` `/tokenize` (no generation). Without `--sent` the figure is recorded as not measured, so the rest runs with no server.
- `--config` and `--index-dir` let the same runner measure another configuration, such as `[chunking] target_tokens = 1024` in a separate index (Rodney's chunk-size experiment), without touching the default index.
- **Refuses to run** when the index's commit differs from the questions' `repo_commit` (AC-1.2), or when the question files fail `check_question_set`.
- Writes one results file, `<out>/retrieval-<UTC time>.json` (default `eval/results/`, never `runs/`, AC-6.1), with:
  - `meta`: CodeCompass commit and whether the working tree was clean; `repo_commit` and the indexed commit; embedder and re-ranker model ids, revisions, device and dtype; the retrieval and chunking settings; the config file path; each question file with its SHA-256; the k values; `label` (`dev` unless `--reported`); start and end times (AC-6.2).
  - `questions`: per question its id, set, category, complexity, ground truth and the four ranked lists with scores.
  - `summary`: the output of `hit_rates`.
- `--reported` refuses to run on a working tree with uncommitted changes; without it the file is labelled `dev` and never used in a reported comparison (AC-6.4).

### 2.3 Design decisions

- **One runner, many configurations:** setups are measured by calling the existing functions, not by adding pipeline flags (§13 C4).
- **Ranked lists are stored, not just hit counts,** so figures can be recomputed or checked by hand without re-running.

## 3. Later sections

LLM runner, grading sheet and report: to be planned next.
