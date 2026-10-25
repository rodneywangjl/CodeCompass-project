# AI Use Log: Rodney Wang

## 2026-10-26 · Review of local dev model setup
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
A check of my uncommitted dev model setup: the `codecompass.toml` generator profile and the `MODEL-SETUP.md` notes on running Qwen2.5-Coder-14B through llama.cpp `llama-server`.
### How I checked it
TODO (member)
### What I kept or changed
Kept the pinned GGUF file, checksum and server settings. The AI confirmed the config loads through `load_online_config`, the SHA-256 and file size match the downloaded model, the llama.cpp version and default port match `llama-server`, and `pytest -m "not model"` stays green (143 passed). Fixed three wording errors in `MODEL-SETUP.md`: the C9 reference points to the spec, not the plan; the scope line names both untracked files; the config comment says a profile table must set `model_id`.

## 2026-10-26 · Low-memory generator profile
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
A separate generator profile for machines with 16 GiB of memory, instead of lowering the shared `dev` context to 8192.
### How I checked it
TODO (member)
### What I kept or changed
Kept a new `dev-lowmem` profile: the same pinned 14B GGUF with an 8192 context, selected with `GENERATOR_PROFILE=dev-lowmem`. Put `dev` back to the 32768 context in `plan.md` and left `dev` as the default (Article VIII.4). Did not add a profile for machines below 16 GiB: the smallest 14B file is 5.4 GiB, and a 7B model would need a constitution amendment (Article VIII.1).

## 2026-10-26 · Spec 002 design review and fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
A review of the constitution, specs and plans for soundness and efficiency, then fixes to spec, plan and tasks 002 on a docs branch before any more online tasks are built.
### How I checked it
TODO (member)
### What I kept or changed
Kept the AI's fixes for citation checking (cited lines must lie inside retrieved chunks, not just overlap them), the round limit (one final answer-only call after the third tool round), context budgeting that reserves room for tool output and counts tokens with the generator's tokenizer, `git blame --porcelain` and a 0x1F-separated `git log` format so commit metadata parses exactly, simpler path validation, and a `/props` check that the running server matches the profile. Did not let it decide three points that need the team: removing the round limit and tool list from config (changes the approved T0.1 test), how the query embedder is reached through the offline public API, and how an uncited "could not determine" answer is shown. These are marked [NEEDS CLARIFICATION]. Kept the one-task, tests-approved-first workflow for the remaining tasks instead of building the rest of the pipeline in one pass.

## 2026-10-26 · T0.2 History fixture repo
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/fixture_repo.py, tests/online/test_fixture_repo_t02.py
- **Outcome:** Kept
### What I asked for
T0.2: a fixture repo with meaningful commit messages, known authors and dates, so the verifier-tool tests can assert exact `git log` and `git blame` output. I gave advance approval for the tests instead of reviewing them before implementation; they are reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept a separate `build_history_repo` rather than adding commits to the Sprint 1 fixture, which rewrites its own history and is relied on by the offline tests. The history includes an author name with a space and a subject with a comma (for the 0x1F log format in plan D7) and a final "wip" commit for the no-rationale case (Article V.5). Fixed dates and identities make the shas identical on every build.

## 2026-10-26 · T0.3 Stub generator
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/stub_generator.py, tests/online/test_stub_generator_t03.py
- **Outcome:** Kept
### What I asked for
T0.3: a deterministic stand-in for the generator so the harness, budgeting and citation tests need no `llama-server`. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept "responses in order, then repeat the last", so a round-limit test needs only one tool-call response. Kept recording a deep copy of each call's messages, after a test showed that storing the list itself lets later rounds rewrite earlier records. Added `count_tokens` (whitespace tokens) because the revised plan D4 counts tokens through the generator. Committed an empty module with the tests so they failed on missing behaviour, not on an import error.

## 2026-10-26 · T0.4 Stub re-ranker
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/stub_reranker.py, tests/online/test_stub_reranker_t04.py
- **Outcome:** Changed
### What I asked for
T0.4: a model-free stand-in for the `bge-reranker-v2-m3` cross-encoder. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
The task suggested scoring by text length. Changed it to count shared query words, so later integration tests can check that a relevant chunk really moves up, rather than just that the order changed. Kept a record of every call's inputs so T3.2 can prove the re-ranker only sees the shortlist (Article IV.3).

## 2026-10-26 · T1.1 RRF merge
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/rrf.py, tests/online/test_rrf_t11.py
- **Outcome:** Kept
### What I asked for
T1.1: Reciprocal Rank Fusion of the vector and BM25 result lists, using ranks only (Article IV.2). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept ranks counted from 0, as plan D2's code does, rather than the 1-based ranks of the original RRF paper; the plan decides how things are built, and the difference is noted for the evaluation work. Returned `(chunk_id, score)` pairs instead of bare ids, because the audit log (AC-7.1) needs each chunk's RRF score. Ties are broken by chunk id so the merge is deterministic.

