# CodeCompass Constitution

**Version:** 1.2.1 | **Project:** CodeCompass (SE201 G1-T1) | **Status:** In force

CodeCompass is a RAG-based Q&A assistant that helps new developers understand a repository. It retrieves real code and commit history, verifies claims with git tooling, and answers with citations that are checked before they are shown.

This constitution is the set of non-negotiable principles that every spec, plan, task, and line of code (human- or AI-written) must respect. Keywords **MUST**, **MUST NOT**, **SHOULD** are used in the RFC 2119 sense. Each article states its *rationale* so that edge cases can be decided by intent, not just wording.

---

## Article I: Grounding Over Fluency

1. Every factual claim in an answer **MUST** be traceable to text that was actually placed in the generator's context (retrieved chunks or tool results).
2. The generator **MUST NOT** answer from its own training knowledge about the repository. If the evidence is insufficient after the allowed tool rounds, the system **MUST** say what it could not determine rather than guess.
3. "I could not find enough evidence" is a valid, preferred output over a confident but unsupported one.

*Rationale:* The core risk of this product is a confidently cited but subtly wrong answer. Everything else in this document exists to reduce that risk.

## Article II: Two Pipelines, One Contract

1. The system consists of two independent pipelines:
   - **Offline indexing pipeline:** Git repo → Repo scanner (tree-sitter + GitPython) → code-aware embedder → vector store (Chroma/HNSW), plus the same chunks → keyword index (BM25).
   - **Online query pipeline:** Developer question → hybrid retriever → cross-encoder re-ranker → agent/generator → verifier tool loop → citation checker → answer.
2. The **only** coupling between them is the persisted vector store and keyword index. The online pipeline **MUST NOT** call scanner, chunker, embedder-writing, or index-writing code directly; the offline pipeline **MUST NOT** depend on query-time state. The single exception is the offline pipeline's **public `ensure-current` entry point** (Article III.2), which the online pipeline calls before answering. Every other offline function the online pipeline uses is read-only (index handles and index status).
3. The index schema is a versioned contract. Each stored chunk **MUST** carry at least: chunk id, text, file path, start/end line, language, symbol name (if any), and the commit SHA it was indexed at. Changing this schema requires a spec and a migration or full re-index.
4. The query embedder **MUST** be the same model (and version) as the indexing embedder. The embedding model name/version **MUST** be recorded in index metadata, and the online pipeline **MUST** refuse to query an index built with a different one.

*Rationale:* Separation lets indexing be slow and expensive while querying stays fast, and lets two people own the halves without stepping on each other. Mismatched embedders produce silently meaningless results.

## Article III: Index Correctness and Incrementality

1. Indexing **MUST** be incremental: only files changed since the last indexed commit are re-processed (diff via GitPython).
2. Before answering each question, the system **MUST** call the offline pipeline's `ensure-current` entry point, which compares repo HEAD against the last indexed commit and runs an incremental re-index if they differ. If re-indexing fails or cannot run (for example, because another process holds the index lock), the answer **MUST** be produced from the existing index and clearly flagged as based on a stale index; the system **MUST NOT** hang or silently answer from stale data.
3. When a file changes or is deleted, its old chunks **MUST** be removed from **both** the vector store and the BM25 index before new chunks are written. The two indexes **MUST NOT** be left able to disagree about which chunks exist.
4. Chunking **MUST** be structure-aware (tree-sitter): chunks follow function/class/module boundaries and **MUST NOT** cut across them. Files tree-sitter cannot parse **MUST** fall back to a documented line-window strategy rather than being skipped silently.
5. Indexing **MUST** be idempotent: re-running it on the same commit produces the same index state.
6. Secrets and irrelevant artifacts (e.g. `.env`, keys, lockfiles, build output, binaries) **MUST** be excluded from indexing via an explicit, reviewable ignore list.

*Rationale:* Stale or duplicated chunks cause the retriever to cite code that no longer exists, which the citation checker cannot catch because the evidence is "real" but outdated.

## Article IV: Hybrid Retrieval, Then Re-ranking

1. Retrieval **MUST** use both semantic (vector ANN) and lexical (BM25) search, and merge the results into one candidate set. Neither alone is acceptable in the default configuration.
2. Results from the two retrievers **MUST** be merged with **Reciprocal Rank Fusion (RRF)**, using only each chunk's rank in each list (`score = sum(1 / (60 + rank))`, with ranks counted from 0, so a list's top result contributes `1/60`), because cosine similarity and BM25 scores are on incomparable scales and **MUST NOT** be added or averaged directly. A chunk found by both retrievers is counted once, with its contributions summed.
   - Default candidate sizes: retrieve the top **50** from the vector index and the top **50** from BM25; RRF-merge and keep the top **50** as the re-rank shortlist; the cross-encoder re-orders them and the top **8** chunks go to the generator.
   - The RRF constant (60) and the three k values are named, configurable values, not magic numbers in code. The final k is additionally capped by the active model profile's context budget (Article VIII.4).
   - These are starting defaults. They **MAY** be changed only with an evaluation run (Article VII.5) once an evaluation set exists.
