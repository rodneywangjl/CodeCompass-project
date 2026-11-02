# Spec 001: Offline Indexing Pipeline

**Project:** CodeCompass (SE201 G1-T1) | **Sprint:** 1 | **Status:** Approved for planning (all clarifications resolved)
**Constitution version:** 1.2.0 | **Constitution articles touched:** I, II, III, VIII, IX, XI (see "Constitution Check")

> This spec says **what** the offline pipeline must do and how we will know it works. It does not choose libraries, file layouts, or class designs beyond what the constitution already fixes; those belong in the plan.

---

## 1. Purpose

Turn a git repository into two searchable, mutually consistent indexes (a semantic vector index and a BM25 keyword index) that the online query pipeline can read. The pipeline runs per commit, reprocesses only what changed, and never leaves the two indexes disagreeing.

The pipeline covers every offline component in the architecture diagram:

`Git repository → Repo scanner (tree-sitter + GitPython, changed files only) → Code-aware embedder → Vector store (Chroma/HNSW)`
`Git repository → Repo scanner → Keyword index (BM25, tantivy)`

## 2. Scope

**In scope (Sprint 1)**
- Detecting which files changed between the last indexed commit and the current HEAD.
- Structure-aware chunking of source files.
- Embedding chunks with the pinned code embedder.
- Writing chunks to the vector store and the keyword index, and deleting stale chunks from both.
- Index metadata (embedder identity, schema version, last indexed commit) and an index-status read API.
- Exclusion rules (secrets, binaries, build output).
- A command-line entry point to run indexing, plus a run report.
- A small fixture repository and the test suite for all of the above.

**Out of scope (this spec)**
- Anything in the online pipeline: query embedding, retrieval, RRF merge, re-ranking, generation, verifier tool, citation checker.
- Indexing commit messages or PR discussions. Commit history reaches the generator only through the verifier tool (Article V).
- Evaluation repo, question set, and any quality tuning (deferred; Article VII.1).
- A web UI, authentication, multi-repository support, or hosted deployment.
- Triggering by a git hook. Indexing is triggered at query time (before each answer) and by a manual command (resolved, C2).
- Indexing non-code files (README, markdown, JSON/YAML config, text). They are skipped and counted in the run report (resolved, C3). This is deliberate, not only a Sprint 1 cut: CodeCompass infers what a program does from its code, and prose about the code goes out of date. The citation checker confirms that a passage was in context, not that it is true (constitution Article VI.5), so a stale document would be cited as valid evidence.

## 3. Terminology

- **Chunk:** the unit of retrieval: a contiguous piece of one file, aligned to code structure, with metadata.
- **Indexed commit:** the commit SHA whose file contents the indexes currently reflect.
- **Index set:** the vector store and keyword index treated together as one logical index.
- **Stale chunk:** a chunk whose file has since changed or been deleted in the repository.

## 4. User Stories and Acceptance Criteria

Priorities: **P1** = required for the sprint to be done, **P2** = should ship, **P3** = nice to have.

### US1 (P1): Build the index for a repository from scratch

*As a developer setting up CodeCompass, I want to point it at a git repository and build the full index, so that the assistant can answer questions about that repo.*

- **AC-1.1** Given a repository with no existing index, when indexing runs, then every non-excluded, supported source file at HEAD is chunked, embedded, and written to both indexes.
- **AC-1.2** Given a completed first run, then the recorded indexed commit equals HEAD's SHA.
- **AC-1.3** Given a completed first run, then the set of chunk ids in the vector store equals the set of chunk ids in the keyword index.
- **AC-1.4** Given a path that is not a git repository, when indexing runs, then it fails with a clear error and writes nothing.
- **AC-1.5** Given a repository with zero commits, when indexing runs, then it fails with a clear error and writes nothing.

### US2 (P1): Update the index incrementally after new commits

*As a developer, I want only changed files to be re-indexed after new commits, so that updates are fast and cheap.*

