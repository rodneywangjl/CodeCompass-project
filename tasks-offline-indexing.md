# Tasks 001: Offline Indexing Pipeline

**Implements:** Plan 001 / Spec 001 | **Constitution:** v1.2.0

## How to use this list

Do **one task at a time, in order** (respect "Depends on"). Every task follows the constitution's TDD cycle (Article IX.3):

1. **Write the tests listed under "Tests first".** Run them and show that they fail for the expected reason (missing behaviour, not a typo or import error). **Stop. A human approves the tests.**
2. Write the minimum code to satisfy the tests. Re-run and fix the code until **all** pass.
3. Refactor with tests green. Run the full required suite: `pytest -m "not model"`.
4. Commit the tests first, then the implementation (two commits, in that order).

**Never edit an approved test to make it pass.** If a test looks wrong, stop and raise it.
**Stay inside "Touches".** If another file needs to change, stop and ask.
**Done when** always includes: the task's tests pass, the full required suite is green, no skipped or xfail tests without a written reason, no new unpinned dependencies.

Paths are under `codecompass/offline/` (code) and `tests/offline/` (tests) unless stated. "Fixture repo" means the scripted git repository from T0.4.

---

## S0: Skeleton and test support

**T0.1 Repo skeleton and tooling**
- Goal: package layout from the plan, pinned `requirements.txt`, pytest config with a registered `model` marker and strict markers.
- Tests first: package imports; `pytest --markers` lists `model`; an unregistered marker fails the run.
- ACs: none (enables the rest). | Touches: `pyproject.toml`/`pytest.ini`, `requirements.txt`, package `__init__` files. | Depends on: none.

**T0.2 Config loader**
- Goal: load and validate `codecompass.toml` into typed config (FR-17).
- Tests first: defaults applied when keys are missing; overrides honoured; unknown key rejected; `target_tokens > hard_max_tokens` rejected; relative paths resolved; nothing hard-coded (a test greps that model names appear only in config defaults).
- ACs: FR-17. | Touches: `config.py`. | Depends on: T0.1.

**T0.3 Core models**
- Goal: `Chunk`, `ChunkMode`, `ChangeSet`, `IndexMeta`, `RunReport` dataclasses with validation.
- Tests first: a chunk requires id, text, repo-relative forward-slash path, start ≤ end, language, symbol (or none), commit sha; backslash paths rejected; `ChangeSet` holds added/modified/deleted.
- ACs: AC-3.2 (shape). | Touches: `models.py`. | Depends on: T0.1.

**T0.4 Fixture-repo builder**
- Goal: a test helper that scripts a git repo: add, modify, delete, rename, rename+modify, binary file, `.env`, ignored file, untracked file, oversize function, syntax-error file, unsupported-language file, history rewrite.
- Tests first: builder returns the expected commit shas and file contents at each commit; rewrite scenario makes the old sha unreachable.
- ACs: enables most. | Touches: `tests/support/fixture_repo.py`. | Depends on: T0.1.

**T0.5 Stub embedder and in-memory fakes**
- Goal: deterministic `StubEmbedder` (small hash-derived vectors) and in-memory fakes of the vector store and keyword index for unit tests.
- Tests first: same text gives the same vector; different text differs; fixed dimension; batch result order matches input order; fakes obey the store protocols (add, delete by path, ids).
- ACs: enables Article IX.7. | Touches: `tests/support/`. | Depends on: T0.3.

**T0.6 Network-free required suite and CI**
- Goal: a pytest fixture that blocks network sockets for non-`model` tests, and a CI workflow running `pytest -m "not model"` on Linux.
- Tests first: a test that tries to open a socket fails under the fixture; a test marked `model` is deselected by default in CI.
- ACs: Article IX.7. | Touches: `tests/conftest.py`, `.github/workflows/`. | Depends on: T0.1.

## S1: Git source

**T1.1 Repo validation and HEAD**
- Tests first: non-git path raises a clear error; repo with zero commits raises a clear error; `head_sha` returns the commit sha; detached HEAD works; uncommitted edits do not change `head_sha`.
- ACs: AC-1.4, 1.5. | Touches: `git_source.py`. | Depends on: T0.4.

**T1.2 Change set**
- Tests first: added, modified, deleted detected; rename appears as one delete plus one add (rename detection off); diff from `None` (empty tree) lists every file; a file modified then reverted across the range is not listed; a directory move lists deletes and adds.
- ACs: AC-2.1, 2.4. | Touches: `git_source.py`. | Depends on: T1.1.

