# Spec 003: Evaluation Framework

**Project:** CodeCompass (SE201 G1-T1) | **Sprint:** 3 | **Status:** Draft v3 for team review (2026-11-01; recommendations in §13 checked against `main` and Flask)
**Owner:** Nicole Goh | **Constitution version:** 1.4.0 | **Constitution articles touched:** I, III, IV, V, VI, VII, VIII, IX, X, XI (see "Constitution Check")

> This spec says **what** the evaluation must measure and how we will know it is correct. It does not choose class designs, file formats or scripts beyond what the constitution fixes; those belong in the plan.
>
> Sources: the approved proposal (§5–§6), Prof. Suppe's feedback on the proposal, and the provisional evaluation rules that were in AGENTS.md §4.3 (2026-10-07, removed in PR #4), updated for constitution 1.4.0. Decisions marked **(recommended)** are agreed by the evaluation owner and wait for team confirmation (§13); the plan is written only after the team confirms them (Article IX.8).

---

## 1. Purpose

Measure whether CodeCompass's retrieval and verification features make answers more grounded, using the controlled comparison required by Article VII and the ablations in the proposal:

1. Frozen question sets with reference answers, reference citations and ground-truth files, fixed before any tuning (Article VII.1).
2. The three configurations of Article VII.2 on the same questions with the same model: **(a)** no-retrieval baseline, **(b)** RAG only, **(c)** RAG + tool verification.
3. The proposal's retrieval ablations: vector-only vs BM25-only vs hybrid (RRF), and hybrid with vs without the re-ranker.
4. Results grouped by **question complexity**, to test the instructor's hypothesis that RAG does well on simple lookups while the agentic system does better on questions that need code tracing.
5. Reproducible, versioned results files (Article VII.6).

### 1.1 Instructor feedback this spec answers
| Feedback (Prof. Suppe) | Where it is handled |
|---|---|
| Allow ample time: the model is slow and there are many ablations. | Retrieval ablations run without the LLM (US4); LLM runs use a fixed subset (US5); runs are resumable (AC-5.5). |
| 40 questions may be too few; use single-repository parts of SWE-QA, SWE-QA-Pro, CoReQA or DeepCodeBench. | Imported SWE-QA Flask set (US2); dataset survey in §12. |
| The model might have memorised these benchmarks. | Contamination check (US10). |
| RAG should do well on simple questions; the agent should do better on code-tracing questions. Cluster the results. | Complexity tag (US3) and grouped reporting (US9). |

## 2. Scope

**In scope (Sprint 3)**
- **Core set:** 40 hand-written questions on `pallets/flask`, 8 per category (§3).
- **Imported set (recommended):** the 48 Flask questions from SWE-QA, at the same Flask commit, converted to our format and reported separately.
- **Held-out set:** 10 questions on `fastapi/fastapi`, sealed until the final generalisation run.
- **Retrieval ablations** (hit rate@k, no LLM) on every answerable question in the core and imported sets.
- **LLM runs** in configurations (b) and (c) on a fixed, balanced subset; configuration (a) for the contamination check.
- Automatic metrics (hit rate@k, citation accuracy, H1, latency), a grading sheet for human judgements, and a summary report grouped by category, complexity tag and question set.

**Out of scope (this spec)**
- Changing chunking, retrieval, re-ranking, prompts or the model. A change after the question sets are frozen is a separate, recorded re-run (Article VII.5), not part of building this framework.
- Grading answers or claims with an LLM. H2, H3 and the 0/1/2 score are human judgements.
- The 32B model. Reported results use one 14B profile (Article VIII.5).
- SWE-QA-Pro, DeepCodeBench and CoReQA (see §12), unless the team decides otherwise.
- A web UI or dashboards.

## 3. Terminology