- **AC-2.1** Given an index at commit A and a repository now at commit B, when indexing runs, then only files added, modified, renamed, or deleted between A and B are processed; unchanged files are not read, parsed, or embedded.
- **AC-2.2** Given a modified file, then all of its previous chunks are removed from **both** indexes and its new chunks are written to both.
- **AC-2.3** Given a deleted file, then all of its chunks are removed from both indexes and none remain.
- **AC-2.4** Given a renamed file, then chunks under the old path are removed and chunks under the new path are added (rename is treated as delete plus add).
- **AC-2.5** Given a repository whose HEAD equals the indexed commit, when indexing runs, then no file is processed, no index write occurs, and the run report says the index is up to date.
- **AC-2.6** Given any sequence of commits, then after each indexing run the index set's contents are identical to what a fresh from-scratch build at that same commit would produce (same chunk ids, text, and metadata).
- **AC-2.7** Given the recorded indexed commit is no longer reachable from HEAD (e.g. history rewritten), when indexing runs, then the pipeline performs a full rebuild and the report states why.
- **AC-2.8** Given a run that fails partway (e.g. an exception during embedding), then the recorded indexed commit is **not** advanced, and re-running indexing converges to the correct state with no stale or duplicated chunks.

### US3 (P1): Structure-aware chunking

*As the online pipeline, I need chunks that follow code structure, so that retrieved text is meaningful and citable.*

- **AC-3.1** Given a supported-language file, then chunk boundaries fall on structural boundaries (function, method, class, module-level block) and **no chunk cuts a function or class in the middle** unless that unit exceeds the size limit (AC-3.3).
- **AC-3.2** Every chunk carries: chunk id, text, repo-relative file path, start line, end line, language, symbol name (or none for non-symbol chunks), and the commit SHA it was indexed at.
- **AC-3.3** Given a unit larger than the target chunk size, then it is split at the next-lower structural boundary (e.g. a class into its methods, a long function into its top-level blocks); no emitted chunk exceeds the embedder's input limit.
- **AC-3.4** Given a file that tree-sitter cannot parse, or a language with no configured grammar, then the file is chunked with the documented line-window fallback, is still indexed, and is listed in the run report as "fallback-chunked". It is never silently skipped.
- **AC-3.5** Given a file with syntax errors, then the pipeline does not crash and the file is indexed via the best available strategy (partial parse or fallback), with the run report noting it.
- **AC-3.6** Chunk line ranges are accurate: for every chunk, the text equals the file's content at `[start line, end line]` at the indexed commit.
- **AC-3.7** Chunk ids are deterministic: chunking the same file content at the same path twice yields the same ids.
- **AC-3.8** Empty files and files with no indexable content produce zero chunks without error.

### US4 (P1): Two indexes that always agree

*As the retrieval layer, I rely on the vector and keyword indexes describing the same chunks.*

- **AC-4.1** Every chunk written to the vector store is also written to the keyword index with the same id and text, and vice versa.
- **AC-4.2** The vector store holds, for each chunk, its vector and original text and metadata; the keyword index holds the chunk's text and id/metadata sufficient to map a keyword hit back to the same chunk record.
- **AC-4.3** A built-in consistency check compares the two indexes' chunk id sets and reports any difference. It exits with an error status when they differ.
- **AC-4.4** The keyword index supports exact-identifier lookup: searching for a function name, error code, or variable name present in a chunk returns that chunk.
- **AC-4.5** Given a mix of operations (add, modify, delete), then the consistency check passes after every run.

### US5 (P2): Index status and safe use by the online pipeline

*As the online pipeline, I need to know what the index contains and whether it is current or compatible.*