## 2026-10-26 · T1.2 RRF configuration
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_rrf_config_t12.py
- **Outcome:** Kept
### What I asked for
T1.2: tests that the RRF constant and k are configurable, plus empty and single-item inputs. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
The tests passed on first run: T1.1's tests already required `k` and `constant` as parameters, so there was no missing behaviour to make red. Kept them as a test-only task, with no implementation commit, instead of weakening the code to manufacture a failure. Added a test that values loaded from `codecompass.toml` drive the merge, which T1.1 did not cover.

## 2026-10-26 · T2.2 Keyword search wrapper
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/keyword.py, tests/online/test_keyword_search_t22.py
- **Outcome:** Kept
### What I asked for
T2.2: BM25 search through the read-only keyword handle from `open_index`, tested against a real tantivy index built from the history fixture. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept a thin wrapper: the Sprint 1 handle already parses queries leniently, and a test with a question full of punctuation (`authenticate()`, quotes, `?`) confirmed it does not crash. Added an early return for blank queries. The vector half (T2.1) is blocked: the read-only vector handle has no search method, and adding one changes Sprint 1 code outside the task's scope.

## 2026-10-26 · T3.1 Re-ranker protocol
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/reranker.py, tests/online/test_reranker_protocol_t31.py
- **Outcome:** Kept
### What I asked for
T3.1: the re-ranker interface the pipeline codes against, so the stub and the real `bge-reranker-v2-m3` wrapper are interchangeable. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept a runtime-checkable `Reranker` protocol only. The real `BgeReranker` is left to T13.1, where it can be tested against the actual model; writing it now would be untested code in the required suite.

## 2026-10-26 · T4.1 Chunk formatting
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/context.py, tests/online/test_context_format_t41.py
- **Outcome:** Kept
### What I asked for
T4.1: format retrieved chunks as plain text with file, line, language and commit metadata for the generator (Article IV.4). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the revised plan D3 header, whose first part is exactly the `Sources` code-citation form, and a separate `citation_label` function that the citation checker can reuse so the two cannot drift apart. `RetrievedChunk.from_record` drops the stored vector when it builds the chunk, so a vector cannot reach the prompt by accident.

## 2026-10-26 · T5.1 Tool argument validation
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_validation_t51.py
- **Outcome:** Kept
### What I asked for
T5.1: validate the path, line range and commit count the model passes to `git blame` / `git log` (Article V.2). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the revised plan D6: the real check is that the path is a file in the git tree at the indexed commit, which also rules out anything outside the repo. Added tests that names like `app/(auth)/page.tsx` and `Outer$Inner.java` pass, since the original character blacklist would have rejected them, and that option-like paths (`-rf`, `--output=x`) and directories are rejected. `n=True` is rejected because Python treats `True` as the integer 1.

## 2026-10-26 · T5.2 git_blame executor
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_git_blame_t52.py
- **Outcome:** Kept
### What I asked for
T5.2: run `git blame` for the model safely and return output the citation checker can match commits against. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept `--porcelain`, parsed into commit records (hash, author, date, subject), and a compact rendering of one line per commit with the lines it owns, instead of passing raw blame output to the model. A test blames an older commit to prove the tool uses the indexed commit, not HEAD. The executor validates its own arguments, so no caller can run it unchecked, and a timeout returns an error the model can read instead of raising.

## 2026-10-26 · T5.3 git_log executor
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_git_log_t53.py
- **Outcome:** Kept
### What I asked for
T5.3: run `git log` on a file for the model, limited to a configured number of commits. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the 0x1F-separated format from the revised plan D7. The test case that motivated it, author "Alice Tan" with the subject "Handle flaky upstream service, raise MAX_RETRIES to 5", would have been split wrongly by the original space-separated format. Output reuses the same commit records and one-line rendering as `git_blame`, so the citation checker handles both tools the same way.

## 2026-10-26 · T5.4 Tool allow list
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_allowlist_t54.py
- **Outcome:** Kept
### What I asked for
T5.4: only `git_blame` and `git_log` may run; any other tool request is refused with a message the model can read (Article V.2). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the dispatch table as the allow list, so `allowed_tools` in config cannot add a tool; a test sets `git_diff` in config and checks it is still refused. This keeps to Article V.2 without touching the approved T0.1 test, which still reads `allowed_tools`. Unexpected arguments (e.g. a `format` passed to `git_log`) are refused too, so the model cannot pass flags through.

## 2026-10-26 · T5.5 Tool-result cache
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/cache.py, tests/online/test_tool_cache_t55.py
- **Outcome:** Kept
### What I asked for
T5.5: cache tool results within one question and record cache hits for the audit log (Article V.3). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept a per-call cache keyed by the tool and its arguments serialised with sorted keys, so argument order does not matter and list values do not crash the hashing. Repo and commit are not in the key because one cache only lives for one `ask` call, where both are fixed; the docstring says so, so a reviewer can check it against Article V.3's key list. Rewrote the tests to import the module rather than the class, so the first run failed on missing behaviour instead of an import error.
