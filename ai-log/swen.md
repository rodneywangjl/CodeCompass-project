# AI Use Log: Swen

## 2026-10-07 · Citation verification and output routing planning
- **Tool (model):** Antigravity (Gemini 3.8 Flash)
- **Files:** docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
Analysis of Spec 002 (Online Retrieval Pipeline) to determine the scope, architecture, and recommended starting point for Citation Verification and Output Routing.
### How I checked it
Cross-referenced the suggested starting points and dependencies against the constitution (Article VI on non-bypassable deterministic verification, Article IX on TDD order) and Tasks 002 (S0 foundational models, S9 citation checker, S10 index freshness, and S12 public API/CLI).
### What I kept or changed
Kept the phased roadmap recommending starting with foundational models (T0.1), followed by the source entry parser (T9.1), the deterministic checker (T9.2/T9.3), formatting and metadata copy (T9.4/T9.5), and finally output routing into QueryResult and CLI.

## 2026-10-07 · Adopt AI use and commit trailer guidelines
- **Tool (model):** Antigravity (Gemini 3.8 Flash)
- **Files:** AGENTS.md, ai-log/swen.md
- **Outcome:** Kept
### What I asked for
Incorporate Sections 4.1 (Commit trailer) and 4.2 (AI use log) into AGENTS.md, and establish personal AI usage log.
### How I checked it
Checked that trailer formatting adheres to the Assisted-by standard and that the log file follows the required 3 fixed fields and 3 free-text sections.
### What I kept or changed
Added Sections 4.1 and 4.2 to AGENTS.md and created ai-log/swen.md with conforming structure.

## 2026-10-26 · Spec 002 copy relay, block 2 (hybrid retrieval, re-ranking, context budget)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/embedder.py, codecompass/online/retrieval/hybrid.py, tests/online/test_query_embedding_t23.py, tests/online/test_hybrid_retrieval_t24.py, tests/online/test_reranker_integration_t32.py, tests/online/test_context_budget_t42.py, ai-log/swen.md
- **Outcome:** Kept
### What I asked for
Carry out block 2 of the Spec 002 copy relay: copy the 9 commits fa9dc5c → 393270a (T2.3–T4.2) from Rodney's referHere branch onto feat/hybrid-retrieval-reranking, made from main after the block 1 PR (#12) was merged, with Rodney's ai-log changes left out.
### How I checked it
Confirmed PR #12 was merged into origin/main before branching. Checked that the 9 commits applied without conflicts, in the same order (test commits before their feature commits, Article IX.3), each under my name and keeping its Assisted-by line. Checked that `git diff 393270a HEAD` shows no differences outside ai-log/. Ran `pytest -m "not model"`: 369 passed, 5 deselected.
### What I kept or changed
Kept all 9 commits unchanged apart from authorship. Added this entry.
