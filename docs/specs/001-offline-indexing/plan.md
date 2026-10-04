# Plan 001: Offline Indexing Pipeline

**Implements:** Spec 001 (Offline Indexing Pipeline) | **Constitution:** v1.2.0 | **Status:** Draft for review

> The spec says what the pipeline must do. This plan says how we will build it, in the leanest way that satisfies every acceptance criterion (AC) without adding components the constitution doesn't allow (Article XI).

---

## 1. Design in one page

One pipeline, one code path. A **full build is just an incremental run from an empty index**, so there is only one flow to write and test, and AC-2.6 (incremental equals from-scratch) is easier to guarantee.

```
ensure_current(repo)
  ├─ read HEAD sha, read meta.json ─── equal? ──► return CURRENT   (fast path: no lock, no heavy imports)
  └─ differ / empty:
       acquire lock (wait up to timeout, then re-check)
       ChangeSet = git diff (indexed_commit → HEAD), --no-renames, paths only
       filter: exclusions → size → binary → non-code
       journal: record target commit + touched paths in meta.json
       for each batch of files:
           reuse vectors of unchanged chunk text  (look up before delete)
           delete old chunks of these paths from BOTH stores
           read blob at HEAD → chunk (tree-sitter | fallback)
           embed only chunks without a reusable vector (batched)
           insert into vector store and keyword index
       commit keyword index once
       set indexed_commit = HEAD, clear journal, write run report
       release lock → return CURRENT (or FAILED, index left usable)
```

## 2. Technology choices (fixed by the constitution unless noted)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | `tomllib` for config; same language as the online side |
| Git access | GitPython | Diff and blob reads from the git object database, never the working tree |
| Parsing | `tree-sitter` with a pinned grammar bundle (e.g. `tree-sitter-language-pack`) | One dependency for Python, JS, TS/TSX, Java. *Plan decision.* |
| Embedder | `jinaai/jina-embeddings-v2-base-code`, pinned revision | Local, `trust_remote_code`, via `transformers`/`sentence-transformers` (Article VIII.1) |
| Vector store | Chroma, persistent, cosine space, HNSW | One collection `chunks` |
| Keyword index | tantivy (Python bindings) behind `KeywordIndex` interface | Article XI.3 |
| Lock | `filelock` | Cross-platform file lock. *Plan decision.* |
| Tests | pytest | Article IX.7 |

All versions pinned in `requirements.txt`. No mlx-lm or generator dependency exists in the offline package.

## 3. Package layout

```
codecompass/offline/
  __init__.py        public API only: ensure_current, status, open_index, check_consistency
  config.py          load/validate codecompass.toml → typed config
  models.py          Chunk, ChangeSet, IndexMeta, RunReport (plain dataclasses)
  git_source.py      repo adapter: head_sha, is_ancestor, diff(), read_blob(), blob_size()
  exclusions.py      rules: patterns, dirs, size limit, binary sniff, non-code
  chunking/
    registry.py      extension → language → structural node types
    treesitter.py    structure-aware chunker
    fallback.py      line-window chunker
    sizing.py        token counting (embedder tokenizer) and size policy
  embedding.py       Embedder protocol + JinaEmbedder (lazy model load)
  stores/
    vector.py        VectorStore (Chroma wrapper)
    keyword.py       KeywordIndex (tantivy wrapper)
  meta.py            meta.json read/write (atomic), compatibility checks
  lock.py            index lock with wait/timeout
  orchestrator.py    the flow in section 1
  report.py          RunReport build, print, write JSON
  cli.py             `index`, `index --dry-run`, `status`, `check`
tests/
  support/           fixture-repo builder, StubEmbedder, in-memory fakes
  offline/           unit + integration tests mirroring the modules
```

**Boundary rule (Article II.2):** only `__init__.py` exports anything to the online pipeline. `ensure_current` is the single write-capable export; `open_index` returns read-only handles; `status` and `check_consistency` are read-only.

## 4. Interfaces (the contracts tests are written against)

