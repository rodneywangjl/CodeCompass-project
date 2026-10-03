# CodeCompass: agent rules

CodeCompass is a RAG-based Q&A assistant over a git repository. Offline pipeline: scanner, chunker, embedder, Chroma vector store, tantivy BM25 index. Online pipeline: hybrid retrieval, re-ranker, generator, verifier tool, citation checker. This repo is built **spec-driven and test-first**.

## Source of truth (read before coding)

- `docs/constitution.md`: non-negotiable rules. It is loaded for every session via `opencode.json`. Follow it.
- `docs/specs/001-offline-indexing/spec.md`: what to build and the acceptance criteria (ACs).
- `docs/specs/001-offline-indexing/plan.md`: how it is built (modules, interfaces, design decisions).
- `docs/specs/001-offline-indexing/tasks.md`: the ordered task list. Work comes from here.

These files are not read automatically. When given a task, read the constitution, the task in `tasks.md`, and the spec and plan sections it references.

## How to work

1. Do **one task at a time**, only the one you are asked to do. Respect its "Depends on" and "Touches".
2. **Tests first.** Write the tests listed under the task's "Tests first". Run them and show that they fail for the expected reason. Then **stop and wait for approval** before writing any implementation.
3. After approval, write the minimum code to pass. Re-run and fix the **code** until all tests pass. Then refactor with tests green.
4. Run the full required suite before finishing: `pytest -m "not model"`.
5. Commit the tests first, then the implementation, as separate commits.

## Hard rules

- **Never edit, weaken, skip, delete, or xfail an approved test to make it pass.** If a test seems wrong, stop and say so.
- Do not add features, files, or refactors outside the task's "Touches".
- Do not add or upgrade a dependency without asking. All dependencies are pinned. Do not use `mlx-lm` or MLX.
- Respect module boundaries: only `codecompass/offline/__init__.py` is exported to the online pipeline; `ensure_current` is its only write-capable export.
- Required tests must be deterministic and must not need network access, a GPU, `llama-server`, or a model download. Use the stub embedder. Tests that need a real model use the `model` marker.
- Models, thresholds, sizes, and paths come from config, never hard-coded.
- If the spec is ambiguous, mark it `[NEEDS CLARIFICATION]` and ask. Do not guess.
- Do not modify `docs/constitution.md`. Amendments are made by a separate, reviewed pull request.

## Environment

Python 3.11+. Generator inference uses llama.cpp only (online pipeline, not this task list). Embedder: `jinaai/jina-embeddings-v2-base-code` at a pinned revision.