**T1.3 Blob reads and sizes**
- Tests first: `read_blob` returns committed content, not working-tree edits; untracked and git-ignored files are never visible; `blob_size` returns size without reading content; CRLF bytes preserved; unicode paths work; symlink entries are flagged and not followed; submodule entries are flagged.
- ACs: AC-6.5, edge cases (C5). | Touches: `git_source.py`. | Depends on: T1.1.

**T1.4 Ancestry**
- Tests first: `is_ancestor` true for a parent, false for an unrelated or rewritten commit; an unresolvable sha (missing, shallow clone) returns false, not an exception.
- ACs: AC-2.7 (detection). | Touches: `git_source.py`. | Depends on: T1.1.

## S2: Exclusions

**T2.1 Pattern and directory rules**
- Tests first: defaults exclude `.env*`, private keys and certificates, lockfiles, build and dependency directories, minified bundles; custom rules work; every exclusion reports which rule matched.
- ACs: AC-6.1, 6.2. | Touches: `exclusions.py`. | Depends on: T0.2.

**T2.2 Size limit and binary detection**
- Tests first: over-limit file skipped with a reason; NUL-byte content detected as binary even with a source extension; text with unicode is not mistaken for binary.
- ACs: AC-6.3, 6.4. | Touches: `exclusions.py`. | Depends on: T2.1.

**T2.3 Non-code classification**
- Tests first: markdown, text, JSON and YAML classified `non-code`; unsupported-language source files are included (fallback), not skipped; the source-extension set comes from config.
- ACs: AC-6.7. | Touches: `exclusions.py`. | Depends on: T2.1.

**T2.4 Cheap-first decision pipeline**
- Tests first: one `classify` call returns include or a skip reason with counts by rule; a spy source shows the blob is **not read** when the path is excluded and **not read** when the size limit fails; order is path, then size, then binary sniff, then non-code.
- ACs: AC-6.2, O6. | Touches: `exclusions.py`. | Depends on: T2.2, T2.3, T1.3.

## S3: Chunking

**T3.1 Token sizing**
- Tests first: token counts come from an injected tokenizer; batch counting equals per-item counting; policy reports `fits`, `over_target`, `over_hard_max`.
- ACs: AC-3.3 (support). | Touches: `chunking/sizing.py`. | Depends on: T0.2.

**T3.2 Chunk ids and text hashes**
- Tests first: same path, symbol, occurrence and text give the same id on repeat runs; a line shift does not change an unchanged chunk's id; identical duplicate chunks in one file get distinct ids; text hash changes when text changes.
- ACs: AC-3.7, 3.2. | Touches: `chunking/ids.py` (or `models.py`). | Depends on: T0.3.

**T3.3 Python chunker**
- Tests first: functions, classes, methods, decorators attached to their function, module header (imports and constants) grouped; nested functions stay inside their parent; every chunk's text equals the file's lines at its range; every chunk boundary falls on a syntax node boundary; empty file yields zero chunks.
- ACs: AC-3.1, 3.2, 3.6, 3.8. | Touches: `chunking/registry.py`, `chunking/treesitter.py`. | Depends on: T3.1, T3.2.

**T3.4 Oversize splitting**
- Tests first: a class over the target becomes a header chunk plus one chunk per method; a long function splits at its top-level blocks; a leaf over the hard max splits into line windows; **property test**: over many generated files no chunk exceeds the hard max and ranges never overlap.
- ACs: AC-3.3. | Touches: `chunking/treesitter.py`. | Depends on: T3.3.

**T3.5 JavaScript, TypeScript and TSX chunker**
- Tests first: function declarations, arrow functions assigned to `const`, classes, methods, exports; JSX components; same range and boundary properties as T3.3.
- ACs: AC-3.1, 3.6. | Touches: `chunking/registry.py`. | Depends on: T3.4.

**T3.6 Java chunker**
- Tests first: classes, interfaces, enums, constructors, methods, nested classes; annotations stay with their method; same range and boundary properties.
- ACs: AC-3.1, 3.6. | Touches: `chunking/registry.py`. | Depends on: T3.4.

**T3.7 Fallback chunker**
- Tests first: line windows near the target size that prefer blank-line breaks; ranges accurate with CRLF and unicode; empty file yields zero chunks; windows never exceed the hard max.
- ACs: AC-3.4, 3.6, 3.8. | Touches: `chunking/fallback.py`. | Depends on: T3.1.

**T3.8 Dispatcher and failure handling**
- Tests first: a language with a grammar uses tree-sitter (`structured`); a language without one uses fallback (`fallback`); a syntax-error file does not crash and is chunked via partial parse or fallback with the mode recorded; a parser exception falls back instead of failing the run.
- ACs: AC-3.4, 3.5. | Touches: `chunking/__init__.py`. | Depends on: T3.5, T3.6, T3.7.

