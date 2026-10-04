# Sprint 1 Summary: Offline Indexing Pipeline (Spec 001)

**Status:** Complete. All tasks T0.1–T10.2 implemented test-first, committed as
test-then-implementation pairs (92 commits total).

## Verification

- Required suite: **134 passed** via `pytest -m "not model"` — deterministic,
  network-blocked (socket guard in `tests/conftest.py`), CPU-only, stub embedder.
- Model suite (local, `pytest -m model`): **4 passed** (T10.1 dimension /
  determinism / batch-parity / NL retrieval, T10.2 end-to-end smoke).
- Consistency check (`check_consistency`) asserted green in every integration test.
- No skipped/xfail tests. `mlx-lm` absent. All dependencies pinned in
  `requirements.txt`.

## What was built (by slice)

| Slice | Contents |
|---|---|
| S0 | Package skeleton, typed `codecompass.toml` loader, core models (`Chunk`, `ChangeSet`, `IndexMeta`, `RunReport`), scripted fixture-repo builder, deterministic `StubEmbedder` + in-memory store fakes, socket-blocking fixture, CI running the required suite |
| S1 | `GitSource`: HEAD validation, `--no-renames` change sets, blob reads/sizes from the object DB (never the work tree), symlink/submodule flagging, ancestry checks |
| S2 | Cheap-first exclusions: path/dir patterns, size limit, NUL-byte binary sniff, non-code gate, per-rule skip counts, lazy source wiring (no reads for excluded/oversize paths) |
| S3 | Structure-aware chunking: token sizing, sha256 chunk ids (line-number-free, so unchanged chunks keep ids), tree-sitter chunker (Python, JS/TS/TSX, Java) with class→header+methods and block-level oversize splits, CRLF-faithful line-window fallback, dispatcher that never fails a run |
| S4 | tantivy `KeywordIndex` (exact-identifier lookup verified first), Chroma cosine `VectorStore`, id-set + per-path consistency check |
| S5 | Atomic `meta.json`, embedder-identity compatibility gate, single-writer file lock with timeout |
| S6 | Single-path `orchestrator`: full build == incremental from empty; length-sorted batched embedding; lazy embedder factory; invalid input writes nothing |
| S7 | Incremental updates with vector reuse, incremental≡fresh property test, crash journal with revert-scenario recovery, history-rewrite rebuilds, config-fingerprint rebuilds, metadata-only advance |
| S8 | Public API (`ensure_current`, `status`, `open_index`, `check_consistency`): O1 fast path with no heavy imports, failure/locked statuses, read-only handles, exact export surface |
| S9 | Human + JSON run reports with stage timings and per-rule skip counts, `runs/` persistence, read-only `dry_run`, `index`/`status`/`check` CLI |
| S10 | Lazy `CodeEmbedder` (sentence-transformers, pinned model revision `516f4baf…`), real-embedder smoke test |

## Design decisions and deviations (all documented in code)

1. **Tantivy tombstones kill same-run re-adds.** Deletes are committed before
   inserts (two keyword commits when a run has both).
2. **AC-2.6 vs O8:** incremental runs must equal fresh builds *including* chunk
   `commit_sha`, so every advancing run re-stamps vector metadata (no re-embed,
   no keyword churn). T7.7 therefore scopes "no store write" to content writes.
3. **O1 fast path:** `ensure_current` imports no stores/models when current
   (test-enforced); `check_consistency` is lazily re-exported to preserve this.
4. **tantivy defaults already preserve** `snake_case`, dotted, and `E1234`
   identifiers — no custom pre-tokenizer needed (plan risk R1 closed).
5. **transformers v5 cannot load the pinned model's remote code** — pinned to
   `transformers==4.57.6` / `sentence-transformers==5.1.2`.
6. **Config-vs-instance embedder identity:** tests pass a `StubEmbedder`
   instance with the default (jina) config; the compatibility gate compares
   index identity against the *instance*. Production (T10 factory path) passes
   matching pairs. Unify if this ever causes confusion.
7. **Memory tradeoff:** all chunking/embedding completes before any store
   mutation (failure atomicity for T8.3), so one run's vectors are held in
   memory. Revisit bounded-memory batching (O9) with measurements per C6.

## How to run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -m "not model"   # required suite
.venv/bin/python -m pytest -m model         # local only (downloads ~600MB once)
.venv/bin/python -m codecompass.offline.cli index <repo> --embedder stub
```