- **Categories** (core set): `architectural`, `runtime-behaviour`, `design-rationale`, `localisation`, `unanswerable` (controls whose answer is not in the repository).
- **Complexity tag:** `simple` (the answer is in one place: one function, file or commit) or `code-tracing` (the answer needs following calls, data or history across several places). Defined by a written rule (US3). **(recommended, team to confirm: §13 C1)**
- **Answerable question:** any question not in the `unanswerable` category.
- **Ground-truth files:** the files (with line ranges) holding the evidence for the reference answer, valid only at the pinned commit.
- **Configuration:** one value of `pipeline.mode`: (a) `no_retrieval`, (b) `rag`, (c) `rag_tools`.
- **Retrieval setup:** one of `vector`, `bm25`, `rrf` (hybrid, before re-ranking), `rrf+rerank` (after re-ranking and context budgeting).
- **LLM subset:** the fixed, balanced subset of questions run through the generator (US5).
- **Run:** one question set (or subset), answered once in one configuration, with one profile, at one CodeCompass commit.
- **Abstention:** an answer that states it could not determine the answer and makes no claims about the repository.
- **Format slip:** a `Sources` entry whose evidence was in context but whose `[N]` marker is missing from the answer text.

## 4. User Stories and Acceptance Criteria

Priorities: **P1** = required for the final submission, **P2** = should ship, **P3** = nice to have.

### US1 (P1): A frozen, checkable core question set

*As the evaluation owner, I need a fixed question set with references anyone can check by hand, so results can't be shaped to fit the system.*

- **AC-1.1** The core set has exactly 40 questions, 8 per category. Each question has an id, category, complexity tag, question text, reference answer, reference citations, and ground-truth files with line ranges. Unanswerable questions have no ground-truth files, and their reference answer states that the information is not in the repository.
- **AC-1.1a** Ground-truth files are files the index includes: code files such as `src/**/*.py` and `tests/**/*.py`. The indexer skips documentation (`.rst`, `.md`, including `CHANGES.rst`), so a question whose evidence exists only in the docs cannot be answered by the system and is not allowed. A design-rationale question cites the relevant code file plus the commit that explains it (reached through `git log` / `git blame`).
- **AC-1.2** The set records the pinned Flask commit as a full SHA, **(recommended)** `85c5d93cbd049c4bd0679c36fd1ddcae8c37b642` (12 Jun 2025), the commit SWE-QA uses, so both sets share one index. Checked 2026-11-01: full history (5,439 commits), 86 code files and 783 chunks in a dry-run index, and all 112 file and line references in SWE-QA's Flask answers exist at this commit. Every ground-truth file and line range exists at that commit; a check fails loudly if one does not.
- **AC-1.3** The set is frozen before any tuning (Article VII.1). After freezing, a reference changes only to fix a genuine error, in its own commit that states the reason, and every results file produced before the fix is flagged.
- **AC-1.4** Each category's 8 questions include both complexity tags. **(recommended: at least 3 of 8 per answerable category; team to confirm, §13 C2)**
- **AC-1.5** Items drafted with AI help are marked, so they can be disclosed in the AI-use log.

### US2 (P1, proposed): Imported SWE-QA Flask set

*As the team, we need more than 40 questions (instructor feedback) without writing them all by hand.*

- **AC-2.1** The 48 Flask questions from SWE-QA (Peng et al., ACL 2026 Findings; `peng-weihan/SWE-QA-Bench`, `Benchmark/flask.jsonl`) are converted to our format with their original question and reference answer unchanged, and their source and dataset version recorded.
- **AC-2.2** Ground-truth files are taken from the code-file paths and line ranges cited in each reference answer and checked by hand at the pinned commit. Cited `docs/*.rst` files (9 citations, always alongside a `.py` file) are not used as ground truth (AC-1.1a). 46 of 48 questions have a usable `.py` ground truth; the 2 with none are kept for answer grading but excluded from hit rate.
- **AC-2.3** Each imported question gets a category and a complexity tag by the same rules as the core set. SWE-QA's question types map as: `Why` → design-rationale, `Where` → localisation, `How` → runtime-behaviour, `What` → architectural. **(recommended, team to confirm: §13 C3)** The imported set has no unanswerable controls.
- **AC-2.4** The licence and citation are recorded (the repository is Apache-2.0). Imported results are reported separately from the core set and combined only where stated.
- **AC-2.5** If the conversion is done with AI help, it is marked and logged (AC-1.5).

### US3 (P1): Complexity tags

*As the team, we need a consistent simple vs code-tracing label to test the instructor's hypothesis.*

- **AC-3.1** A written tagging rule with examples exists before any question is tagged. (Proposal: Gavin writes the rule.)
- **AC-3.2** Every question in the core and imported sets is tagged independently by two people, and the agreement rate is reported. Disagreements are settled by discussion and recorded. (Proposal: Gavin and Kelsey.)
- **AC-3.3** Tags are frozen with the question sets (AC-1.3).