3. The cross-encoder re-ranker **MUST** operate only on the shortlist, never on the whole index.
4. The generator **MUST** receive plain text with file/line/commit metadata, never raw vectors.

*Rationale:* Embeddings miss exact identifiers; BM25 misses paraphrase. Cheap recall first, accurate ordering second.

## Article V: Bounded, Auditable Agent Loop

1. The generator either answers or requests a tool call. The loop is governed by the "Enough context?" check `round < 3`: rounds are counted from 0, so the verifier tool may run **at most 3 times** per question. When the generator has enough context, or the round limit is reached, the system proceeds to the citation checker with what it has; it **MUST NOT** loop indefinitely. Each round executes at most one tool call. The limit counts tool executions, not generator calls: if the generator still requests a tool after the third tool result, that request is not executed, and the harness makes one final generator call that runs no tool and asks for an answer from the evidence already in context. The limit is a named constant (`MAX_VERIFIER_ROUNDS = 3`), changed only by amending this article.
2. Tools are **read-only** and **allow-listed**: `git blame` and `git log` only. Adding any other tool (including file search) is out of scope for v1 and requires an amendment. The harness executes tools; the model never gets a raw shell. Arguments **MUST** be validated (path inside repo, line ranges in bounds, no shell interpolation).
3. Tool results **MUST** be cached (keyed by repo, commit, path, line range, command) and **MUST** be appended to the generator's context as messages carrying the tool results, so they count as citable evidence. These are messages in the harness's own documented format, not a server-side tool-calling role (Article VIII.2).
4. Every tool call and result **MUST** be logged per query (round number, tool, arguments, cache hit/miss) so that any answer can be audited after the fact.
5. When commit history gives no useful rationale (e.g. uninformative messages), the system **MUST** say so explicitly instead of inventing a "why".

*Rationale:* Intent usually lives in commit messages, not code. The verifier is only valuable if it is safe, bounded, and honest when commit hygiene is poor (a known limitation of this design).

## Article VI: Citation Integrity (Non-Bypassable)

1. Before any answer is shown, a deterministic **citation checker** **MUST** verify that every cited file and commit appears in the context actually supplied to the generator (retrieved chunks plus tool results) during that query.
2. The checker **MUST** be ordinary code, not an LLM call. It **MUST NOT** be skippable by configuration in the production path.
3. Outcomes:
   - **F: Cited answer** — all citations verified; shown normally.
   - **G: Flagged answer** — at least one citation could not be matched to real evidence; shown with (a) a visible banner above the whole answer stating that some citations could not be verified, and (b) a clear mark on each individual `Sources` entry that failed verification, so the developer knows exactly which to check. A flagged answer **MUST NEVER** be rendered identically to a verified one.
4. Citations **MUST** use the fixed format below, so checking is exact matching, not fuzzy interpretation.
   - **In the answer body:** numbered inline markers, e.g. `...retries three times [1], added to handle a flaky upstream service [2].`
   - **In a closing `Sources` section:** one entry per marker, in one of two forms:
     - Code: `[1] src/auth/client.py, lines 42-58 (indexed at a1b2c3d)`
     - Commit: `[2] Commit a1b2c3d, "handle flaky upstream service", Alice, 2024-03-14`
   - File paths are repo-relative. Commit hashes are the 7-character abbreviation of a hash that exists in the repo.
   - The checker parses only the `Sources` entries and matches each path/line range against retrieved chunk metadata and each commit hash against tool results. A marker with no matching entry, or an entry matching nothing in context, makes the answer **G (flagged)**. An answer with no citations at all is **never** outcome F: with no citations, "all citations verified" would be true of any answer, however unsupported. How such an answer is shown (the G banner, or a distinct "no sources cited" notice for an answer that only states what could not be determined, Article I.3) is set by the spec.
   - Commit subject, author, and date in an entry **MUST** be copied by the harness from the tool result, not generated by the model.
5. The checker verifies that a citation *exists in context*, not that the claim is *correct*. UI copy and documentation **MUST NOT** imply "verified" means "true".

*Rationale:* This stops fabricated file names and commit hashes. Being honest about its limits matters for the Responsible AI goals.