```python
class Embedder(Protocol):
    identity: EmbedderIdentity           # model id, revision, dimension
    def embed(self, texts: list[str]) -> list[list[float]]: ...   # batched, deterministic

class VectorStore(Protocol):
    def vectors_for_paths(self, paths) -> dict[str, list[float]]  # text_hash -> vector (for reuse)
    def delete_paths(self, paths: list[str]) -> None
    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None
    def ids(self) -> set[str]
    def count(self) -> int

class KeywordIndex(Protocol):
    def delete_paths(self, paths: list[str]) -> None
    def add(self, chunks: list[Chunk]) -> None
    def commit(self) -> None
    def search(self, text: str, limit: int) -> list[str]           # chunk ids
    def ids(self) -> set[str]

class Chunker(Protocol):
    def chunk(self, path: str, content: str, commit_sha: str) -> tuple[list[Chunk], ChunkMode]  # mode: structured | fallback

class GitSource(Protocol):
    def head_sha(self) -> str | None
    def is_ancestor(self, old: str, new: str) -> bool
    def diff(self, old: str | None, new: str) -> ChangeSet          # added/modified/deleted paths
    def blob_size(self, sha: str, path: str) -> int
    def read_blob(self, sha: str, path: str) -> bytes
```

Production code depends only on these protocols. Tests supply a deterministic `StubEmbedder` (hash-derived small vectors) and, for unit tests, in-memory fakes of both stores, so the required suite needs no model, GPU, or network.

## 5. Key design decisions

**D1. Change detection.** `git diff --name-status --no-renames <indexed>..<HEAD>`. With rename detection off, a rename appears as one delete plus one add, which is exactly AC-2.4 and removes the "renamed and modified" edge case. An empty index diffs against the empty tree, which makes the full build the same code path.

**D2. Read from git, not the disk.** File content comes from the HEAD commit's object, so uncommitted edits and untracked files can never leak in (spec edge case) and files git ignores are never present (AC-6.5).

**D3. Chunk identity.** `id = sha256(path | qualified_symbol | occurrence_index | text_hash)` truncated. Deterministic (AC-3.7), unchanged chunks keep their id even if their line numbers shift, and identical duplicate chunks in one file stay distinct via `occurrence_index`.

**D4. Chunking algorithm (tree-sitter).**
1. Parse with a cached per-language parser.
2. Collect top-level units from the language registry (functions, classes, methods, plus the module-level residue such as imports and constants grouped as a header unit).
3. A unit at or under the target size becomes one chunk. A class over the target becomes a header chunk (signature, docstring, fields) plus one chunk per method.
4. A leaf unit over the target splits at its top-level child blocks; a leaf over the embedder's hard limit splits into line windows. No overlap in Sprint 1, so line ranges never overlap.
5. Stored chunk text is the exact source text of `[start, end]` (AC-3.6). The embedder receives that same text; adding path or symbol context to the embedded text is a retrieval-quality experiment and is **deferred until an evaluation set exists** (Article VII.1).

**D5. Fallback.** Unsupported-language source files, parse failures, and files with syntax errors the parser cannot recover use line windows: accumulate lines to the target size, preferring to break at blank lines. They are flagged `fallback` in the report (AC-3.4, 3.5).

**D6. Crash safety with a touched-paths journal.** Before writing anything, `meta.json` records `in_progress = {target_commit, touched_paths}`. `indexed_commit` only advances after both stores are finished. On the next run the change set is the **union** of the fresh diff and the journal's paths. The union matters: if run 1 half-processed a file at commit B and the file was reverted by commit C, a plain A-to-C diff would not list it and the index would silently keep B's version. Re-processing is safe because the per-path operation is "delete everything for this path from both stores, then insert" (AC-2.8, FR-5).

**D7. Single writer.** An exclusive file lock guards all writes. A second caller waits up to the configured timeout, then re-checks currency (usually nothing left to do); on timeout it returns an "index is locked" status (C8, AC-5.8). The fast path takes no lock.

**D8. Consistency check.** Compares the id sets from both stores and verifies per-path agreement; used at the end of integration tests and exposed as `check` (AC-4.3, 4.5).