### US4 (P1): Retrieval ablations (hit rate@k, no LLM)

*As the team, we need to know which retrieval setup puts the right code in front of the model, cheaply, on every question.*

- **AC-4.1** hit rate@k = the share of answerable questions with at least one ground-truth file in the top k (proposal §6.2). Unanswerable questions are excluded.
- **AC-4.2** It is measured for each retrieval setup: `vector`, `bm25`, `rrf` at k = 1, 5 and 10, and `rrf+rerank` at k = 1, 5 and the number of chunks actually sent (`final_k` after context budgeting).
- **AC-4.3** It is computed without generating answers, using the pipeline's own retrieval components (`embed_question`, `vector_search`, `keyword_search`, `rrf_merge`, `retrieve`, `rerank_chunks`, `BgeReranker`, through `open_index`) and the configured k values, without changing pipeline behaviour or adding pipeline flags (§13 C4). The `vector`, `bm25`, `rrf` and re-ranker@k figures need no `llama-server`. The "actually sent" figure applies context budgeting, which counts tokens through the server's `/tokenize` endpoint, so the server must be running (no generation).
- **AC-4.4** The headline is file-level hit rate@10. A line-overlap hit rate (the cited lines overlap a ground-truth range) is reported as a secondary figure.
- **AC-4.5** Results are reported per question set, category and complexity tag.

### US5 (P1): LLM runs on a fixed subset

*As the evaluation owner, I need the configurations compared on the same questions with everything else held constant (Article VII.3–VII.4), within the time we have.*

- **AC-5.1** The LLM subset is chosen before any LLM run by a written rule, balanced across categories and complexity tags, drawn from both the core and imported sets. **(recommended: 20 questions, see §13 C5; team to confirm)**
- **AC-5.2** Every subset question runs in configurations (b) `rag` and (c) `rag_tools` through the public `ask()` API. Configuration (a) is run for the contamination check (US10).
- **AC-5.3** Across configurations in one comparison, the question set, CodeCompass commit, Flask commit, index, profile, model, seed, temperature, timeout and `max_verifier_rounds` are identical. The harness refuses to combine runs that differ in any of these.
- **AC-5.4** All reported runs use one 14B profile on one machine, chosen once (Article VIII.5). **(recommended)** `dev-lowmem` (8k context, temperature 0.1, seed 42) on Nicole's machine with the CUDA build (`-ngl 12`, `-np 1`), timeout 900 s.
- **AC-5.4a** The settings for reported runs live in a committed evaluation config file (for example `eval/codecompass.eval.toml`, a copy of `codecompass.toml` with the evaluation timeout), not in a git-ignored local file, and every results file names it (Article VII.6).
- **AC-5.5** A run can be resumed after an interruption without re-asking questions that already have a result. A failing `ask()` call (for example a timeout) is recorded with its reason and retried once; the run continues.

### US6 (P1): Reproducible, versioned results

- **AC-6.1** Each run writes a results file under `eval/results/` (never `runs/`, which is git-ignored).
- **AC-6.2** Each results file records: the CodeCompass commit (tagged for the reported runs); the pinned repo commit; the indexed commit; the profile, model id, context window, GGUF file and checksum, and llama.cpp release; temperature, seed and timeout; the evaluation config file and its git commit; the embedder and re-ranker revisions; `pipeline.mode`, `max_verifier_rounds`, the enabled tools and the retrieval k values; the question-set versions; and start and end times.
- **AC-6.3** Per question it records: the answer text, citation outcome (F/G), each source with its verification status, retrieved and sent chunks with scores, tool calls, stage timings, errors, and the path of the per-query audit log.
- **AC-6.4** Development runs are labelled as such and never mixed into a reported comparison.

### US7 (P1): Citation accuracy, H1 and format slips

