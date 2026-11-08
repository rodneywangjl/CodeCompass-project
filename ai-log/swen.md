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
Ran pytest -m "not model" on macOS (Python 3.12.6): 1,174 passed, 0 failed, 10 deselected (model-marked). The 17 long-line tests (test_long_line_t111.py) cover both the fallback and tree-sitter chunkers for both bugs. Created a scratch repo at ~/scratch/longline2 with two files, each holding one 60,000-character line of random letters and digits: a single long string inside a function, so the tree-sitter chunker handles it and a long line in a file with no tree-sitter grammar, so the fallback chunker handles it. Counted the tokens with the real Jina tokenizer. The long line is 42,352 tokens, far over the 8,192 limit.
Indexed on a 3090 node with the real GPU embedder: python -m codecompass.offline.cli index ~/scratch/longline2 --embedder code.
Checked the result: python -m codecompass.offline.cli check ~/scratch/longline2.

Result: the index completed with fallback=1, non_code=0, chunks added=12, and consistent: True (12 chunks agree). The tokenizer warning (42352 > 8192) appeared during counting, as expected. Indexing took about 8 minutes, mostly in the embedding step.
### What I kept or changed
Before any implementation, I corrected two of my own tests (a wrong line number, and a test that reached the wrong code path) and added two tests for the long line starting its own window and for short lines before it inside a function. Added one fix beyond the list: the fallback chunker's last chunk reported an end line one past the end of the file, which the lines-after test exposed; clamped it. The tree-sitter lines-before-a-long-line test passes before the fix, so it guards behaviour rather than failing. Did not push or open a PR.

## 2026-11-08 · ask streams every answer, so the timeout is per wait (T19.3)
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** codecompass/online/generator/llama.py, codecompass/online/config.py, codecompass/online/__init__.py, codecompass/online/tui.py, codecompass.toml, tests/online/test_ask_stream_timeout_t193.py, tests/online/test_stream_generator_t22.py, docs/specs/002-online-retrieval/tasks.md, docs/specs/004-tui/tasks.md, docs/specs/004-tui/plan.md, ai-log/swen.md
- **Outcome:** Changed
### What I asked for
Stop `ask` timing out on slow machines: the non-streaming call without a callback capped the whole answer at `timeout_seconds`. Always stream, add a connect timeout for the first contact with the server, keep the payload and answer unchanged.
### How I checked it
`pytest tests/online/test_ask_stream_timeout_t193.py tests/online/test_stream_generator_t22.py -v`
Ran all the tests for commits to the branch and verified that all tests passed. Ran the full required suite with `pytest -m "not model"` on cluster as well as local computer.
### What I kept or changed
Amended Spec 004 T2.2 and the plan, which said the request is unchanged without a callback (you chose this). Changed two approved stream tests to expect `stream: true` on every call, and one fixture so its stream matches its reply (needs reviewer sign-off, Article IX.3). The connect timeout bounds only the readiness check, because urllib cannot set a connect timeout separately from the wait for the answer. The value is set after construction so the approved TUI fakes keep their constructor. The existing `timeout_seconds` is still not validated; only the new value is.

## 2026-11-07 · Repeated tool calls are not run again (T19.4)
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_repeated_tool_calls_t194.py, tests/online/test_harness_round_limit_t83.py, docs/specs/002-online-retrieval/tasks.md, ai-log/swen.md
- **Outcome:** Changed
### What I asked for
Re-test whether a repeated tool call (same tool and arguments in one question) still wastes a round after T19.1. If it does, stop it from running again, tell the model to use the earlier result, log the repeat, and decide whether a repeat counts against `max_verifier_rounds`.
### How I checked it
TODO (Swen)
### What I kept or changed
The probe showed the cache stopped re-execution but the repeat still used a round, and the model got the full result again. Decided a repeat counts against the limit (Article V.1: the loop must stay bounded). The round-limit test T8.3 fed the same call every round, so it had to change to distinct calls; the assertions are unchanged, and it needs reviewer sign-off (Article IX.3). Evaluation must be re-run before results are reported (Article VII.5).

## 2026-11-08 · Vague-question hint behind a config flag (T19.5)
- **Tool (model):** Claude Code (claude-haiku-5-5)
- **Files:** codecompass/online/agent/harness.py, codecompass/online/config.py, codecompass/online/__init__.py, tests/online/test_vague_question_hint_t195.py, docs/specs/002-online-retrieval/tasks.md, ai-log/swen.md
- **Outcome:** Changed
### What I asked for
A `[prompt] vague_question_hint` flag, off by default. When on, the system prompt tells the model that, if the question names no file or function and the context does not answer it, it should say so and ask the developer to name a file or function. Tests first, with the flag loading, layering, rejecting a non-boolean, and being recorded in the audit log.
### How I checked it
Ran pytest tests/online/test_vague_question_hint_t195.py -v (21 passed). On the cluster, set `[prompt] vague_question_hint = true` in a local config (not committed), asked a vague question that still passes the evidence gate with `python -m codecompass.online.cli ask <repo> "<question>" --config <file>`, and checked that the answer says it could not find the answer and asks for a file or function. Then checked the newest JSON in the query log directory has `"prompt": {"vague_question_hint": true, ...}`. With the flag false, the same question gives the earlier answer and the log says false.
### What I kept or changed
Kept the rule as one numbered sentence after the existing rules, so with the flag off the prompt is byte-for-byte today's (snapshot tests, with and without tools). The evidence gate (AC-1.5) refuses before the model is called, so this sentence reaches the model only for questions that pass the gate and are still not answered from the context. The gate's refusal text is unchanged; changing it would be a spec change. Off by default; the evaluation must be re-run before any result that uses the flag is reported (Article VII.5). I first added a `[prompt]` table to codecompass.toml; that broke tests/eval/test_eval_config_t52.py, which requires the eval config to match the project config, so the default lives only in code.