- **AC-5.1** Index metadata records: schema version, embedder model identifier and pinned revision, embedding dimensionality, last indexed commit SHA, and time of last successful run.
- **AC-5.2** A read-only status function returns that metadata plus whether the index is **current** (indexed commit equals repo HEAD), **stale** (different), or **empty** (never built).
- **AC-5.3** Given an index built with embedder X, when the pipeline is configured with embedder Y (different identifier or revision), then indexing and index opening refuse to proceed with a clear error (Article II.4).
- **AC-5.4** Given an index with an unknown or older schema version, then opening it fails with a clear error naming the expected and found versions.
- **AC-5.5** The offline pipeline exposes read access to both indexes without exposing scanner or chunker internals (Article II.2).
- **AC-5.6** The offline pipeline exposes one public `ensure-current` operation. It compares repo HEAD with the recorded indexed commit; if they differ it runs an incremental update, and it returns only when the index is current or has failed. It is the only write-capable operation the online pipeline is allowed to call (Article II.2).
- **AC-5.7** Given the index is already current, when `ensure-current` is called, then it reads no source file and writes nothing (it only compares commits), so calling it before every question is cheap.
- **AC-5.8** Given `ensure-current` fails (e.g. embedding error), then it returns a clear failure status and leaves the existing index usable and unchanged, so the online pipeline can answer from it and flag the answer as stale (Article III.2). It never blocks indefinitely.

### US6 (P2): Exclusions and secret safety

*As a team member, I need to be sure secrets and junk never enter the index.*

- **AC-6.1** An explicit, reviewable exclusion list (file name patterns and directories) is applied before any file is read for chunking. It ships with defaults covering at least: environment files (`.env*`), private keys and certificates, lockfiles, build and dependency directories, minified bundles, and binary files.
- **AC-6.2** Excluded files produce no chunks in either index, and the run report counts them by rule.
- **AC-6.3** Binary files are detected by content and skipped even if their extension is not on the list.
- **AC-6.4** Files over a configured maximum size are skipped and reported, not silently dropped.
- **AC-6.5** The repository's own ignore rules are respected (files git ignores are not indexed).
- **AC-6.6** Adding or editing an exclusion rule takes effect on the next run, and files newly excluded have their existing chunks removed from both indexes.
- **AC-6.7** Files that are not source code (e.g. markdown, plain text, JSON/YAML config) are skipped and counted as "non-code" in the run report. The set of source-code extensions is configuration. Source files in languages without a tree-sitter grammar are still indexed through the fallback (AC-3.4).

### US7 (P3): Observable runs

*As a developer, I want to see what a run did.*

- **AC-7.1** Each run produces a report with: mode (full, incremental, up-to-date, rebuild), from-commit and to-commit, counts of files added/modified/deleted/renamed/skipped/fallback-chunked, chunks added and removed, embedder and index schema versions, and elapsed time.
- **AC-7.2** The report is printed and also written to a machine-readable file.
- **AC-7.3** A dry-run mode lists what would change without modifying either index or the recorded commit.

## 5. Functional Requirements

| ID | Requirement | Satisfied by |
|----|-------------|--------------|
| FR-1 | The system **MUST** build a complete index from a repository at HEAD. | AC-1.1 to 1.5 |
| FR-2 | The system **MUST** detect changes between the last indexed commit and HEAD and process only changed files. | AC-2.1, 2.5 |
| FR-3 | On any file modification, deletion, rename, or newly excluded path, old chunks **MUST** be removed from both indexes first, before new chunks for that file are inserted. | AC-2.2 to 2.4, 6.6 |
| FR-4 | An incremental result **MUST** equal a from-scratch build at the same commit. | AC-2.6 |
| FR-5 | A failed run **MUST NOT** advance the recorded indexed commit; re-running **MUST** converge. | AC-2.8 |
| FR-6 | Chunking **MUST** follow code structure and **MUST NOT** cut functions or classes except when oversize. | AC-3.1, 3.3 |
| FR-7 | Unparseable or unsupported files **MUST** use a documented fallback and be reported. | AC-3.4, 3.5 |
| FR-8 | Each chunk **MUST** carry the constitution's required metadata fields. | AC-3.2, 3.6 |
| FR-9 | Chunk ids **MUST** be deterministic. | AC-3.7 |
| FR-10 | Vector and keyword indexes **MUST** hold the same chunk set at all times between runs, and a consistency check **MUST** exist. | AC-4.1 to 4.5 |
| FR-11 | The keyword index **MUST** support exact-token lookup of identifiers. | AC-4.4 |
| FR-12 | Index metadata **MUST** record embedder identity/revision, schema version, and indexed commit; mismatches **MUST** be refused. | AC-5.1 to 5.4 |
| FR-13 | The offline pipeline **MUST** expose a read-only status function and read access to the indexes. | AC-5.2, 5.5 |
| FR-18 | The offline pipeline **MUST** expose a single public `ensure-current` operation for the online pipeline to call before answering; it **MUST** be cheap when nothing changed and **MUST** fail safely. | AC-5.6 to 5.8 |
| FR-14 | Exclusion rules **MUST** be explicit, configurable, and applied before reading files; secrets **MUST NOT** be indexed. | AC-6.1 to 6.6 |
| FR-15 | Each run **MUST** produce a human- and machine-readable report; a dry-run mode **MUST** exist. | AC-7.1 to 7.3 |
| FR-16 | Indexing **MUST** be idempotent: running twice on the same commit leaves identical state. | AC-2.5, 2.6 |
| FR-17 | All model names, thresholds, sizes, and paths **MUST** be configuration, not hard-coded. | Article VIII.1 |

