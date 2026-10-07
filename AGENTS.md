# CodeCompass: agent rules

CodeCompass is a RAG-based Q&A assistant over a git repository. Offline pipeline: scanner, chunker, embedder, Chroma vector store, tantivy BM25 index. Online pipeline: hybrid retrieval, re-ranker, generator, verifier tool, citation checker. This repo is built **spec-driven and test-first**.

## Source of truth (read before coding)

- `docs/constitution.md`: non-negotiable rules. Follow it. It is **not** loaded automatically by any tool — read it yourself before writing any code or tests.
- `docs/specs/001-offline-indexing/spec.md`: what to build and the acceptance criteria (ACs).
- `docs/specs/001-offline-indexing/plan.md`: how it is built (modules, interfaces, design decisions).
- `docs/specs/001-offline-indexing/tasks.md`: the ordered task list. Work comes from here.
- `docs/summary/SPRINT1-SUMMARY.md`: what was built in Sprint 1, verification results, and design deviations. Read it for context and to avoid redoing or contradicting finished work; it is a **record, not authority** — where it and the spec or plan disagree, the spec and plan win.

These files are not read automatically. When given a task, read the constitution, the task in `tasks.md`, and the spec and plan sections it references.

Later specs follow the same layout: `docs/specs/002-online-retrieval/` (online query pipeline) and `docs/specs/003-evaluation/` (evaluation framework, once written). Work on those features comes from their own `spec.md`, `plan.md` and `tasks.md`.

**Claude Code users:** Claude Code reads `CLAUDE.md` / `CLAUDE.local.md`, not this file. Put `@AGENTS.md` at the top of your personal, git-ignored `CLAUDE.local.md` so these rules load in every session.

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


## 4.3 Evaluation rules and definitions (Article VII)

> **Status: provisional.** Proposed by Nicole (evaluation owner) on 2026-10-07 for team review. It will move into `docs/specs/003-evaluation/spec.md` once that spec is written; until then, this section is the working definition. Change it only by agreement in a reviewed PR.

### Evaluation data rules
- **Development repo:** `pallets/flask`, pinned to one commit recorded in the question-set file. Ground-truth files and line ranges are only valid at that commit.
- **Held-out repo:** `fastapi/fastapi`. Do not index it, query it, or tune anything against it during development. It is run once, at the end, for the 10-question generalisation check.
- **Frozen references:** the question set, reference answers, reference citations and ground-truth files are fixed before any tuning (Article VII.1). Never edit them to match system output. A genuine error in a reference is fixed in its own commit, with the reason, and is flagged in the results.
- **Reported results** use the `prod` (32B) profile (Article VIII.5). Results from `dev` (14B) are development signals only.
- **Results files** are versioned under `eval/results/`, not `runs/`, which is git-ignored. Each file records: the git commit of CodeCompass, the pinned Flask commit, the generator profile and model id, the embedder and re-ranker revisions, the configuration flags, and per-question outputs (Article VII.6).

### Hallucinated answer (used for Verification Gain)
An answer counts as **hallucinated** if **any** of the following is true:

| # | Condition | How it is decided |
|---|---|---|
| H1 | **Fabricated or unmatched citation.** The citation checker returns outcome **G** for an answer that makes claims about the repository (Article VI). | Automatic, from the checker result |
| H2 | **Unsupported claim.** The answer makes at least one factual claim about the repository that is not supported by the evidence actually placed in the generator's context (retrieved chunks and tool results). This includes a claim that happens to be true of Flask but came from the model's training knowledge rather than the context (Article I.1–I.2). | Human grading against the context in the per-query audit log |
| H3 | **Fabricated answer to an unanswerable control.** The system gives a substantive answer instead of stating that it could not determine it (Article I.2–I.3). | Human grading; unanswerable questions only |

**Not hallucinated:**
- An explicit abstention ("I could not find enough evidence…") that makes no claims about the repository. This holds even if the checker flags it for having no `Sources` section. On an answerable question it scores 0 for answer quality, but it is recorded as *abstained*, not *hallucinated*.
- A supported but incomplete answer, which scores 1 ("partially correct").

**Relation to the answer-quality rubric (0/1/2):** H2 and H3 answers always score 0. A score-0 answer that is wrong **only** because it is incomplete or misread, with every claim still traceable to the context, is **not** counted as hallucinated. Graders record the reason for every 0: `unsupported`, `fabricated-citation`, `abstained`, or `wrong-but-grounded`.

**Why both automatic and human checks:** the citation checker only proves that a cited file or commit was *in the context*, not that the claim is *correct* (Article VI.5). An F (cited) answer can still hallucinate, which H2 catches.

### Metrics
- **Hallucination rate** = hallucinated answers ÷ questions answered in that configuration. It includes the unanswerable controls, and is reported overall and per question category.
- **Verification Gain** (primary metric) = hallucination rate (**RAG-only**, verifier tools off) − hallucination rate (**full agentic**, verifier tools on). It is measured on the same questions, with the same index commit and the same `prod` model. A positive value means verification helps.
- **hit rate@k** = share of answerable questions with at least one ground-truth file in the top k. It is measured at k = 1, 5 and 10 on the RRF shortlist (before re-ranking) and at k = 1, 5 and `final_k` (default 8) on the chunks the generator receives (after re-ranking). The headline is hit rate@10 before re-ranking, compared with hit rate@`final_k` after re-ranking. Unanswerable controls are excluded.
- **Citation accuracy** = cited `Sources` entries that the checker verifies ÷ all cited entries.
- **Latency** is recorded per configuration from the audit-log stage timings.