## Article VII: Evaluation First

1. A fixed evaluation question set with hand-written reference answers and reference citations **MUST** exist before pipeline behaviour is tuned.
2. The evaluation is a three-way comparison on the same questions: **(a)** no-retrieval baseline, **(b)** RAG only, **(c)** RAG + tool verification. Scored on **answer correctness** and **citation accuracy**, with hallucination rate as the headline comparison between (b) and (c).
3. The three configurations **MUST** be selectable by configuration flags in one codebase, so differences are attributable only to the retrieval/verification features. The active configuration **MUST** be recorded in every per-query log and every evaluation result file, as the model profile is (Article VIII.4).
4. To keep the comparison unconfounded, the **same single generative model** is used across configurations. Specialisation happens at the retrieval/embedding layer, not by adding more generator models.
5. Any change to chunking, embeddings, retrieval, re-ranking, prompts, or the generator model **MUST** be followed by a re-run of the evaluation, with results recorded alongside the change.
6. Evaluation runs **MUST** be reproducible: pinned model versions, pinned repo commit under test, fixed seeds/temperature where supported, and results written to versioned files.

## Article VIII: Models and Environment

1. Model names, sizes, quantisation, and endpoints **MUST** be configuration, not hard-coded. Decided choices: generator **Qwen2.5-Coder-Instruct**, with the **14B** used for day-to-day development and the **32B** used in production, cross-encoder `bge-reranker-v2-m3`, Chroma (HNSW) as the vector store, tantivy (BM25) as the keyword index. Embedder: **`jinaai/jina-embeddings-v2-base-code`** (open weights, Apache 2.0, ~161M parameters, 8192-token input, trained on code and English text). It runs locally and needs no paid service (Article VIII.6). The revision loaded **MUST** be pinned, because the model requires `trust_remote_code`. The re-ranker's revision **MUST** be pinned too: it decides which chunks the generator sees, so an unpinned re-ranker makes results irreproducible (Article VII.6). Chunks **SHOULD** target roughly 512 tokens or fewer (the model was trained at 512 and extrapolates beyond it), and the chunker **MUST NOT** emit chunks exceeding the model's input limit. voyage-code is excluded from the default path as it is a paid API. A newer code embedder (e.g. `jina-code-embeddings-0.5b`) **MAY** be adopted later only through a full re-index and an Article II.4 version change.
2. **Generator inference uses llama.cpp only.** Qwen2.5-Coder-Instruct is run through **llama.cpp's `llama-server`** using quantised **GGUF** model files, for both the `dev` (14B) and `prod` (32B) profiles. This keeps the project runnable on Linux, Windows, and macOS. mlx-lm and MLX model builds **MUST NOT** be used or listed as a dependency.
   - **Pinning:** the llama.cpp release (tag or commit) in use **MUST** be recorded, and each profile **MUST** pin the exact GGUF file: source repository, file name, quantisation level (e.g. Q4_K_M), and SHA-256 checksum. Changing the quantisation, the GGUF file, or the llama.cpp version is a model change and triggers Article VII.5.
   - **Integration:** the generator interface (Article VIII.4) talks to `llama-server` over local HTTP using a standard HTTP client. `llama-cpp-python` is not used, so no teammate needs a C++ toolchain. Server start-up, health check, and shutdown are handled in one documented place. The server **MUST** bind to localhost only (`127.0.0.1`) unless a deployment spec says otherwise.
   - **Single wrapper:** chat-template handling, stop tokens, and request/response parsing live only inside the generator wrapper; no other module talks to `llama-server` directly.
   - **Tool calls** are produced and parsed by the harness from the model's text output using a documented, tested format. The harness **MUST NOT** rely on any server-side tool-calling feature.
   - **Scope:** llama.cpp serves only the generator. The embedder and the cross-encoder re-ranker run through their own libraries.
   - **Hardware:** GPU acceleration (Metal, CUDA, or Vulkan builds) is optional and chosen per machine through server launch settings in the profile; CPU-only operation **MUST** remain possible. Code **MUST NOT** assume a specific GPU API or model size. Prompts and context assembly **MUST** respect the configured model's context window (set at server launch), and the 32B profile's memory footprint **MUST** be checked on the target machine before release.