- **AC-7.1** Citation accuracy = `Sources` entries the checker verifies ÷ all `Sources` entries, over all answers in a configuration (micro average, proposal §6.2). The share of answers that are fully F is reported alongside. Target: more than 95% (§7).
- **AC-7.2** H1 is pre-filled from the checker outcome (§5.2). An abstention is never H1.
- **AC-7.3** Format slips are detected and counted separately. **(recommended)** A format slip alone is not H1; the answer's claims are still graded for H2. A "strict H1" that counts slips is reported for transparency. (team to confirm: §13 C7)
- **AC-7.4** Each answer is pre-labelled as a likely abstention by matching the pipeline's no-evidence message and phrases such as "could not find" or "could not determine"; a grader confirms. **(recommended)**

### US8 (P1): Blind grading sheet

*As a grader, I need everything required to judge each answer, without knowing which configuration produced it.*

- **AC-8.1** For each answer in configurations (b) and (c), the harness produces a grading row: question, category, tag, reference answer and citations, the system answer with sources and checker outcome, the pre-filled H1, format-slip and abstention labels, and the full context the model saw.
- **AC-8.2** The full context comes from the harness recording the messages sent to the generator (retrieved chunks and full tool results), with no change to Spec 002 code. **(recommended)** (team to confirm: §13 C8)
- **AC-8.3** Rows are shuffled and the configuration is hidden from graders.
- **AC-8.4** Two graders grade every row independently (proposal: Nicole grader 1, Rodney grader 2): H2, H3 (unanswerable only), the 0/1/2 score, and for every 0 a reason (`unsupported`, `fabricated-citation`, `abstained`, `wrong-but-grounded`). Agreement is reported; disagreements are settled together and recorded.
- **AC-8.5** The harness never fills in H2, H3 or the quality score.

### US9 (P1): Headline results, grouped

- **AC-9.1** Hallucination rate = hallucinated answers ÷ answers in that configuration (§5.2), reported overall and by category, complexity tag and question set. **(recommended)** Abstentions are in the denominator (not hallucinated); pipeline errors are excluded and counted separately. (team to confirm: §13 C9)
- **AC-9.2** Verification Gain = hallucination rate (b) − hallucination rate (c), on the same subset and conditions. Positive means verification helps.
- **AC-9.3** Answer quality (mean 0/1/2 and distribution) for (b) and (c), by category, complexity tag and question set.
- **AC-9.4** A paired comparison per question: whether (c) did better, the same or worse than (b), shown separately for `simple` and `code-tracing` questions.
- **AC-9.5** No significance tests (the sample is small); every figure states its number of questions. **(recommended)**
- **AC-9.6** The report keeps 3–5 failure examples from the frozen sets, each with its audit log, for the write-up.

### US10 (P2): Contamination check

*As the team, we need to know whether the model already knows Flask or the imported questions, which would inflate results (instructor feedback).*