**D9. Compatibility gate.** `meta.json` holds schema version and embedder identity (id, revision, dimension). Opening or writing with a mismatch raises a typed error naming expected and found values (AC-5.3, 5.4).

**D10. Keyword tokenisation (risk R1).** AC-4.4 needs identifiers like `get_user_by_id` to match whole. Task S4 starts with a failing test for exactly that. If tantivy's built-in tokenizers split such identifiers, we pre-tokenise in our own code (identifier-preserving, lowercase) and index with a simple whitespace tokenizer. We do not add sub-token splitting (snake/camel) in Sprint 1; that is a retrieval-quality change for after evaluation exists.

## 6. Optimisations (and what each must not break)

| # | Optimisation | Saves | Must not break |
|---|---|---|---|
| O1 | **Fast path in `ensure_current`:** read HEAD and `meta.json`, compare, return. No lock, no store or model imports. | Nearly all of the cost of the per-question check | AC-5.7 (reads no source, writes nothing) |
| O2 | **Diff only, from the object database:** one `git diff` for paths, blob reads on demand, no checkout. | Scanning and disk I/O | D2 (committed content only) |
| O3 | **Vector reuse for unchanged chunks.** Before deleting a modified file's old chunks, fetch their `text_hash → vector`. After re-chunking, reuse a vector whenever the text hash matches and embed only the rest. Records are still deleted and re-inserted, only the *embedding computation* is skipped. | The dominant cost (embedding): a one-line edit re-embeds one chunk, not the whole file | AC-2.2, AC-2.6 (output identical to a fresh build; valid because the pinned embedder is deterministic and an embedder change is refused by D9) |
| O4 | **Batched, length-sorted embedding** in inference mode, batch size and device from config, model loaded lazily and only if there is something to embed. | Padding waste, GPU/CPU idle time, startup cost on no-op runs | Output order (results are mapped back to chunk ids) |
| O5 | **Batched store operations:** one delete per batch for all its paths, bulk add, a single tantivy commit per run. | Round trips and index segment churn | D6 ordering (delete before insert, journal first) |
| O6 | **Cheap filters first:** path rules, then blob size from the git object (no read), then a NUL-byte sniff on the first bytes, then non-code check, and only then parse. | Reading and parsing files that will be skipped | AC-6.2 to 6.4 (skips still counted in the report) |
| O7 | **Parser and tokenizer reuse:** one parser per language, one fast tokenizer instance, batch tokenisation for sizing. | Per-file setup cost | None |
| O8 | **Metadata-only advance** when a diff contains only excluded or non-code paths: update `indexed_commit` without touching either store. | Needless store work on doc-only commits | AC-2.1, 2.5 |
| O9 | **Bounded memory:** files are processed in batches (config), so peak memory is one batch of chunks and vectors, not the repo. | Memory on large repos | None |

**Deliberately not optimised yet:** no multiprocessing, threads, or async. Embedding dominates runtime and the sources of parallelism add failure modes (GIL, store write contention). The run report records per-stage timings (parse, chunk, embed, store write), and we revisit with measurements (C6).

## 7. Data layout and configuration

```
<index_dir>/                 # default: user app-data dir / codecompass / <repo-id>   (C4)
  meta.json                  # schema_version, embedder{id,revision,dim}, indexed_commit,
                             #   last_run_at, in_progress{target_commit, touched_paths} | null
  vector/                    # Chroma persistent store
  keyword/                   # tantivy index
  runs/<timestamp>.json      # run reports (AC-7.2)
  index.lock                 # writer lock
```

`meta.json` is written atomically (temp file then rename). Chroma metadata per chunk: `file_path, start_line, end_line, language, symbol, commit_sha, text_hash`; the document is the chunk text. Stored paths are repo-relative with forward slashes on every OS.