3. Dependencies **MUST** be declared in `requirements.txt` (or equivalent lockfile) and versions pinned for anything affecting results.
4. **Switchable generator.** The generator is selected through named **model profiles** in a single config file (e.g. `dev` = 14B, `prod` = 32B), chosen by one setting or environment variable (e.g. `GENERATOR_PROFILE`). Switching models **MUST NOT** require any code change. Specifically:
   - Each profile defines the model id, backend (`llama.cpp` only; the field exists so that any future backend must be added through an amendment, behind the same interface), GGUF file and checksum, server launch settings, quantisation, context window, and generation parameters.
   - All generator access goes through one interface; no other module imports a model library or names a model directly.
   - Prompt templates, context budgeting (how many chunks fit), and tool-call parsing **MUST** be driven by the active profile and work with both models.
   - The active profile and resolved model id **MUST** be logged at startup, recorded on every per-query log (Article V.4), and stored in every evaluation result file.
   - The default profile is `dev`. Production deployments **MUST** set `prod` explicitly, and startup **MUST** fail loudly on an unknown profile rather than silently falling back.
5. **Evaluation and release use the 32B.** Reported evaluation results (Article VII) and any production release **MUST** use the `prod` (32B) profile. Results from the 14B are development signals only and **MUST NOT** be reported as evaluation results. Because the models may differ in tool-call reliability and citation compliance, any change that passes on the 14B **MUST** be re-checked on the 32B before release.
6. Hardware-dependent code is isolated so the required test suite runs anywhere (Article IX.7): everything that needs `llama-server` or a real model sits behind the generator interface and is replaced by a stub generator in tests.
7. The system **MUST** run end to end on a developer laptop with no paid external service required for the core path (embedding API providers are optional alternatives, not requirements).

## Article IX: Spec-Driven, Test-Driven Development

1. **Spec before code.** No feature is implemented without a written spec containing: user story/purpose, functional requirements, **testable acceptance criteria**, out-of-scope items, and which Article(s) of this constitution it touches.
2. **Workflow:** constitution → spec → plan (design and data contracts) → tasks → tests → implementation. Specs **MUST NOT** prescribe implementation details beyond what the constitution fixes; plans may.
3. **Tests derive from acceptance criteria and come first.** Tests are written (or AI-generated from the acceptance criteria and then human-reviewed) and approved **before** any implementation. They cover the happy path, negative paths, and edge cases for each criterion.
   **The TDD cycle is mandatory for every task:**
   1. **Create the test.** Write the test(s) for the task from its acceptance criteria.
   2. **Red.** Run them and confirm they fail, and fail for the expected reason (a missing behaviour, not a typo or import error).
   3. **Code.** Write the minimum implementation needed to satisfy the tests.
   4. **Green.** Run the tests. If any fail, change the code and run again, repeating until **all** pass.
   5. **Refactor.** Clean up with the tests kept green.
   6. Run the full suite before opening a PR.
   Rules that protect the cycle:
   - No production code is written without a failing test that requires it.
   - To turn a test green, change the code, **never the test**. An approved test is only changed when the spec changes or the test itself is wrong, and then with reviewer sign-off. This applies equally to AI coding tools, which **MUST** run the tests themselves and iterate until they pass but **MUST NOT** weaken, skip, delete, or mark as expected-failure an approved test to make it pass.
   - A bug fix starts with a failing test that reproduces the bug.
   - The test commit **MUST** precede the implementation commit in the branch history for the task, so the order is visible in review.
   - A task is done only when its approved tests and the full suite are green, with no skipped or xfail tests lacking a linked justification.
4. Test layers:
   - **Unit tests** for deterministic components: chunker, diff detection, index delete/re-insert, merge/fusion, tool-argument validation, cache, citation checker.
   - **Integration tests** for index→retrieve and retrieve→re-rank on a small fixture repository with known answers.
   - **LLM-dependent behaviour** tested with recorded/stubbed model responses for the harness logic, plus the evaluation set (Article VII) for real-model quality.
5. Required regression tests include: a citation to a non-retrieved file is flagged; the round limit terminates the loop; a changed file leaves no stale chunks in either index; a mismatched embedder version is rejected.
6. **AI-assisted coding is allowed and expected**, subject to: the author runs and understands the change, a second person reviews every PR, and AI output is held to the same tests and this constitution. "The AI wrote it" is not a defence.
7. Pull requests **MUST** reference the spec/task they implement and state which constitution articles they affect. CI **MUST** run the required test suite and a PR **MUST NOT** be merged while it fails. The required suite uses the stub generator and local fixtures only: it **MUST** be deterministic and **MUST NOT** need a GPU, `llama-server`, a model download, or network access. Tests that need a real model are marked separately (e.g. `model`), run locally on the `dev` profile, and are not required for merge. The default test framework is **pytest**.
8. Ambiguity in a spec **MUST** be marked `[NEEDS CLARIFICATION]` and resolved before planning, not guessed by the implementer (human or AI).

## Article X: Responsible AI and Developer Experience