## S4: Stores

**T4.1 Keyword index (do the identifier test first, risk R1)**
- Tests first: searching `get_user_by_id`, a camelCase name, a dotted name, and an error code like `E1234` returns the chunk that contains it; `delete_paths` removes a path's chunks; `ids()` matches what was added; searching an empty index returns nothing; data persists after reopen.
- ACs: AC-4.1, 4.2, 4.4. | Touches: `stores/keyword.py`. | Depends on: T0.3.
- Note: if the identifier test fails with tantivy's built-in tokenizers, switch to our own identifier-preserving pre-tokenisation (plan D10), not to a different library.

**T4.2 Vector store**
- Tests first: add stores vector, text, and metadata; `ids()` and `count()` correct; `delete_paths` removes only that path's chunks; `vectors_for_paths` returns text hash to vector; cosine space configured; persists after reopen; a vector of the wrong dimension is rejected.
- ACs: AC-4.1, 4.2. | Touches: `stores/vector.py`. | Depends on: T0.3.

**T4.3 Consistency check**
- Tests first: equal id sets pass; an id missing from either side is reported with the side and path; per-path disagreement reported; the check returns an error status when they differ.
- ACs: AC-4.3, 4.5. | Touches: `stores/consistency.py`. | Depends on: T4.1, T4.2.

## S5: Metadata and locking

**T5.1 Index metadata**
- Tests first: write then read round-trips all fields (schema version, embedder identity, indexed commit, config fingerprint, last run time, journal); write is atomic (a simulated crash mid-write leaves the previous file valid); unknown schema version raises an error naming expected and found.
- ACs: AC-5.1, 5.4. | Touches: `meta.py`. | Depends on: T0.3.

**T5.2 Compatibility gate**
- Tests first: a different embedder id, revision, or dimension raises a typed error naming both; a matching identity passes.
- ACs: AC-5.3, FR-12. | Touches: `meta.py`. | Depends on: T5.1.

**T5.3 Writer lock**
- Tests first: second acquirer waits and succeeds after release; timeout raises `LockTimeout`; lock released when the holder process dies; a two-process test shows no overlap.
- ACs: AC-5.8 (part), C8. | Touches: `lock.py`. | Depends on: T0.2.

## S6: Full build

**T6.1 Orchestrator: build from an empty index**
- Tests first (stub embedder, real stores): on the fixture repo every included file is chunked and present in **both** stores; indexed commit equals HEAD; the id sets of both stores are equal; `.env`, binary, ignored, untracked, and non-code files are absent; the run returns a `RunReport` object.
- ACs: AC-1.1, 1.2, 1.3, 6.5. | Touches: `orchestrator.py`. | Depends on: T1.4, T2.4, T3.8, T4.3, T5.2, T5.3.

**T6.2 Embedding batches and lazy model**
- Tests first: the embedder receives batches no larger than the configured size; chunks are length-sorted for embedding but each vector lands on the right chunk id; the embedder factory is **never called** when there is nothing to embed.
- ACs: O4. | Touches: `embedding.py`, `orchestrator.py`. | Depends on: T6.1.

**T6.3 No writes on invalid input**
- Tests first: a non-repo path and a zero-commit repo raise the clear errors and create no index directory, no metadata, no lock file.
- ACs: AC-1.4, 1.5. | Touches: `orchestrator.py`. | Depends on: T6.1.

## S7: Incremental updates

**T7.1 Incremental update**
- Tests first: modified, deleted, renamed, and added files each leave the right chunks in both stores and no stale ones; unchanged files are **not read, parsed, or embedded** (spy counts); a second run at the same commit does no work and writes nothing.
- ACs: AC-2.1 to 2.5, FR-16. | Touches: `orchestrator.py`. | Depends on: T6.1.

**T7.2 Vector reuse**
- Tests first: after editing one function in a file with many, the embedder is called only for the changed chunk; the resulting index equals a fresh build.
- ACs: AC-2.2, 2.6, O3. | Touches: `orchestrator.py`, `stores/vector.py`. | Depends on: T7.1.

**T7.3 Incremental equals from-scratch (property test)**
- Tests first: generate random commit sequences (add, modify, delete, rename, rename+modify, revert, mode-only change, directory move); after every incremental run, ids, text, metadata, and vectors equal a fresh build at that commit.
- ACs: AC-2.6, FR-4. | Touches: tests only, plus fixes found. | Depends on: T7.2.