`codecompass.toml` (all values from the spec's "configuration, not hard-coded" rule, FR-17):

```
[index]      dir
[chunking]   target_tokens=512  hard_max_tokens=<embedder limit>  batch_files
[files]      max_file_bytes  source_extensions  exclude_patterns  exclude_dirs
[languages]  treesitter = ["python","javascript","typescript","tsx","java"]
[embedder]   model  revision  device  batch_size
[lock]       timeout_seconds=120
```

## 8. Spec coverage map

| Spec items | Built in | Verified by |
|---|---|---|
| AC-1.x full build | `orchestrator` (empty-index diff) | integration, stub embedder |
| AC-2.1 to 2.5, 2.7 | `git_source`, `orchestrator` | unit (change set), integration |
| AC-2.6 equivalence, AC-2.8 crash | D6 journal, per-path delete+insert | integration: random commit sequences, injected failure |
| AC-3.x | `chunking/*` | unit per language and fallback, property tests (ranges, determinism, no mid-unit cuts) |
| AC-4.x | `stores/*`, D8, D10 | unit (fakes) and integration (real Chroma and tantivy, stub vectors) |
| AC-5.1 to 5.4, 5.6 to 5.8 | `meta`, `lock`, `__init__.ensure_current` | unit and integration (current, stale, failing, concurrent) |
| AC-5.5 | `__init__` export surface | test that only the allowed names are exported |
| AC-6.x | `exclusions` | unit, fixture repo |
| AC-7.x | `report`, `cli` | unit, CLI smoke test |
| Real embedder | `JinaEmbedder` | `model`-marked local tests only |

## 9. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | tantivy tokenizers split identifiers | Failing test first (D10); pre-tokenise fallback |
| R2 | Grammar node names differ per language | Registry holds per-language node types; each language has fixture files and its own chunker tests |
| R3 | `trust_remote_code` model load fails offline or breaks on a library upgrade | Pin revision and library versions; `model`-marked smoke test; cache model locally |
| R4 | Chroma delete-by-path slow on large collections | Batched deletes; measure via the run report before changing anything |
| R5 | File locks behave differently on Windows | `filelock` plus a two-process test on each OS in CI where available |
| R6 | History rewrite or shallow clone breaks `is_ancestor` | Treat any failure to resolve the indexed commit as "not reachable" and do a full rebuild with the reason in the report (AC-2.7) |

## 10. Build order (each slice starts with failing tests, Article IX.3)

| Slice | Delivers | Main ACs |
|---|---|---|
| S0 | Repo skeleton, config loader, `StubEmbedder`, fixture-repo builder, CI running the required suite | none (enables the rest) |
| S1 | `git_source`: head, ancestry, diff, blob read | 2.1, 2.7 (part) |
| S2 | `exclusions` | 6.1 to 6.5, 6.7 |
| S3 | Chunking: Python first, then JS/TS, Java, fallback, sizing | 3.1 to 3.8 |
| S4 | `VectorStore`, `KeywordIndex`, consistency check (R1 first) | 4.1 to 4.5 |
| S5 | `meta`, compatibility gate, `lock` | 5.1, 5.3, 5.4, 5.8 (lock) |
| S6 | Orchestrator: full build | 1.1 to 1.5 |
| S7 | Incremental, vector reuse (O3), journal, equivalence property test | 2.2 to 2.8, 6.6 |
| S8 | `ensure_current`, `status`, `open_index`, export surface | 5.2, 5.5 to 5.8 |
| S9 | Run report, dry-run, CLI | 7.1 to 7.3 |
| S10 | Real `JinaEmbedder` and `model`-marked tests | dimension and smoke test |

## 11. Constitution check

| Article | Compliance |
|---|---|
| II | Only `__init__` exports; `ensure_current` is the one write-capable entry; embedder identity gated by D9 |
| III | Incremental, delete-from-both first, structure-aware chunking, fallback, idempotence, exclusions all designed in (D1 to D8) |
| VIII | Model, revision, device, sizes are config; local; dependencies pinned; no mlx-lm |
| IX | Interfaces and slices are test-first; required suite is model-free |
| XI | No new components: Chroma, tantivy, one embedder, one lock, one JSON metadata file |

No conflicts found.

## 12. Next

Turn section 10 into a **task list**: each task names its failing tests first, the ACs it satisfies, and its definition of done.