1. **Show the evidence.** Answers **MUST** present citations as navigable references (file/line, commit) so the developer can read the source themselves.
2. **Support learning, not replace it.** Answers **SHOULD** point to where to look next and explain reasoning from evidence, not just hand over a conclusion, to avoid eroding a junior developer's own exploration.
3. **Calibrated confidence.** Flagged answers, stale-index warnings, and "no rationale found in history" messages are required UX states, not optional polish.
4. **Privacy and security.** Repo content is processed locally by default; nothing is sent to a third-party service unless explicitly configured, and secrets are never indexed (Article III.6).
5. **Known limitation, stated openly:** the verifier is only as useful as the repository's commit history. Documentation **MUST** state this.

## Article XI: Simplicity and Scope

1. Build the smallest thing that satisfies the spec and the evaluation. No new component (additional models, databases, agents) without a spec justifying it against Article VII's controlled comparison.
2. Offline and online code live in separate modules with a narrow shared interface (index schema, config).
3. Prefer boring, replaceable choices so components can be swapped without touching the pipeline. The BM25 keyword index uses **tantivy** (Python bindings) behind a small keyword-index interface (add chunks, delete chunks by file, search); no other module imports tantivy directly.

## Governance

- This constitution supersedes individual specs and plans. If a spec conflicts with it, the spec changes, or the constitution is formally amended.
- **Amendments** are made by pull request. The PR **MUST** state the reason for the change, bump the version, and note any specs or code that must change as a result. Normal PR review (Article IX.7) applies; no separate team sign-off is required.
- Versioning: MAJOR = principle removed or redefined; MINOR = article added or materially expanded; PATCH = wording/clarification.
- Compliance is checked at spec review, plan review, and PR review; reviewers explicitly confirm "constitution check: pass" or list violations with justification.

---

## Appendix A: Decisions

**Resolved**

| # | Decision | Where applied |
|---|----------|---------------|
| 1 | Generator is Qwen2.5-Coder-Instruct: 14B for development, 32B for production and evaluation, switchable by config profile with no code change | Article VIII.1, VIII.4-5 |
| 2 | Agent loop uses `round < 3`: at most 3 tool runs, one per round, then one final answer-only call if the model still asks for a tool, then the citation checker | Article V.1 |
| 3 | Citation format: numbered inline markers plus a `Sources` section with fixed entry formats | Article VI.4 |

**Resolved (continued)**

| # | Decision | Where applied |
|---|----------|---------------|
| 4 | Embedder: `jina-embeddings-v2-base-code`, local, pinned revision | Article VIII.1 |
| 5 | Merge: Reciprocal Rank Fusion (constant 60); k = 50 + 50 retrieved, 50 re-ranked, 8 to the generator; all configurable | Article IV.2 |

**Resolved (final batch)**

| # | Decision | Where applied |
|---|----------|---------------|
| 6 | BM25 library: tantivy, behind a keyword-index interface | Article XI.3, VIII.1 |
| 7 | Flagged-answer UX: whole-answer banner plus a mark on each unverified source | Article VI.3 |
| 8 | Tools: `git blame` and `git log` only in v1 | Article V.2 |
| 9 | CI gating: passing tests is required to merge; required suite is deterministic and model-free | Article IX.7 |
| 10 | Generator inference via llama.cpp `llama-server` only (pinned release and GGUF checksum, cross-platform); mlx-lm not used | Article VIII.2 |
| 11 | TDD cycle (create test, red, code until green, refactor) is mandatory | Article IX.3 |
| 12 | Query-time freshness: online pipeline calls one public offline `ensure-current` entry point before answering (the only permitted online-to-offline write path) | Article II.2, III.2 |

**Deferred**

| # | Question | Notes |
|---|----------|-------|
| 13 | Evaluation repo and question set | Not decided; the team is building first. This does not block building, but Article VII.1 blocks tuning retrieval parameters, prompts, or models until it exists, and no results may be reported before then. |

## Appendix B: Traceability (diagram node → articles)

| Component | Governing articles |
|-----------|--------------------|
| Repo scanner (tree-sitter + GitPython) | II, III |
| Code-aware embedder | II.4, VIII |
| Vector store (Chroma/HNSW) / Keyword index (BM25) | II.3, III.3, XI.3 |
| Hybrid retriever | IV.1, IV.2 |
| Re-ranker (cross-encoder) | IV.3 |
| Agent/Generator | I, V.1, VII.4, VIII |
| "Enough context?" decision (round < 3) | V.1 |
| Verifier tool (git blame/log, cached) | V.2–V.5 |
| Citation checker → F / G | VI |