- **AC-10.1** Configuration (a) `no_retrieval` is run on a sample of core and imported questions, and the answers are graded 0/1/2 against the references.
- **AC-10.2** The report compares no-retrieval quality on imported vs core questions. A clearly higher score on imported questions is flagged as possible memorisation, and imported results are interpreted with that caveat. (Context: Qwen2.5-Coder was released in late 2024, before SWE-QA was published in Sept 2025, so the benchmark itself is unlikely to be memorised; Flask's code may be.)
- **AC-10.3** Citation accuracy in (a) is reported; it is expected to be near zero (proposal §6.3).

### US11 (P2): Latency

- **AC-11.1** Per configuration: median and maximum total time per question, and the median per stage, from audit-log timings. The latency cost of verification is reported, not omitted (proposal §6.3).

### US12 (P3): Held-out generalisation run

- **AC-12.1** After the Flask comparison is complete and nothing is being tuned, the FastAPI set runs once in (b) and (c) under the same conditions, reported separately. (Proposal: Swen.)

## 5. Definitions

### 5.1 Answer-quality score (0/1/2, proposal §6.2)
- **2:** correct, matches the reference answer, and supported by the evidence.
- **1:** partially correct, for example explains *what* but not *why*.
- **0:** incorrect, or claims not supported by the retrieved evidence, or an abstention on an answerable question. Every 0 records a reason (AC-8.4).

### 5.2 Hallucinated answer (hallucination rate and Verification Gain)
An answer is **hallucinated** if **any** of these is true:

| # | Condition | Decided by |
|---|---|---|
| H1 | **Fabricated or unmatched citation.** The checker returns G for an answer that makes claims about the repository (Article VI), other than for a format slip alone (AC-7.3, proposed). | Automatic |
| H2 | **Unsupported claim.** At least one factual claim about the repository is not supported by the evidence in the generator's context (retrieved chunks and tool results), including claims true of the repository that came from the model's own knowledge (Article I.1–I.2). Uncited parts marked "(not cited)" (Article VI.3) count if they are unsupported. | Human |
| H3 | **Fabricated answer to an unanswerable control.** A substantive answer instead of saying it could not determine it (Article I.2–I.3). | Human, unanswerable only |

**Not hallucinated:** an abstention (scored 0 on an answerable question, recorded as *abstained*); a supported but incomplete answer (score 1).

**Relation to quality:** H2 and H3 answers always score 0. A 0 that is wrong only because it is incomplete or misread, with every claim traceable to the context, is `wrong-but-grounded`, not hallucinated.

**Why both checks:** the checker only proves a cited file or commit was in the context, not that the claim is correct (Article VI.5); H2 catches F answers that still hallucinate.

**Configuration (a):** graded only for the contamination check (US10) and citation accuracy; hallucination rate and Verification Gain use (b) and (c) only.

## 6. Evaluation data rules

- **Development repo:** `pallets/flask` at one pinned commit, recorded in every question set. Full clone with history (the `git log` and `git blame` tools need it).
- **Held-out repo:** `fastapi/fastapi`. Never indexed, queried or tuned against during development; its questions are not read until the final run (US12). None of the surveyed datasets include FastAPI.
- **Frozen references:** fixed before any tuning (Article VII.1) and never edited to match system output (AC-1.3). This applies to imported questions too.
- **One profile:** every reported comparison uses one 14B profile (Article VIII.5); results from different profiles are never mixed.
- **Results files:** versioned under `eval/results/`, never `runs/`.
- **Prompt changes after the baseline:** an optional prompt change (for example a nudge to write `[N]` markers) may be tried only after the baseline runs are recorded, by the prompt owner, as a separate recorded run (Article VII.5). It never replaces the baseline.

## 7. Success criteria (proposal §6.3, provisional)

- Hybrid (RRF) beats `vector` and `bm25` on hit rate@10, and re-ranking improves it further. If not, the report says the added complexity is not justified.
- (c) beats (b) on answer quality, with the largest gain on design-rationale and **code-tracing** questions; (b) and (c) are close on `simple` questions (instructor hypothesis).
- Verification Gain > 0.
- More than 95% of citations resolve in (b) and (c); the no-retrieval baseline is expected to fail this.
- The latency cost of verification is reported.

## 8. Functional Requirements

| ID | Requirement | Satisfied by |
|----|-------------|--------------|
| FR-1 | Question sets **MUST** be frozen, pinned to a commit, tagged and checkable by hand. | AC-1.1–1.5, AC-2.1–2.5, AC-3.1–3.3 |
| FR-2 | The FastAPI set **MUST NOT** be used before the final generalisation run. | AC-12.1 |
| FR-3 | Retrieval ablations **MUST** run without the generator and without changing pipeline behaviour. | AC-4.1–4.5 |
| FR-4 | LLM runs **MUST** use the public `ask()` API, and runs combined in a comparison **MUST** share every condition except the configuration. | AC-5.1–5.5 |
| FR-5 | Every run **MUST** write a versioned results file with full provenance. | AC-6.1–6.4 |
| FR-6 | Automatic metrics **MUST** be deterministic. | AC-4.x, AC-7.1–7.4 |
| FR-7 | H2, H3 and the quality score **MUST** be blind human judgements; the harness **MUST NOT** fill them in. | AC-8.1–8.5 |
| FR-8 | The report **MUST** group results by category, complexity tag and question set. | AC-4.5, AC-9.1–9.6 |
| FR-9 | The harness **MUST NOT** change pipeline behaviour, prompts or retrieval parameters. | Scope; Article VII.1 |

## 9. Edge Cases

Each needs at least one test:

- A ground-truth path or line range that does not exist at the pinned commit fails the question-set check.
- Wrong number of core questions per category fails the check.
- An imported question with no usable ground-truth file is excluded from hit rate but kept for grading.
- `ask()` times out: recorded, retried once, run continues.
- An interrupted run resumes without repeating answered questions.
- Two runs with different profiles, commits, seeds or timeouts are refused as one comparison.
- An abstention with no `Sources` is not H1.
- A format slip is counted separately and is not H1 on its own (recommended).
- Configuration (a): excluded from hit rate, Verification Gain and hallucination rate.
- A stale index during a run is flagged, and the run is not reported until re-run on a current index.
- An unanswerable question answered with an abstention is correct behaviour (not H3).

## 10. Non-Functional Requirements

- **Reproducibility:** fixed seed and temperature from the profile, pinned models and commits, a tagged CodeCompass commit for reported runs, versioned results (Article VII.6).
- **Determinism:** the same recorded answers always give the same automatic metrics and report.
- **Isolation:** the required test suite uses stubs and fixtures only (Article IX.7); real runs are not part of it.
- **Time budget:** LLM runs take about 5 minutes per question per configuration on the chosen machine (measured 2026-10-31, CUDA build); the subset and resumable runs keep the total within the schedule.
- **Dependencies:** standard library and existing pins only.
- **Integrity:** the harness never writes to question sets or references.

## 11. Key Entities

| Entity | Description | Key attributes |
|--------|-------------|----------------|
| Question | One evaluation question | id, set, category, complexity tag, text, reference answer, reference citations, ground-truth files, source (hand-written / SWE-QA), AI-assisted flag |
| QuestionSet | A frozen set for one repository | repo, pinned commit, version, licence and citation (imported), questions |
| RetrievalResult | Hit-rate data for one question and setup | setup, ranked files and lines, hit@k |
| Run | One set or subset in one configuration | provenance (AC-6.2), per-question results |
| QuestionResult | One answer in one run | answer, outcome, sources, chunks, tool calls, full context, timings, error |
| GradingRow | Human judgements for one answer | hidden configuration, H1 / slip / abstention (pre-filled), H2, H3, score, reason, grader |
| Report | Metrics for a comparison | hit rate@k by setup, citation accuracy, hallucination rate, Verification Gain, quality, contamination, latency, counts, failure examples |

## 12. Dataset survey (2026-11-01)

| Dataset | Flask? | Notes | Decision |
|---|---|---|---|
| **SWE-QA** (Peng et al., ACL 2026 Findings; arXiv 2509.14635) | **Yes: 48 questions** at `85c5d93` | 12 What / 12 How / 12 Why / 12 Where; answers cite files and lines; repo licence Apache-2.0 | **Use (recommended)**: US2 |
| SWE-QA-Pro (TIGER-AI-Lab; arXiv 2603.16124) | No | 27 lesser-known repos (e.g. sanic, mkdocs), filtered against memorisation; MIT | Not used: needs a second repo indexed |
| DeepCodeBench (Qodo, Hugging Face) | No | 912 questions over 8 ML repos; each question at its own commit; Apache-2.0 | Not used: one index per commit is impractical |
| CoReQA (arXiv 2501.03447) | No | ~1,563 questions over ~190 repos, 4 languages; no code repository found | Not used: too few per repo |

## 13. Clarifications

**Decided** (from the proposal and instructor feedback): retrieval ablations measured by hit rate (proposal §6.1, §6.3); file-level hit rate (§6.2); micro citation accuracy (§6.2); blind grading by two graders (task list); quality graded in (b) and (c) only (§6.2); no-retrieval used for contamination and citation accuracy; results grouped by complexity (feedback); FastAPI held out (§5).

**Recommended** (agreed by Nicole on 2026-11-01; team to confirm). Each was checked against `main` (`49e1cf4`) and Flask `85c5d93` on 2026-11-01:

| # | Question | Recommendation | Compatibility check |
|---|----------|----------------|---------------------|
| C1 | Tag names: "simple-lookup vs multi-hop" or "simple vs code-tracing"? | `simple` / `code-tracing`, matching the instructor's wording. | Labels only. |
| C2 | How many code-tracing questions per category? | At least 3 of 8 in each answerable category. | Labels only. |
| C3 | Confirm the SWE-QA type → category mapping. | Why → design-rationale, Where → localisation, How → runtime-behaviour, What → architectural. | SWE-QA has exactly 12 of each type. |
| C4 | Measure single-retriever setups in the harness rather than as pipeline flags? | Yes: no pipeline change needed; Kelsey owns the ablation runner. | All retrieval functions exist and are importable; no pipeline change. The "sent" figure needs `llama-server` running for `/tokenize`. |
| C5 | LLM subset size and selection rule? | 20 questions (4 per category, 2 simple + 2 code-tracing where possible), half core and half imported, chosen by fixed ids before any run. | Flask is small (783 chunks); re-measure time per question on the first runs. |
| C6 | Profile and machine for reported runs? | `dev-lowmem` on Nicole's machine, CUDA build, `-ngl 12`, timeout 900 s. | Profile runs on this machine; seed 42 and temperature 0.1 are sent to the server. The 900 s timeout must go in a committed eval config (AC-5.4a). |
| C7 | Does a format slip count as H1? | No; count separately and report a strict H1 too. | Detectable with public `parse_answer()` / `body_markers()` plus the sent chunks and captured context. |
| C8 | Capture full context through a recording generator wrapper passed to `ask()`? | Yes: no Spec 002 change needed. | `ask()` accepts `generator=`; the wrapper passes `generate()` and `count_tokens()` through. |
| C9 | Hallucination-rate denominator? | Abstentions included; errors excluded and reported. | `NO_EVIDENCE` / `NO_INDEX` are fixed strings; timeouts raise `GeneratorError`. |
| C10 | Pin Flask at SWE-QA's commit `85c5d93…`? | Yes, if the SWE-QA set is adopted; otherwise Flask 3.1.3 (`22d9247…`). Then amend constitution Appendix A #13. | Full history; all 112 SWE-QA references valid; dry-run index 86 files, 783 chunks. |

## 14. Ownership (from the proposal task tracker)

| Work | Owner |
|---|---|
| Spec 003, dataset survey and conversion, contamination check, 8 unanswerable questions, review and freeze all questions, grader 1, results analysis (with Gavin) | Nicole |
| 8 architectural questions, grader 2, index any extra repo | Rodney |
| 8 runtime-behaviour questions, run budget, FastAPI held-out check | Swen |
| 8 design-rationale questions, tagging rule, analysis by complexity (with Nicole) | Gavin |
| 8 localisation questions, second tagger, ablation runner (resumable, cached) | Kelsey |

## 15. Constitution Check

| Article | How this spec complies |
|---------|------------------------|
| I (Grounding) | H2 and H3 measure exactly the failures Article I forbids. |
| III (Index correctness) | Runs use a current index; stale answers are flagged and re-run. |
| IV (Retrieval) | Ablations measure retrieval setups without changing the default pipeline (IV.1). |
| V (Agent loop) | `max_verifier_rounds` and tools are recorded and held constant. |
| VI (Citations) | H1 and citation accuracy come from the deterministic checker; "verified" is never reported as "true" (VI.5). |
| VII (Evaluation first) | The three-way comparison, frozen references, re-run on change and reproducible results are this spec's subject. |
| VIII (Models) | One 14B profile for reported results (VIII.5); model ids and pins recorded. |
| IX (Spec-driven, TDD) | Testable ACs; harness built test-first with stubs; open questions marked. |
| X (Responsible AI) | Contamination check, licence and citation of imported data, and stated sample-size limits. |
| XI (Simplicity) | No new pipeline components; standard library and existing pins. |

No conflicts with the constitution were identified. C10 needs an amendment PR for Appendix A #13.

## 16. Test Strategy

| Test level | What it covers |
|------------|----------------|
| Unit | Question-set validation, SWE-QA conversion and ground-truth extraction, tagging agreement, hit rate@k per setup, citation accuracy, H1 / format-slip / abstention pre-fill, comparison-condition checks, subset selection, report arithmetic and grouping |
| Integration (stub generator, stub re-ranker, fixture repo) | A small run in each configuration; retrieval ablations; results-file provenance; resume after interruption; error retry; grading sheet with hidden configuration and full context |
| Real runs (not in the required suite) | Flask retrieval ablations, the LLM subset in (b) and (c), the contamination check, the FastAPI run |

**Definition of done:** all P1 and P2 ACs have approved, passing tests; CI is green; the Flask comparison has been run, graded and reported.

## 17. What Comes Next

1. Team confirms §13 (C10, C5, C6 and C7 first).
2. Pin the Flask commit; write and convert the question sets; tag them (US1–US3).
3. Write the plan and tasks, each starting with its tests.
4. Amendment PR for constitution Appendix A #13.