**T7.4 Journal and crash recovery**
- Tests first: inject a failure at each point (during embedding, after the vector delete, after the vector insert before the keyword insert, before the final commit); the indexed commit does not advance; a re-run converges to a fresh build with no stale or duplicate chunks; **revert scenario:** a run that half-processes commit B, then commit C reverts the file, still ends correct.
- ACs: AC-2.8, FR-5. | Touches: `orchestrator.py`, `meta.py`. | Depends on: T7.1.

**T7.5 Unreachable indexed commit**
- Tests first: after a history rewrite the run performs a full rebuild and the report states the reason; an unresolvable commit does the same.
- ACs: AC-2.7. | Touches: `orchestrator.py`. | Depends on: T7.1, T1.4.

**T7.6 Config fingerprint and newly excluded paths**
- Tests first: adding an exclusion rule removes that path's existing chunks from both stores on the next run; changing target tokens triggers re-chunking; an unchanged config does not trigger a rebuild; a rebuild reuses vectors for unchanged chunks.
- ACs: AC-6.6, plan D11. | Touches: `orchestrator.py`, `meta.py`. | Depends on: T7.2.

**T7.7 Metadata-only advance**
- Tests first: a commit touching only excluded or non-code paths advances the indexed commit without any store write.
- ACs: AC-2.1, O8. | Touches: `orchestrator.py`. | Depends on: T7.1.

## S8: Public API

**T8.1 Status**
- Tests first: reports `empty`, `current`, `stale` correctly; returns the metadata fields; makes no writes.
- ACs: AC-5.1, 5.2. | Touches: `__init__.py`. | Depends on: T5.1.

**T8.2 `ensure_current`: fast path and stale path**
- Tests first: when current it reads no source, writes nothing, takes no lock, and does not import the stores or the model; when stale it runs an incremental update and returns current.
- ACs: AC-5.6, 5.7, O1. | Touches: `__init__.py`, `orchestrator.py`. | Depends on: T7.1, T8.1.

**T8.3 `ensure_current`: failure and concurrency**
- Tests first: an embedding failure returns a failure status and leaves the existing index usable and unchanged; two concurrent callers: the second waits, re-checks, and finds nothing to do; a wait past the timeout returns a locked status; it never blocks forever.
- ACs: AC-5.8, C8. | Touches: `__init__.py`, `orchestrator.py`. | Depends on: T8.2, T7.4.

**T8.4 Read-only handles and export surface**
- Tests first: the package exports exactly `ensure_current`, `status`, `open_index`, `check_consistency` (plus types); returned handles have no write methods; opening with a mismatched embedder or schema fails with the typed errors.
- ACs: AC-5.3, 5.4, 5.5, Article II.2. | Touches: `__init__.py`. | Depends on: T8.2.

## S9: Report and CLI

**T9.1 Run report**
- Tests first: contains mode, from and to commits, counts (added, modified, deleted, skipped by rule, fallback-chunked, non-code), chunks added and removed, embedder and schema versions, per-stage timings; prints readable text and writes JSON.
- ACs: AC-7.1, 7.2. | Touches: `report.py`. | Depends on: T7.1.

**T9.2 Dry run**
- Tests first: lists the changes that would happen; makes no store writes, no metadata change, no lock file.
- ACs: AC-7.3. | Touches: `orchestrator.py`, `report.py`. | Depends on: T9.1.

**T9.3 CLI**
- Tests first: `index`, `index --full`, `index --dry-run`, `status`, `check` run against the fixture repo with correct exit codes (non-zero on failure or inconsistency).
- ACs: AC-7.x, AC-4.3. | Touches: `cli.py`. | Depends on: T9.2, T8.4.

## S10: Real embedder (local only, `model` marker)

**T10.1 Jina embedder**
- Tests first (`model`): loads the pinned revision; recorded dimension equals output dimension; two calls give identical vectors; batch and single results match within tolerance; sizing uses its tokenizer; a natural-language query finds a known chunk among fixture chunks.
- ACs: Article VIII.1, FR-12. | Touches: `embedding.py`. | Depends on: T6.2.

**T10.2 End-to-end smoke test**
- Tests first (`model`): `ensure_current` on a small real repository twice (second run is up to date); consistency check passes; the report's timings are saved to inform the performance target (C6).
- ACs: whole spec. | Touches: tests only. | Depends on: T10.1, T9.3.

---

## Completion checklist (spec "definition of done")

- [ ] Every P1 and P2 AC has an approved, passing test.
- [ ] `pytest -m "not model"` is green in CI with no network.
- [ ] `model` tests pass locally on the `dev` profile machine.
- [ ] Consistency check passes after every integration scenario.
- [ ] No skipped or xfail tests without a linked reason.
- [ ] All dependencies pinned; `mlx-lm` absent.
