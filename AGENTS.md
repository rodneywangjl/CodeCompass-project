# CodeCompass: agent rules

CodeCompass is a RAG-based Q&A assistant over a git repository. Offline pipeline: scanner, chunker, embedder, Chroma vector store, tantivy BM25 index. Online pipeline: hybrid retrieval, re-ranker, generator, verifier tool, citation checker. This repo is built **spec-driven and test-first**.

## Source of truth (read before coding)

- `docs/constitution.md`: non-negotiable rules. Follow it. It is **not** loaded automatically by any tool — read it yourself before writing any code or tests.
- `docs/specs/001-offline-indexing/spec.md`: what to build and the acceptance criteria (ACs).
- `docs/specs/001-offline-indexing/plan.md`: how it is built (modules, interfaces, design decisions).
- `docs/specs/001-offline-indexing/tasks.md`: the ordered task list. Work comes from here.
- `docs/summary/SPRINT1-SUMMARY.md`: what was built in Sprint 1, verification results, and design deviations. Read it for context and to avoid redoing or contradicting finished work; it is a **record, not authority** — where it and the spec or plan disagree, the spec and plan win.

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

## 4.1 Commit trailer

Add one line to the message of any commit that contains AI-assisted work, in the form below. This follows the Assisted-by convention used by the Linux kernel and LLVM.

```
Assisted-by: <tool> (<model>)
```

For example:
```
Add document chunking to the retrieval pipeline

Split source documents into overlapping chunks before embedding.

Assisted-by: Claude Code (Claude Sonnet 4.5)
```

If your tool adds its own attribution line, such as `Co-Authored-By`, you may use that instead.

## 4.2 AI use log

Each team member must keep a log file in an `ai-log` folder at the top level of the repository, named after the member.

```
ai-log/
  arjun-kumar.md
  nurul-huda.md
  wei-ling.md
```

Add an entry for each significant use of an AI tool. One entry per task is sufficient; you do not need to record every prompt.
- Add entries as you work.
- Commit each entry with the work it describes.
- Each entry has a heading with the date and a short title, three fixed fields, and three short free-text sections.
- The most important part of an entry is how you checked the output.

For example:

```markdown
# AI Use Log: Wei Ling
## 2026-10-12 · Retrieval pipeline skeleton
- **Tool (model):** Claude Code (Claude Sonnet 4.5)
- **Files:** src/retrieval/pipeline.py, tests/test_chunking.py
- **Outcome:** Changed
### What I asked for
A skeleton for the retrieval pipeline: document loading, chunking,
embedding and a top-k query function.
### How I checked it
Ran the unit tests, which passed. Reviewing the chunking logic by hand
showed that the overlap was measured in characters rather than tokens,
so chunks near the limit were silently cut short.
### What I kept or changed
Kept the structure and the loader. Rewrote the chunk-overlap handling to
count tokens and added a test for chunks at the size limit.
```

