# CodeCompass: agent rules

CodeCompass is a RAG-based Q&A assistant over a git repository. Offline pipeline: scanner, chunker, embedder, Chroma vector store, tantivy BM25 index. Online pipeline: hybrid retrieval, re-ranker, generator, verifier tool, citation checker. This repo is built **spec-driven and test-first**.

## Source of truth (read before coding)

None of these files load automatically. Before any task, read them yourself:

- `docs/constitution.md`: non-negotiable rules. Read it before writing any code or tests.
- The spec folder for your task, `docs/specs/<NNN-feature>/`:
  - `spec.md`: what to build and the acceptance criteria (ACs).
  - `plan.md`: how it is built (modules, interfaces, design decisions).
  - `tasks.md`: the ordered task list. Work comes from here.

| Spec | Status |
|---|---|
| `001-offline-indexing` | Done (Sprint 1) |
| `002-online-retrieval` | **Current**: online query pipeline |
| `003-evaluation` | Not yet written. Draft rules are in `docs/specs/003-evaluation/draft-rules.md` |

- `docs/summary/SPRINT1-SUMMARY.md`: what Sprint 1 built, its verification results and design deviations. It is a **record, not authority**: where it disagrees with a spec or plan, the spec and plan win.

When given a task: read the constitution, the task in `tasks.md`, and the spec and plan sections it references.

## Setup and commands

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
git config user.name "<name>" && git config user.email "<email>"  # fixture-repo tests need a git identity

pytest tests/online/test_config_t01.py   # one task's tests
pytest -m "not model"                    # full required suite (what CI runs)
```

Never run `pytest -m model`, start `llama-server`, or download model weights unless explicitly asked.

## How to work

1. Do **one task at a time**, only the one you are asked to do. Respect its "Depends on" and "Touches".
2. **Tests first.** Write the tests listed under the task's "Tests first". Name the files `tests/<offline|online>/test_<topic>_t<NN>.py` (e.g. `test_config_t01.py` for T0.1).
3. **Red.** Run them and confirm they fail for the expected reason: a missing behaviour, **not a typo or import error**.
4. **Stop for approval.** Show:
   - each test name and the AC it covers
   - the failing output

   Then wait for an explicit "approved" before writing any implementation.
5. **Green.** Write the minimum code to pass. Re-run and fix the **code** until all tests pass. Then refactor with tests green.
6. Run the full required suite: `pytest -m "not model"`.
7. Commit the tests first, then the implementation, as two separate commits.

### Done when
- The task's tests pass and `pytest -m "not model"` is green.
- No skipped or xfail tests without a written reason.
- No new or unpinned dependencies.
- Nothing changed outside the task's "Touches".

## Hard rules

- **Never edit, weaken, skip, delete, or xfail an approved test to make it pass.** If a test seems wrong, stop and say so.
- Do not add features, files, or refactors outside the task's "Touches". If another file needs to change, stop and ask.
- Do not add or upgrade a dependency without asking. All dependencies are pinned. Do not use `mlx-lm` or MLX.
- **Module boundary (Article II.2):**
  - `codecompass.offline` exports only `ensure_current`, `status`, `open_index` and `check_consistency`. `ensure_current` is the only write-capable export.
  - `codecompass.online` imports from `codecompass.offline` only through that public API. It never imports scanner, chunker, embedder, or store code. The query embedder comes bound to the handles: `open_index(..., embedder=)` then `handles.embed_query()`.
  - The result types `EnsureResult`, `IndexHandles` and `IndexStatus` are what those functions return. They are not in `__all__` and online code does not import them (Plan 002 §3).
- Required tests must be deterministic and must not need network access, a GPU, `llama-server`, or a model download. Use the stubs in `tests/support/` (`StubEmbedder`, `StubGenerator`, `StubReranker`). Tests that need a real model use the `model` marker.
- Models, thresholds, sizes, and paths come from config, never hard-coded.
- If the spec is ambiguous, mark it `[NEEDS CLARIFICATION]` and ask. Do not guess.
- Do not modify `docs/constitution.md`. Amendments are made by a separate, reviewed pull request.

## Evaluation data

Full definitions are in `docs/specs/003-evaluation/draft-rules.md` (provisional). The rules an agent must never break:

- Never index, query, or tune anything against the held-out repo `fastapi/fastapi`.
- Never edit the question set, reference answers, reference citations, or ground-truth files to match system output.
- Versioned results go in `eval/results/`, not `runs/` (git-ignored).
- Any open question in that file is `[NEEDS CLARIFICATION]`.

## Environment

- Python 3.11+. Dependencies are pinned in `requirements.txt`.
- Embedder: `jinaai/jina-embeddings-v2-base-code` at the revision pinned in `codecompass/offline/config.py`.
- Generator: Qwen2.5-Coder-Instruct through llama.cpp `llama-server` only. Profiles: `dev` (14B) for development, `prod` (32B) for reported results.

## Git conventions

- Branch: `feat/<spec-name>-t<N.N>`, e.g. `feat/online-retrieval-t0.1`.
- Commits: `test(T0.1): <summary>`, then `feat(T0.1): <summary>`. Use `fix:` / `docs:` for work outside a task.
- Pull requests must name the spec and task they implement and the constitution articles they affect (Article IX.7). A second person reviews every PR, and CI must pass before merge.

### Commit trailer

Add this line to any commit that contains AI-assisted work (the Assisted-by convention used by the Linux kernel and LLVM):

```
Assisted-by: <tool> (<model id>)
```

For example:
```
feat(T0.1): implement online package skeleton, config, and models

Assisted-by: Claude Code (claude-opus-5-5)
```

If your tool adds its own attribution line, such as `Co-Authored-By`, you may use that instead.

## AI use log

Each team member keeps a log in `ai-log/`:

```
ai-log/
  gavin-tay.md
  kelsey.md
  nicole-goh.md
  rodney-wang.md
  swen.md
```

- Write in the log of the member you are working for. If unsure, match `git config user.name` or ask.
- Add one entry per task, as you work, and commit it with the work it describes.
- Each entry has a heading with the date and a short title, three fixed fields, and three short free-text sections.
- **Agents may draft every part except "How I checked it".** Leave that section with a `TODO` for the member to write. It records the human's own verification, which is the most important part of the entry.

```markdown
## 2026-10-12 · Retrieval pipeline skeleton
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/pipeline.py, tests/online/test_retrieval_t21.py
- **Outcome:** Changed
### What I asked for
A skeleton for the retrieval pipeline: query embedding, hybrid search and RRF merge.
### How I checked it
TODO (member)
### What I kept or changed
Kept the structure. Rewrote the RRF tie-break to be deterministic and added a test for it.
```