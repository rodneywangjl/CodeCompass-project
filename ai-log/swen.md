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

## 2026-10-26 · Hybrid retrieval, re-ranking and context budgeting (T2.3, T2.4, T3.2, T4.2)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/embedder.py, codecompass/online/retrieval/hybrid.py, codecompass/online/retrieval/reranker.py, codecompass/online/context.py, codecompass/online/config.py, tests/online/test_query_embedding_t23.py, tests/online/test_hybrid_retrieval_t24.py, tests/online/test_reranker_integration_t32.py, tests/online/test_context_budget_t42.py
- **Outcome:** Kept
### What I asked for
Tests-first implementation of four Spec 002 tasks, with no approval stops between tests and code:
- T2.3: embed the question through the index handles (`embed_question`), so the embedder `open_index` checked against the index is the one used.
- T2.4: hybrid retrieval (`retrieve`) that runs vector and keyword search and merges them with RRF into a shortlist of at most `rerank_k`.
- T3.2: `rerank_chunks` that scores the shortlist with the re-ranker, sorts best first (ties keep shortlist order) and keeps `final_k`.
- T4.2: context budgeting in generator tokens. `chunk_budget` reserves the answer, prompt prefix and `max_verifier_rounds × max_tool_output_tokens`; `fit_chunks` keeps chunks in order until the first misfit; `check_round_reserve` raises a ValueError citing Article V.1 when the tool reserve leaves no room for code. Added `tools.max_tool_output_tokens` (default 768, Plan §7).
### How I checked it
Checked the test cases myself.
### What I kept or changed
Kept all four implementations. Claude corrected its own T4.2 test (d7d465e): a 4096-token window cannot hold the default reserve (3 × 768) plus a 2048-token answer, so the window was changed to 8192 (dev-lowmem). I reviewed them afterwards.
## 2026-11-03 · GPU cluster notebook for running CodeCompass
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** notebooks/codecompass_gpu_cluster.ipynb
- **Outcome:** Changed
### What I asked for
A notebook to run CodeCompass on an individual SCIS GPU cluster account: check the GPU, unzip and install the project, download the pinned 14B GGUF with a checksum, build `llama-server` from source (the prebuilt binary needs a newer glibc than the cluster has), start the server with the `dev` profile settings, index a public repo (Flask), ask questions, and test whether the model requests the allow-listed tools. Built up over several sessions, with each failure fixed in turn.
### How I checked it
Ran the notebook on my SCIS cluster account (RTX 3090). Indexed Flask and asked the same question with the GPU re-ranker and the CPU re-ranker. The top scores were 0.00350 (GPU) and 0.00348 (CPU), and re-ranking took 0.4 s on the GPU against 147 s on the CPU. Ran the tool-call test: the model requested a tool in 8 of 8 runs that passed the evidence gate. 
### What I kept or changed
Rewrote the notebook from the cells that ran on the cluster, in the order that works after a kernel restart. Kept the layered config loader (`load_online_config_layers`) because the single-file loader ignores the user config. Kept the GPU re-ranker, which matched the CPU top score (0.00350 vs 0.00348) and took 0.4 s instead of 147 s. Left out the one-off config-swap test cell. Did not change the evidence gate or the embedder revision: the gate's 0.02 minimum is a retrieval setting, and the unpinned remote code is a team decision under Article VIII.1.

## 2026-11-04 · Clean up the GPU cluster notebook and add login steps
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** notebooks/codecompass_gpu_cluster.ipynb, ai-log/swen.md
- **Outcome:** Changed
### What I asked for
Clean up the cluster notebook using the fixes from the run, so it works in order after a kernel restart, and summarise the login steps for the group.
### How I checked it
Read through notebook and run it to ensure it works on GPU cluster.
### What I kept or changed
Rewrote the notebook in run order: login steps, paths and config, one-time setup, server, index, questions, tool tests, checks and stop. Kept the layered config loader, so the user config file is read. Removed the config-swap test cell, which left the user config on CPU settings when a question failed. Added the account and data rules from scis_tech. Checked that the notebook has no passwords. Not committed.

## 2026-11-07 · Split over-long lines in the chunkers (T11.1)
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** codecompass/offline/chunking/sizing.py, codecompass/offline/chunking/fallback.py, codecompass/offline/chunking/treesitter.py, tests/offline/test_long_line_t111.py, docs/specs/001-offline-indexing/tasks.md, ai-log/swen.md
- **Outcome:** Changed
### What I asked for
Fix the GPU cluster bug on branch `fix/chunker-long-lines`: a single source line over the hard max crashed the fallback chunker (a `TypeError` from joining the embedder's token ids) and was emitted whole by the tree-sitter chunker. Write the failing tests first, add a T11.1 entry to the Spec 001 tasks, and split such lines by characters, re-counted with the real tokenizer.
### How I checked it
TODO (Swen)
### What I kept or changed
Before any implementation, I corrected two of my own tests (a wrong line number, and a test that reached the wrong code path) and added two tests for the long line starting its own window and for short lines before it inside a function. Added one fix beyond the list: the fallback chunker's last chunk reported an end line one past the end of the file, which the lines-after test exposed; clamped it. The tree-sitter lines-before-a-long-line test passes before the fix, so it guards behaviour rather than failing. Did not push or open a PR.