## 6. Edge Cases

Each of these needs at least one test:

- Initial run on a repository with a single commit; and with thousands of commits (only HEAD content matters).
- A commit that only changes file mode or whitespace.
- A file modified then reverted across commits between two index runs (net change is none).
- A file renamed **and** modified in the same range.
- A file that changes language by extension (e.g. `.js` to `.ts`).
- A directory deleted or moved with many files.
- A very large single function; a file with thousands of tiny functions.
- Unicode paths and file contents; CRLF line endings (line numbers must still be correct).
- A symlink inside the repo (must not escape the repo or loop).
- A submodule path (skipped and reported). (resolved, C5)
- Detached HEAD, and a repo with a dirty working tree: the index reflects the **committed** HEAD content, not uncommitted changes.
- Two runs (e.g. two concurrent questions each calling `ensure-current`) started on the same index: the second waits for the first, then re-checks currency and usually finds nothing to do; it never interleaves writes. If the wait exceeds a configured timeout it fails with an "index is locked" status (AC-5.8).

## 7. Non-Functional Requirements

- **Determinism:** same repo state plus same configuration produces the same index contents.
- **Locality:** nothing leaves the machine; the embedder runs locally (Article X.4, VIII.1).
- **Portability:** runs on Linux, Windows, and macOS. Path handling is repo-relative with forward slashes in stored metadata regardless of OS.
- **Isolation:** the required test suite runs with no GPU, no network, and no model download. A stub embedder returns deterministic vectors for tests; the real embedder is exercised only by `model`-marked tests (Article IX.7).
- **Performance:** no numeric target in Sprint 1. The run report records timings so a target can be set from measurements. (resolved, C6)
- **Dependencies:** libraries and the embedder revision are pinned (Article VIII.1, VIII.3); tantivy is used only behind the keyword-index interface (Article XI.3).

## 8. Key Entities

| Entity | Description | Key attributes |
|--------|-------------|----------------|
| Chunk | Retrievable unit of code | id, text, file path, start line, end line, language, symbol name, indexed-at commit SHA |
| Chunk vector | Embedding of a chunk | chunk id, vector, text, metadata (in the vector store) |
| Keyword record | BM25 entry for a chunk | chunk id, text, metadata (in the keyword index) |
| Index metadata | Describes the index set | schema version, embedder id + revision, dimensionality, last indexed commit, last run time |
| Change set | Files changed between two commits | added, modified, deleted, renamed paths |
| Run report | Outcome of one run | mode, commits, counts, skipped/fallback lists, versions, elapsed time |
| Exclusion rules | What is never indexed | patterns, size limit, defaults |

## 9. Constitution Check

