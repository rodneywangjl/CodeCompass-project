# Tasks 003: Evaluation Framework

**Spec:** `docs/specs/003-evaluation/spec.md` | **Plan:** `docs/specs/003-evaluation/plan.md` | **Status:** Partial (2026-11-08)

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

## S5: LLM runs and grading

Order: T5.1 first (T4.2 needs it), then T5.2–T5.4 in any order, then T5.5. Tag `eval-v1` after T5.5; T5.6 can be built while the official runs go. T5.3's subset file must be committed before the first official LLM run.

**T5.1 Run details**
- Tests first: every key of plan §3.1 is present in every case; with no profile and no server the generator and server groups are all `None`; with a profile the generator fields come from that profile and the config; with a fake `/props` server the server fields come from it; an unreachable server raises `ValueError`; in a git checkout `commit`, `tag` and `dirty` are read from git (a tagged HEAD gives the tag, an uncommitted change makes `dirty` true); outside a git checkout they are all `None`; the config SHA-256 changes when the file changes; the index fields come from offline `status()` (an unindexed repo gives state `empty` and `indexed_commit` `None`); the result is JSON-serialisable.
- ACs: AC-5.3, AC-6.2. | Touches: `codecompass/eval/run_meta.py`, `tests/eval/test_run_meta_t51.py`. | Depends on: none.

**T5.2 Evaluation config**
- Tests first: `eval/codecompass.eval.toml` loads with the project's config loader; it sets CUDA for the embedder and re-ranker, fp16 for the re-ranker, `docs_fallback = false` and `timeout_seconds = 300`; every other value equals `codecompass.toml`, so it has the full `[generator]` section and the `dev` profile (a file with only the GPU settings fails); the `dev` profile resolves to the 14B model with the pinned checksum and a 32k context.
- ACs: AC-5.4, AC-5.4a. | Touches: `eval/codecompass.eval.toml`, `tests/eval/test_eval_config_t52.py`. | Depends on: none.

**T5.3 Grading subset**
- Tests first: the same input gives the same 20 ids; 4 per category; in each answerable category 2 core and 2 SWE-QA, one of each tag where available; an empty group falls back by the rule; unanswerable picks come from core only; changing a question's text does not change the pick (ids only); the frozen set gives 8 `simple`, 8 `code-tracing` and 4 unanswerable; the committed `grading-subset.json` equals what the rule gives for the frozen files and records their SHA-256; the command writes the file, and a missing question file gives an error and writes nothing.
- ACs: AC-5.1. | Touches: `codecompass/eval/subset.py`, `tests/eval/test_subset_t53.py`, `eval/questions/grading-subset.json`. | Depends on: none.

**T5.4 Recording generator**
- Tests first: with the stub generator, `generate` and `count_tokens` return what the inner generator returns; `on_text` is passed through; every `messages` list and every output is kept in order; `ask()` on the fixture repo gives the same answer and outcome with and without the wrapper.
- ACs: AC-8.2. | Touches: `codecompass/eval/recording.py`, `tests/eval/test_recording_t54.py`. | Depends on: none.

**T5.5 LLM runner**
- Tests first (fixture repo, stub generator, stub re-ranker): the embedder, re-ranker and generator are created once and the same objects are passed to every `ask()` call; each mode writes one results file with every per-question field of plan §3.5, and each question records the mode it ran in; `no_retrieval` sends no chunks and tools run in `rag_tools` only; `in_subset` comes from the subset file; `meta` contains `run_meta` and the run fields; a question whose `ask()` raises is retried once and then recorded with its error, and the run continues; `--resume` skips ids with a result or a final error, and refuses a file from another mode; the file is rewritten after each question; a repo HEAD or index commit different from `repo_commit`, a question set with problems, a missing config file or an unknown mode stops the run before any question; `--reported` refuses a dirty tree and labels a clean run `reported`; the command maps its arguments and prints the path, or `error:` and exits 1.
- ACs: AC-5.2, AC-5.3, AC-5.5, AC-6.1–6.4. | Touches: `codecompass/eval/llm_run.py`, `tests/eval/test_llm_run_t55.py`. | Depends on: T5.1, T5.4.

**T5.6 Automatic labels and grading sheet**
- Tests first: an answer citing nothing that is not an abstention is `uncited`, not H1; an errored row has no labels; `summary` counts each label and leaves errors out; `load_results` reads `.json` and `.json.gz`; errored answers are skipped and listed; results in the wrong slot or under different conditions are refused; the command writes the sheet and `summary.json`, or prints `error:`; `NO_EVIDENCE` and `NO_INDEX` are abstentions, and an answer with sources is not; a G answer whose unverified markers are all unreferenced is a slip, both with no markers at all and with some missing; a G answer with an entry matching nothing, or a `[N]` with no entry, is H1 even if other entries are unreferenced; a slip is not H1 but is strict H1; an abstention is never H1; citation accuracy is micro-averaged; the sheet has one row per subset question in (b) and in (c) and one per answerable subset question in (a) (56 for the real subset; no unanswerable question in (a)), is shuffled the same way for the same seed, hides the configuration, leaves every grader column empty except H2 and H3 pre-filled `n/a` on (a) rows; every row has a Markdown file with the full recorded context except the system prompt, which would reveal the configuration; the key file maps every row back.
- ACs: AC-7.1–7.4, AC-8.1, AC-8.3, AC-8.5, AC-10.1. | Touches: `codecompass/eval/grading.py`, `tests/eval/test_grading_t56.py`. | Depends on: T5.5.

## S6: Report figures

**T6.1 Merge and agreement**
- Tests first:
  - each grader's columns come only from their own file;
  - a changed row id or pre-filled cell is refused;
  - an empty grader cell is refused with its row id;
  - an invalid value, a 0 with no reason, and H2 yes with a non-zero score are refused;
  - agreement is the share of matching rows, with n;
  - Cohen's kappa for the score and for H2 matches a hand-worked example (and is `None` when it is undefined, e.g. both graders give one value throughout);
  - disagreeing rows are listed;
  - final cells are pre-filled only where both agree;
  - the command writes `sheet-merged.csv` and `agreement.json`.
- ACs: AC-8.4. | Touches: `codecompass/eval/report.py`, `tests/eval/test_report_merge_t61.py`. | Depends on: T5.6.

**T6.2 Figures**
- Tests first (small made-up sheet, key and results files):
  - an empty final cell is refused;
  - the hallucination rate counts H1, H2 or H3 once per answer, keeps abstentions in the denominator and leaves skipped errors out;
  - strict H1 also counts slips;
  - Verification Gain = (b) − (c);
  - quality mean and counts;
  - paired better / same / worse, split by tag;
  - groupings by category, tag and set;
  - the contamination difference, and the flag at exactly 0.5 (flagged) and just below it (not flagged);
  - unanswerable questions count in the overall rate and appear as their own group;
  - latency median and max;
  - hit rates copied from the retrieval file;
  - every figure has an n;
  - `report.md` contains each table;
  - failure candidates are the H1, H2 or H3 rows.
- ACs: AC-4.x, AC-7.1, AC-9.1–9.6, AC-10.2, AC-10.3, AC-11.1. | Touches: `codecompass/eval/report.py`, `tests/eval/test_report_figures_t62.py`. | Depends on: T6.1.
