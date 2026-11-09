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
- **Whole-file ground truth** (24 SWE-QA questions whose answers name a file but no lines, for example `swe-qa-flask-37`, all of `cli.py`): any chunk of that file would overlap it, so such a question counts for `file_hit` but is left out of the line figure. The runner records `line_truth`, the ground-truth entries that are real line ranges (not line 1 to the file's last line at `repo_commit`); line hit compares only against those, so a question that mixes a whole-file entry with real ranges (12 questions in the frozen set) is scored on its real ranges. A question with no real range is `whole_file: true` and counts for the file figures only. The run details record the embedder and re-ranker settings from the config (model, revision, device, dtype) and the class used.
- `hit_rates(rows, ks) -> dict`: for each setup and k, `{"n", "file_hits", "file_rate", "line_n", "line_hits", "line_rate"}` (`line_n` counts only questions that are not `whole_file`) overall and grouped by `set`, `category` and `complexity` (AC-4.5). A question with no ground truth (the 8 unanswerable controls; all 48 SWE-QA questions have one, AC-2.2) is left out of `n` and counted under `excluded` (AC-4.1, AC-2.2). A group with `n = 0` has rate `None`, never a division by zero.
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
  - `meta.run`: the shared run details from `run_meta` (§3.1), the same shape as the LLM runner's results; `None` when no config file is given. With `--sent` it also records the generator profile and the server. A `--config` path that does not exist is an error.
  - `summary`: the output of `hit_rates`.
- `--reported` refuses to run unless CodeCompass is a git checkout with no uncommitted changes, and records the commit and tag (`git describe --tags`); without it the file is labelled `dev` and never used in a reported comparison (AC-6.4).
- **Reported runs use a git clone, not a zip:** the cluster copy uploaded as a zip has no `.git`, so the commit cannot be read. Official runs (both runners) clone the repository on the cluster and check out the tag `eval-v1`.

### 2.3 Design decisions

- **One runner, many configurations:** setups are measured by calling the existing functions, not by adding pipeline flags (§13 C4).
- **Ranked lists are stored, not just hit counts,** so figures can be recomputed or checked by hand without re-running.

## 3. LLM runs and grading sheet (AC-5.1–5.5, AC-6.1–6.4, AC-7.1–7.4, AC-8.1–8.5)

Runs every question through `ask()` in each configuration, records everything a grader and the report need, and builds the blind grading sheet. Nothing in `codecompass/online` or `codecompass/offline` changes. Standard library only.

### 3.1 Run details: `codecompass/eval/run_meta.py`

`run_meta(config_path, repo_path, *, index_dir=None, profile=None, server_url=None, project_dir=None) -> dict`

Shared by the retrieval runner (§2.2) and the LLM runner (§3.5); each runner adds its own fields (question files and their SHA-256, k values or mode, `label`, end time). **Every key below is always present, and a value is `None` when it does not apply**, so two results files can be compared key by key (AC-5.3).

| Group | Keys | Source |
|---|---|---|
| `codecompass` | `commit`, `tag`, `dirty` | `git rev-parse HEAD`, `git describe --tags --exact-match` and `git status --porcelain` in `project_dir` (default: the checkout that contains the `codecompass` package). All `None` when it is not a git checkout; `tag` is `None` when HEAD has no tag. |
| `repo` | `path`, `head_commit` | `repo_path` and `git rev-parse HEAD` in it |
| `index` | `dir`, `state`, `indexed_commit`, `embedder_model`, `embedder_revision` | offline `status()` |
| `config` | `path`, `sha256`, `retrieval`, `chunking` | the config file, its SHA-256, and its loaded retrieval and chunking settings |
| `embedder` | `model`, `revision`, `device` | config |
| `reranker` | `model`, `revision`, `device`, `dtype` | config |
| `generator` | `profile`, `model_id`, `gguf_file`, `gguf_checksum_pinned`, `context_window`, `temperature`, `seed`, `timeout_seconds`, `max_verifier_rounds` | the resolved profile and config; all `None` when `profile` is `None` |
| `server` | `url`, `build_info`, `model_path`, `n_ctx` | `GET <server_url>/props`; all `None` when `server_url` is `None`. An unreachable server raises `ValueError`, so a run never records a server it could not read. |
| `host` | `hostname`, `gpu`, `python`, `started_at` | `socket.gethostname()`, `nvidia-smi --query-gpu=name` (`None` if absent), `platform.python_version()`, UTC time in ISO 8601 |

- The GGUF checksum is the profile's pinned value, recorded as pinned: `llama-server` does not report it.
- `/props` is read through the module's `urlopen`, so tests replace it with a fake server (the required suite blocks real sockets).
- Reported runs use a git clone of the tag `eval-v1` (§2.2), so `codecompass.commit` and `tag` are always known for them.

### 3.2 Evaluation config: `eval/codecompass.eval.toml`

A committed copy of `codecompass.toml` with these differences: `[embedder] device = "cuda"`; `[reranker] device = "cuda"`, `dtype = "float16"`; `[generator] timeout_seconds = 300`; and `docs_fallback = false` stated explicitly in `[retrieval]`. Every other value equals `codecompass.toml`, so the file has the full `[generator]` section and the `dev` profile, not only the GPU settings. Every results file names it and its SHA-256 (AC-5.4a).

**Timeout (timing run, 2026-11-08, cluster RTX 3090, `dev`, 5 `rag_tools` questions outside the evaluation set):** since T19.3 the timeout is a per-wait limit (no output for that many seconds). The longest wait was 1.8 s (prompt processing of 4,566 tokens); every request finished within 2.5 s. Three times that is about 6 s, so the 300 s floor applies.

### 3.3 Grading subset: `codecompass/eval/subset.py`

`select_subset(rows) -> list[str]` (question ids), deterministic:

1. Group the answerable questions by (category, set, complexity).
2. In each group, order the questions by `sha256(id)` and take the first. Nobody chooses the questions, and the rule has no free parameter: a seeded random draw would leave the seed open to being tried until the subset looked favourable, which a reader could not rule out.
3. For each answerable category, take one `simple` and one `code-tracing` from `core`, and the same from `swe-qa`. If a group is empty, take the next question in `sha256` order from the same category and set.
4. Unanswerable: the first 4 core unanswerable questions in `sha256(id)` order.

The chosen ids are written to `eval/questions/grading-subset.json` and **committed before the first LLM run**. The tests check the rule, not the list, and also check that the committed file is what the rule gives for the frozen question files, so a hand edit fails.

`python -m codecompass.eval.subset FILE [FILE ...] --out PATH` writes `{"rule": "plan 003 §3.3", "question_files": [{"path", "sha256"}], "ids": [...]}` with the ids sorted, and prints how many were chosen per category and tag. Each SHA-256 is taken with line endings normalised to LF, so it is the same on Windows and Linux checkouts.

### 3.4 Recording generator: `codecompass/eval/recording.py`

`RecordingGenerator(inner)` implements `generate(messages, *, on_text=None)` and `count_tokens(text)` by passing them through to `inner`, and keeps a copy of each `messages` list and each returned text in `calls`, in order. The runner passes it as `ask(..., generator=RecordingGenerator(real))`. This gives the graders the full context (retrieved chunks and full tool results; the audit log keeps only the first line of each tool result) and keeps the model's raw text (§13 C8).

### 3.5 LLM runner: `codecompass/eval/llm_run.py`

`python -m codecompass.eval.llm_run FILE [FILE ...] --repo PATH --config TOML --mode {no_retrieval,rag,rag_tools} [--subset PATH] [--index-dir DIR] [--profile dev] [--reported] [--out DIR] [--resume FILE]`

`run_llm(question_files, repo_path, *, config_path, mode, subset_path, profile="dev", index_dir=None, generator=None, reranker=None, embedder=None, reported=False, project_dir=None, out_dir=Path("eval/results"), resume=None) -> Path`. `--subset` defaults to `eval/questions/grading-subset.json`. The runner **loads the config from `config_path` itself**, so the config recorded (path and SHA-256) is the config that ran; a missing file stops the run.

- **Checks first**, refusing to start if any fails (`ValueError`, no file written): the mode is one of the three; the question files pass `check_question_set`; the repo's HEAD equals every question's `repo_commit`; the index's commit equals it too (AC-1.2); with `--reported`, a clean git checkout (AC-6.4).
- Sets `pipeline.mode` from `--mode` on the loaded config. One results file per mode: `<out>/llm-<mode>-<UTC time>.json` (default `eval/results/`). A `--resume` file from another mode is refused.
- The generator defaults to the configured `llama-server` generator for the profile; tests pass a stub.
- Creates the embedder, re-ranker and generator **once** and passes them to every `ask()` call. In the timing run, loading them in a new process for each question took about 15 of the 20 s per question; loaded once, a question takes about 5–8 s, so 264 runs take about 30 minutes.
- For each question: `ask()` with a fresh `RecordingGenerator`. On an exception it records the type and message and retries once; if the retry fails too, it records the error and moves on (AC-5.5).
- Rewrites the results file after **every** question, so an interrupted run loses at most one answer. `--resume FILE` continues that file and skips ids that already have a result or a final error.
- Per question (AC-6.3): `id`, `set`, `category`, `complexity`, `in_subset`; `mode` (from the audit log, to show each question really ran in that mode); `answer` (rendered); `raw_text` (last generator output); `citation_outcome`; `sources` with `verified`; `unverified` and `unreferenced` (from the audit log's `citation` record); `retrieved`, `tool_calls` and `round_limit_hit` from the audit log; `timings`; `log_file`; `messages` (the recorded calls, each `{"messages", "output"}`); `error` (`{"type", "message"}` or `None`) and `attempts`. A question that failed both attempts has `None` in the answer fields.
- `meta`: `run_meta(...)` plus `mode`, `docs_fallback`, `label` (`reported` or `dev`), each question file with its SHA-256, the subset file with its SHA-256, and start and end times.

### 3.6 Automatic labels and grading sheet: `codecompass/eval/grading.py`

- `is_abstention(answer) -> bool`: true for `NO_EVIDENCE`, `NO_INDEX`, or an answer with no `Sources` that says it "could not find" or "could not determine" (any case) (AC-7.4). A pre-fill; the grader confirms it. `None` (an errored question) is not an abstention.
- `labels(row) -> dict` for one result row, all `None` for an errored row:
  - `format_slip`: outcome G, the answer has sources, and `set(unverified) == set(unreferenced)` (`unreferenced` is always a subset of `unverified`). Covers both "no markers at all" and "some markers missing" (AC-7.3).
  - `uncited`: no sources and not an abstention. Nothing was fabricated (Article VI.3), so it is **not H1**; the graders judge its claims under H2. **(decided 2026-11-08)**
  - `h1`: outcome G, not an abstention, at least one unverified marker, and not a slip: a citation that matches nothing, a `[N]` with no entry, or a duplicate marker (AC-7.2, AC-7.3). `h1_strict` is `h1` or a slip.
- `citation_accuracy(rows)`: verified ÷ all `Sources` entries (micro average), and the share of answers that are F, over the rows without an error (AC-7.1). `None` when there is nothing to divide by.
- `summary(results)`: per run, `n` (answered), `errors`, `abstentions`, `format_slips`, `uncited`, `h1`, `h1_strict` and the citation accuracy, over **all** questions in the run (automatic metrics cover all 88).
- `load_results(path)` reads `.json` or `.json.gz`, in case a results file is compressed for size.
- `make_sheet(results_a, results_b, results_c, question_rows, *, seed, out_dir)`: one row per subset question in (b) and in (c) (20 + 20), plus one row per **answerable** subset question in (a) (16, for the contamination check, AC-10.1); 56 rows in all. Reference answers and citations come from `question_rows`. Rows are shuffled together with `random.Random(seed)` and numbered `R01`, `R02`, …, so the configuration is hidden (AC-8.1, AC-8.3). The harness leaves every grader column empty (AC-8.5). An errored answer is skipped and listed in `key.json`. It refuses results in the wrong slot (for example a `rag_tools` run given as (b)) or runs whose conditions differ (all `run_meta` groups except `host`, plus `docs_fallback`, `label`, the question files and the subset) (AC-5.3).
- `python -m codecompass.eval.grading --a FILE --b FILE --c FILE --questions FILE... --seed N --out DIR` writes the sheet folder and `summary.json` (the summary for each run) and prints the folder.
- Row files leave out the system prompt: it is the same fixed text for every answer of a configuration, and it differs when tools are on, so it would reveal the configuration (AC-8.3). Tool results in `rag_tools` rows can still reveal it; the sheet and file names never name it, and the report states this limitation.
- (a) rows are graded for the score only: their H2 and H3 cells are pre-filled `n/a` (no retrieved context to check claims against), and their H1 / slip labels are left out of the hallucination figures, which use (b) and (c) only (§5 "Configuration (a)").
- Output, in `eval/results/grading-<UTC time>/`:
  - `sheet.csv`: one short row per answer: row id, question id, category, tag, set, pre-filled abstention / slip / uncited / H1 labels (`yes`/`no`; slip and H1 `n/a` for (a) rows), the name of the row's Markdown file, and for each grader (`nicole_`, `kelsey_`) H2, H3, score and reason, empty except H2 and H3 `n/a` for (a) rows and H3 `n/a` for answerable questions.
  - `rows/<row id>.md`: everything a grader reads: the question, reference answer and citations, the system answer with its sources and checker outcome, and the full context the model saw (each message, tool results in full). A 32k-token context does not fit in a spreadsheet cell.
  - `key.json`: `seed`, `rows` (row id → question id and configuration) and `skipped` (errored answers). Graders do not open it until grading is finished.
  - `summary.json` (from the command): the automatic counts for each run.

### 3.7 Design decisions

- **Run all, grade a subset:** the automatic metrics cover all 88 questions; human grading covers the 20-question subset in (b) and (c), plus its 16 answerable questions in (a) for the contamination check: 56 rows each, which two graders can finish in an afternoon (§13 C5).
- **Capture context in the harness, not the pipeline:** the recording wrapper uses the public `generator=` parameter (§13 C8).
- **One results file per mode, rewritten after each question:** resumable, and AC-5.3 can compare `meta` across files before any figures are combined.
- **Tag after T5.5:** grading (T5.6) only reads results files, so the official runs can start while it is built.

## 4. Report figures (AC-4.x, AC-7.1, AC-8.4, AC-9.1–9.6, AC-10.2–10.3, AC-11.1)

Reads the graded sheets, the key, and the results files. Writes versioned figures under `eval/results/`. Standard library only. Nothing under `codecompass/online` or `codecompass/offline` changes. No significance tests (AC-9.5); **every figure carries its n**.

### 4.1 Merge the two graders' sheets: `codecompass/eval/report.py merge`

`python -m codecompass.eval.report merge --sheet DIR/sheet.csv --nicole sheet-nicole.csv --kelsey sheet-kelsey.csv --out DIR/sheet-merged.csv`

- Takes each grader's columns **only from that grader's own copy** (`nicole_*` from `sheet-nicole.csv`, `kelsey_*` from `sheet-kelsey.csv`), so neither can overwrite the other. Refuses if the row ids or pre-filled columns differ from `sheet.csv` (someone edited the wrong columns or the wrong file).
- Refuses if any grader cell is still empty (a row not graded), listing the row ids. `n/a` cells must still be `n/a`.
- Checks values: H2/H3 `yes`/`no`; score `0`/`1`/`2`; a reason for every 0, from `unsupported`, `fabricated-citation`, `abstained`, `wrong-but-grounded`; H2 or H3 `yes` must have score 0 (§5.2).
- **Agreement (AC-8.4):** for score, H2, H3 and the 0-reason, the share of rows where the two graders agree (with n), and Cohen's kappa for the score and for H2. It also lists the disagreeing row ids.
- Writes `sheet-merged.csv`: all columns, plus `agree` (`yes`/`no`) and `final_h2`, `final_h3`, `final_score`, `final_reason`, `note`. Final cells are **pre-filled where both agree** and left empty where they disagree. The two graders then fill those together and write in `note` why.
- Writes `agreement.json`.

### 4.2 Figures: `codecompass/eval/report.py figures`

`python -m codecompass.eval.report figures --merged DIR/sheet-merged.csv --key DIR/key.json --results A.json B.json C.json [--retrieval RETRIEVAL.json] --out eval/results/report-<UTC time>/`

- Refuses if any `final_*` cell is empty (disagreements not yet settled) or the rows do not match the key.
- Joins the rows with `key.json` to get each row's configuration. **This is the only place the key is read.**

| Figure | Definition | From | AC |
|---|---|---|---|
| **Hallucination rate** (b), (c) | answers with H1 (pre-filled) **or** final H2 **or** final H3 ÷ graded answers; abstentions in the denominator, errors out (skipped rows) | merged sheet + key | AC-9.1 |
| Same, strict | H1 replaced by strict H1 (the sheet's H1 or format-slip label) | merged sheet + key | AC-7.3 |
| **Verification Gain** | rate(b) − rate(c); positive = tools help | the two rates | AC-9.2 |
| **Quality** | mean final score and the 0/1/2 counts, (b) and (c) | merged sheet | AC-9.3 |
| **Paired comparison** | per question: (c) better / same / worse than (b) on score, and hallucinated in (b) but not (c) and vice versa; split `simple` / `code-tracing` | merged sheet | AC-9.4 |
| Groupings | every figure above overall and by category, tag and set | | AC-9.1, AC-9.3, FR-8 |
| **Contamination** | (a) mean final score, core vs SWE-QA (8 + 8), and the difference; flagged when SWE-QA is higher by ≥ 0.5 (the report interprets it, AC-10.2) | merged sheet | AC-10.2 |
| Citation accuracy (a), (b), (c) | from `summary()` over all 88; also F share, slips, uncited, H1, strict H1, abstentions, errors | results files | AC-7.1, AC-10.3 |
| **Latency** | per configuration: median and max of total time per question, median per stage | results files (`timings`) | AC-11.1 |
| Hit rate@k | copied from the retrieval results file's `summary` (file and line rates, with n) | retrieval file | AC-4.x |
| Failure-example candidates | rows with final H2 or H3 yes, or H1, with question id, configuration and audit-log path; the 3–5 examples are **chosen by hand** | merged sheet + results | AC-9.6 |

- The contamination flag threshold (≥ 0.5) was fixed on 2026-11-09, before any results existed (§4.4).
- Output:
  - `report.json`: every figure, with n, plus the run details (`meta`) of the three results files and the agreement figures;
  - `report.md`: the same as tables, ready to copy into the slides and the report;
  - `failure-candidates.md`.

### 4.3 Design decisions
- **Two steps, with settling in between:** agreement is measured on the raw grades; the figures use only the settled `final_*` values, so the disagreements are resolved by people, not by averaging.
- **The key is read only by `figures`**, after grading, so the configuration stays hidden while grading.
- **No significance tests** (AC-9.5): n is small (20 per configuration); every figure states its n.
- **The figures are computed, not typed:** the slides and the report copy from `report.md`, so the numbers can be traced back to the files.

### 4.4 Decisions (Nicole, 2026-11-09, before any results existed)

1. **Contamination flag:** flagged when the (a) mean score on SWE-QA is **≥ 0.5 above** core (fixed now, before the numbers, so it cannot be tuned). The report also shows the difference, both score distributions and n (8 + 8), with the caveat that the two sets differ in style and difficulty, so a gap suggests memorisation but does not prove it.
2. **Agreement:** % agreement for every field (score, H2, H3, 0-reason), **plus Cohen's kappa for the score and for H2**, each with n. Kappa is shown next to the %, never alone (it is unstable at n = 56).
3. **Unanswerable questions in (b)/(c):** included in the overall hallucination rate **and** reported as their own group (category `unanswerable`).