| Article | How this spec complies |
|---------|------------------------|
| I (Grounding) | Accurate line ranges and commit SHAs in metadata make later citations verifiable (AC-3.2, 3.6). |
| II (Two pipelines, one contract) | Index schema and metadata are the only interface; embedder identity enforced (AC-5.1 to 5.5). |
| III (Index correctness) | Incremental updates, HEAD vs indexed commit, delete-from-both, structure-aware chunking, fallback, idempotence, exclusions (US2, US3, US6). |
| VIII (Models and environment) | Embedder pinned and recorded; config-driven; local; no paid service (FR-17, NFRs). |
| IX (Spec-driven, TDD) | Every AC is testable; tests are written first per task; required suite is model-free. |
| XI (Simplicity) | One pipeline, one keyword-index interface, no extra components. |

No conflicts with the constitution were identified.

## 10. Test Strategy (feeds the TDD cycle)

Every AC above becomes one or more tests written **before** the code that satisfies it (Article IX.3: create test, confirm red, code until green).

**Fixture repository.** A small git repository built by a test helper (not checked in as a binary) with scripted commits covering: initial files in each supported language, a modification, a deletion, a rename, a rename-plus-modify, an oversize function, a syntax-error file, an unsupported-language file, a binary file, a `.env` file, an ignored file, and a history rewrite scenario.

| Test level | What it covers |
|------------|----------------|
| Unit | Change-set computation, chunker per language, fallback chunker, chunk id determinism, exclusion rules, metadata validation, schema/embedder compatibility checks, run report |
| Integration (stub embedder) | `ensure-current` (current, stale, failing, concurrent), full build, incremental update, equivalence to from-scratch build (AC-2.6), crash-and-resume (AC-2.8), two-index consistency (AC-4.x), rename/delete handling, concurrent-run refusal |
| `model`-marked (local only) | Real embedder produces vectors of the recorded dimensionality; smoke test that a query vector finds a known chunk |

**Required regression tests** (from Article IX.5): a changed file leaves no stale chunks in either index; a mismatched embedder version is rejected.

**Definition of done for this spec:** all ACs for P1 and P2 stories have approved, passing tests; the full required suite is green in CI; the run report and consistency check work on the fixture repository; no skipped or xfail tests without a linked justification.

## 11. Clarifications (all resolved)

Resolved per Article IX.8, so planning can start.

| # | Question | Decision |
|---|----------|----------|
| C1 | Languages with tree-sitter chunking in Sprint 1 | Python, JavaScript, TypeScript (including TSX/JSX), Java. Every other source language uses the line-window fallback (AC-3.4). Adding a language later is a new spec. |
| C2 | How indexing is triggered | Before answering each question, via `ensure-current` (AC-5.6), per the project proposal. A manual command also exists. No git hook. |
| C3 | Non-code files | Not indexed in Sprint 1; only code files are chunked. Skipped and counted as "non-code" (AC-6.7). Reason: the code is the source of truth, and prose docs go stale yet would still pass the citation checker (Article VI.5). Docs may be added only by a later spec that shows, with the evaluation set (Article VII), that they help, and that labels them as documentation, never as code. |
| C4 | Index storage | A per-repository directory set in configuration. Default: the user's local application-data directory, in a subfolder keyed by a stable repository identifier. It is never inside the repository's tracked files, so indexing cannot dirty the working tree. |
| C5 | Submodules | Skipped and reported in the run report. |
| C6 | Performance target | None for Sprint 1. The run report records timings, and a target is set after the first measured runs. The up-to-date path of `ensure-current` must stay cheap (AC-5.7). |
| C7 | Target chunk size | About 512 tokens or fewer, counted with the embedder's own tokenizer; the hard ceiling is the embedder's input limit (AC-3.3). Both values are configuration. |
| C8 | Concurrent runs | A second run waits for the first, then re-checks and proceeds. The wait timeout is configuration (default 120 seconds); on timeout it fails with an "index is locked" status (AC-5.8). |
| C9 | Branch indexed | Whatever HEAD points to in the repository passed in. No branch selection in Sprint 1. |

## 12. What Comes Next

1. Write the **plan** (module boundaries, interfaces for the generator-free parts: scanner, chunker, embedder, vector store, keyword index, orchestrator; data layout; configuration).
2. Break the plan into **tasks**, each tied to ACs and each starting with its tests.
