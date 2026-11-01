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

## 2026-10-26 · T5.6 Tool output cap
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_cap_t56.py
- **Outcome:** Changed
### What I asked for
T5.6 (added in the spec review): cap each tool result so three tool rounds can never overflow the context window. Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept whole-line truncation with a visible `[output truncated: N more lines]` marker. Added a rule the task did not state: commits whose line was cut are removed from the result's records, so the citation checker cannot verify a commit the model never saw (Article VI.1). Refactored the first version, which re-counted the whole text for every line, to count each line once, because the real token counter is an HTTP call to `llama-server`.

## 2026-10-26 · T6.1 Tool-call parser
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tool_parser.py, tests/online/test_tool_parser_t61.py
- **Outcome:** Kept
### What I asked for
T6.1: read `<tool>name(key="value")</tool>` requests from the model's text, treating anything malformed as a final answer (Article VIII.2: no server-side tool calling). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept parsing with Python's `ast` module rather than a hand-written regex for the arguments. It accepts only `name(key=literal)`, rejects positional arguments, `**kwargs`, attribute calls like `os.system(...)` and nested calls, and never evaluates anything; a test replaces `eval` with a trap to check that. Added `strip_tool_blocks` for the forced final answer in plan D15. Unknown tool names still parse, so the allow-list refusal message (T5.4) reaches the model instead of the request being silently dropped.

## 2026-10-26 · T9.1 Source entry parser
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/parser.py, tests/online/test_source_parser_t91.py
- **Outcome:** Kept
### What I asked for
T9.1: parse the answer's `Sources` section into code and commit entries in the constitution's fixed format (Article VI.4). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept strict entry patterns, since the constitution fixes the format so checking can be exact. Entries that start with `[N]` but match neither form are kept as `invalid` rather than dropped, so the checker flags them instead of losing them. Accepted common heading variants (`## Sources`, `**Sources**`, `Sources:`) because models vary there and it carries no evidence. Inline markers ignore indexing such as `arr[0]`, so code in an answer is not read as a citation.

## 2026-10-26 · T9.2 Citation checker: verified answers
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_citation_checker_f_t92.py
- **Outcome:** Kept
### What I asked for
T9.2: the deterministic checker that marks an answer F when every citation matches evidence actually placed in context (Article VI.1). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept containment as the rule: a cited range must be fully covered by retrieved chunks of that file, and may span adjacent chunks. Coverage is checked by walking sorted chunk intervals rather than listing every cited line, so a model citing `lines 1-999999999` cannot make the checker loop for a long time. Commit citations match only parsed commit records from tool results, not any text that happens to contain the hash.

## 2026-10-26 · T9.3 Citation checker: flagged answers
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_citation_checker_g_t93.py
- **Outcome:** Kept
### What I asked for
T9.3: every way a citation can fail must produce outcome G (Article VI.3). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Nine of the fourteen tests passed on first run, because T9.2's per-entry check already flags a bad entry; the five that failed covered marker cross-checks and a missing `Sources` section, which is what this task added. Kept a test for a range that overlaps a chunk but runs past it (`lines 50-70` against a chunk at 42-58), the case the original plan's overlap rule let through. Duplicate entries for one marker are flagged rather than accepting whichever matches. A missing `Sources` section is G as the spec says today; how such answers are shown is still an open team question.

## 2026-10-26 · T9.4 Flagged answer formatting
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/formatter.py, tests/online/test_citation_format_t94.py
- **Outcome:** Kept
### What I asked for
T9.4: show a flagged answer with a banner over the whole answer and a mark on each unverified source, so it never looks like a verified one (Article VI.3). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the plan D11 banner and `[UNVERIFIED]` prefix, with a test that the banner never uses the word "true" (Article VI.5: verified means "found in context", not "correct"). Added a line for an inline marker that has no `Sources` entry at all, which the plan did not cover; otherwise the developer would see the banner but no marked source to check. Only lines after the answer body are marked, so a body line that happens to start with `[1]` is left alone.

## 2026-10-26 · T9.5 Harness-copied commit metadata
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_commit_metadata_t95.py
- **Outcome:** Kept
### What I asked for
T9.5: the commit subject, author and date shown in `Sources` must come from the tool result, never from the model (Article VI.4). Tests approved in advance; reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept the copy inside `check`, so no answer can leave the checker with model-written commit details. The rewritten `Sources` line is what the formatter shows; a test has the model claim "Mallory, 1999-01-01" and checks that the name appears nowhere in the rendered answer. Unverified commit entries are left exactly as written, so the reader sees what the model actually claimed next to the `[UNVERIFIED]` mark. A test against the real history fixture confirms records from `git blame` and `git log` both work.

## 2026-10-26 · Vector search on the read-only index handle
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/stores/vector.py, codecompass/offline/__init__.py, tests/offline/test_vector_search.py
- **Outcome:** Changed
### What I asked for
A repo review found that `open_index` handles had no vector ANN search, which blocks the online vector retriever (Spec 002 T2.1). I asked for a tests-first fix.
### How I checked it
TODO (member)
### What I kept or changed
Added `search(vector, limit)` returning ranked chunk ids, mirroring `KeywordIndex.search`. It returns `[]` on an empty store and caps `limit` at the store size. The read-only facade passes it through and still has no write methods.

## 2026-10-26 · Query embedder on the index handles
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/__init__.py, tests/offline/test_query_embedder.py
- **Outcome:** Changed
### What I asked for
The online pipeline needs to embed questions with the same embedder as the index, but Plan 002 D1 imports the internal `CodeEmbedder`, which breaks Article II.2. Separately, `open_index` only checked the config, not the embedder actually used. I asked for both to be fixed tests-first.
### How I checked it
TODO (member)
### What I kept or changed
Chose to bind the embedder to the handles: `open_index(..., embedder=None)` attaches it, and `handles.embed_query(text)` uses it. With no embedder passed, the pinned one is built from config and loads lazily. I chose the strict rule: the config and the embedder must both match the index, otherwise it is refused. No new public export.

## 2026-10-26 · Online config merge without a TOML round trip
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/config.py, codecompass/online/config.py, tests/online/test_config_merge.py
- **Outcome:** Changed
### What I asked for
T0.1's `load_online_config` wrote the offline sections back out as TOML text in a temp file. That crashed on, or silently corrupted, values with backslashes or quotes (e.g. Windows paths) and wrote booleans as `True`. I asked for a tests-first fix.
### How I checked it
TODO (member)
### What I kept or changed
Split the offline `load_config` so its validation runs on a parsed dict (`config_from_dict(raw, anchor=)`). The online loader passes its offline sections straight in and the TOML writer is deleted. The tests also found that relative `index.dir` resolved against the temp folder; the anchor is now the real config file's folder. The boolean bug has no test because no offline setting is boolean yet; the code that caused it is removed.

## 2026-10-26 · Spec 002 follow-up fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** AGENTS.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
A second repo review found gaps that PR #5 did not cover. I asked for them to be fixed one at a time in the spec, plan and tasks, without changing finished tasks or approved tests.
### How I checked it
TODO (member)
### What I kept or changed
- Resolved the plan's query-embedder clarification to match PR `fix/query-embedder`, and removed the AGENTS.md export TODO.
- `locked` is now treated as stale, like `failed` (D12, T10.1).
- D2 now matches the approved RRF code: ranks count from 0, ties broken by chunk id. An earlier draft said "from 1", which contradicted the approved T1.1 tests, so I dropped it.
- Tool results are sent as tagged `user` messages, not the `tool` role (D16, spec C12).
- Every acceptance criterion that had no task now has one (AC-1.2 reworded; AC-1.3, 3.7, 5.7, 5.8, 5.11 added to T4.2, T7.1, T8.5, T10.3, T12.3). AC-3.7 is handled in the harness, not in the finished T5.2/T5.3.

## 2026-10-26 · Pushed straight to main without review
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** branches `fix/vector-search`, `fix/query-embedder`, `fix/config-merge`, `docs/spec-002-followups`
- **Outcome:** Changed
### What I asked for
Merge the four branches above straight into `main`, with no PRs. This skips the second-person review that AGENTS.md and Article IX.6–IX.7 require, so it is recorded here.
### How I checked it
TODO (member)
### What I kept or changed
Merged with merge commits, so each fix's test-before-fix commit order stays visible. The full required suite passed before the push (327 passed). These changes most need a teammate's look after the fact, because they change Sprint 1 code:
- `open_index` now takes `embedder=` and refuses unless **both** the config's embedder and the embedder instance match the index.
- `codecompass/offline/config.py` gained `config_from_dict`, and the online loader no longer writes a temp file.

## 2026-10-26 · Review follow-ups: model setup, eval modes, docs fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** MODEL-SETUP.md, codecompass.toml, AGENTS.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Work through the remaining review items and push them straight to `main`, without review.
### How I checked it
TODO (member)
### What I kept or changed
- Reviewed and merged `docs/model-setup`. Its `codecompass.toml` loads with the new config loader, and no code or test reads it from the repo root. Updated two notes that would go stale, and flagged that `prod` still has no pinned GGUF (Article VIII.2).
- AGENTS.md no longer points at `docs/specs/003-evaluation/draft-rules.md`, which was never committed.
- Plan D8 now explains why its cache key meets Article V.3.
- Added the three Article VII.3 evaluation modes to Spec 002 (US10, FR-18, D17, T12.4), so `ask` is built with them.
- Drafted the constitution amendment for the duplicate Appendix A #12, but did not apply it: agents may not edit the constitution.

## 2026-10-26 · Constitution 1.2.1 clarifications
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix the errors in the constitution that today's review found, choosing the best option for each. I explicitly asked for this, overriding the AGENTS.md rule that agents never edit the constitution.
### How I checked it
TODO (member)
### What I kept or changed
PATCH 1.2.0 → 1.2.1 with four clarifications, each stating what the spec, plan and approved code already do:
- IV.2: RRF ranks count from 0. Kept 0 rather than the more common 1, so the approved T1.1 tests stay unchanged.
- V.1: one tool call per round, and one final answer-only call when the limit is hit.
- V.3: "tool messages" means the harness's own format, not the server's `tool` role.
- Appendix A: duplicate #12 renumbered to #13.

Pushed as branch `docs/constitution-1.2.1`, not to `main`: Governance requires amendments to be reviewed, so a teammate should approve it before it merges.

## 2026-10-26 · T2.1 Vector search wrapper
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/vector.py, tests/online/test_vector_search_t21.py
- **Outcome:** Kept
### What I asked for
T2.1: a wrapper that returns the top-k chunk ids by cosine similarity from the read-only vector handle, written tests-first.
### How I checked it
TODO (member)
### What I kept or changed
Kept as drafted: `vector_search(index, query_vector, k)` mirrors `keyword_search` and calls the handle's `search` (added in `fix/vector-search`). It takes a vector, not text, because embedding the question is T2.3's job. The ordering test checks the exact cosine order, which holds because Chroma searches exactly on a collection this small.

## 2026-10-26 · Constitution gaps and prompt reuse across rounds
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix every remaining problem in the constitution and optimise the architecture.
### How I checked it
TODO (member)
### What I kept or changed
- Constitution (still PATCH 1.2.1):
  - an uncited answer is never F;
  - the stale warning also covers a locked index;
  - the re-ranker revision is pinned;
  - the evaluation configuration is logged;
  - the Appendix A #2 summary matches Article V.1.
- Plan: prompt-prefix reuse across rounds (`cache_prompt`, append-only conversation), as an explicit logged profile setting, because llama.cpp says cache reuse can change outputs slightly.
- Not changed, because each is a trade-off that needs the team or an evaluation (Article VII.5):
  - several tool calls per round;
  - smaller re-rank candidate sets;
  - re-indexing in the background.

## 2026-10-26 · T9.7 Uncited answers and uncited parts
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/formatter.py, tests/online/test_uncited_t97.py, tests/online/test_citation_format_t94.py, docs/constitution.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Team decision Q1: anything in an answer that cites nothing should be marked professionally so the developer checks it. Both cases: an answer with no citations at all (A), and the uncited parts of a cited answer (B).
### How I checked it
TODO (member)
### What I kept or changed
- An answer with no citations stays outcome G, but shows an uncited-answer note instead of the "citations could not be verified" banner, because nothing was fabricated.
- In a cited answer, each paragraph or list item without a `[N]` marker gets "(not cited)" and a note at the top.
- Headings, code blocks and lead-in lines ending in ":" are skipped.
- Constitution VI.3 and VI.4, spec AC-4.8, AC-4.9 and FR-19, and plan D11 were updated first.
- One approved T9.4 test was changed to match AC-4.8. I approved it; second-person reviewer sign-off is still pending (Article IX.3).

## 2026-10-26 · T0.5 Configurable round limit and tool settings validation
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, codecompass/online/config.py, codecompass/online/agent/tools.py, tests/online/test_tool_settings_t05.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Team decision Q2: keep the round limit in the settings file and allow it to be raised in future, not fixed by the constitution.
### How I checked it
TODO (member)
### What I kept or changed
- Amended the constitution to 1.3.0 (MINOR). `max_verifier_rounds` is configurable (default 3) but always bounded: a negative or non-integer value fails startup, as does a value whose tool-result reserve leaves no room for chunks (the budget check lands in T4.2). The value is logged and counts as a pipeline change (VII.5).
- `allowed_tools` can switch tools off but never add one, and the tool runner now respects it; before this it was silently ignored.
- Validation is in the loader, not `ToolsConfig`, so the approved T5.4 test that builds a widened `ToolsConfig` still holds.
- No approved tests changed.

## 2026-11-01 · Dev environment, local models and a dev-7b profile
- **Tool (model):** Claude Code (claude-opus-5-5, claude-sonnet-5-5)
- **Files:** codecompass.toml
- **Outcome:** Changed
### What I asked for
Get the repo running: create `.venv` and install the pinned dependencies, then download the real models (embedder, re-ranker, generator). The 14B does not fit my 8 GB GPU, so I asked for the 7B instead, a `dev-7b` profile in `codecompass.toml`, and a run of the model tests.
### How I checked it
TODO (member)
### What I kept or changed
- `.venv` built from `requirements.txt` unchanged; `pytest -m "not model"` passed (500 passed, 8 deselected).
- Downloaded the embedder and re-ranker at their pinned revisions, and `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (SHA-256 matches the value Hugging Face records). The 14B download was started and then cancelled by me; nothing from it is on disk.
- Added a `[generator.profiles.dev-7b]` table (16384 context, same sampling settings as the 14B profiles). The default profile stays `dev`. This is a model change under Article VII.5, so its results are development signals only.
- `pytest -m model` on the 7B: 7 passed, 1 failed. `test_real_pipeline_end_to_end` failed 4 out of 4 runs because the 7B writes a `Sources` entry but never puts `[1]` inline in the answer, so the checker (correctly) flags it. No test or code was changed for this. The result is noted here, not fixed.
- The installed `llama-server` is `0.6.0-dev` (build 11429), not the 0.7.0 recorded in `MODEL-SETUP.md`. The version comment in the profile is left for me to fill in. Not committed.

## 2026-11-01 · Spec 004 minimal terminal UI (spec, plan, tasks)
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md
- **Outcome:** Changed
### What I asked for
A lightweight terminal UI, started by typing `codecompass`, that only lets me type a question and read the model's reply, and that uses the git repo root it is run from.
### How I checked it
TODO (member)
### What I kept or changed
- Kept it to one standard-library module over `ask()`, printing the answer unchanged so a flagged answer can never look verified (Article VI.3). Left out streaming, panes, colours and conversation memory.
- Decisions I approved: Q1 reuse the default models across questions (plan 002 O1 was not implemented for the defaults), Q2 add a setuptools build backend and a `codecompass` script entry, Q4 look for `codecompass.toml` in `--config`, then the repo root, then `~/.config/codecompass/`, then built-in defaults. Q3 (`readline` for history) is still open.
- Repo root is found with `git rev-parse --show-toplevel`, so it works from any subdirectory.
- Spec 003 already exists on a remote branch, so this one is 004. Not committed yet.

## 2026-11-01 · T0.1 Reuse default models across questions
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** tests/online/test_model_reuse_tui_t01.py, codecompass/offline/embedding.py, codecompass/offline/__init__.py, codecompass/online/__init__.py
- **Outcome:** Changed
### What I asked for
Task T0.1 of Spec 004: tests for building the default re-ranker and embedder once per process and reusing them on every later question, without weakening the embedder identity check (Article II.4).
### How I checked it
TODO (member)
### What I kept or changed
- Six tests. Four fail for the expected reason today (the models are rebuilt on every question: 3 re-rankers and 4 embedders where 1 is expected). Two already pass and act as guards: injected stubs never enter the cache, and a cached embedder still cannot bypass the mismatch check.
- Two of my own first drafts were wrong and were fixed before review: one stub embedder had the wrong identity, and the two "different config" tests passed trivially until I made them ask A, B, A.
- I approved the tests, then the implementation went in: `shared_embedder()` in `offline/embedding.py` (used by `ensure_current` and `open_index`) and a small cache in `online/__init__.py` for the re-ranker. Both are keyed on class and config, at most 4 entries each.
- The first version keyed on config only and broke the existing `test_ensure_default_embedder.py` in the full suite (an earlier test had cached a real `CodeEmbedder` for the stub config, so that test's monkeypatch never took effect). I fixed it in the code by adding the class to the key and did not touch any approved test.
- `pytest -m "not model"`: 506 passed. The test commit comes before the implementation commit on `feat/tui-t0.1`.

## 2026-11-01 · T1.1 Terminal UI session loop
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_session_t11.py
- **Outcome:** Changed
### What I asked for
Task T1.1 of Spec 004: the prompt loop behind `codecompass`. Read a question, print the answer, repeat; quit cleanly; survive errors and Ctrl-C.
### How I checked it
TODO (member)
### What I kept or changed
- `run_session(answer, *, stdin, stdout, stderr)` takes the answering function and the streams as arguments, so the loop is tested with a fake and needs no model. Only the answer goes to stdout; the prompt, the "Thinking…" status line, hints and errors go to stderr, and only when the stream is a terminal.
- Tests first: 17 tests, all failing with `NotImplementedError` from a stub `tui.py` (so the failure is missing behaviour, not an import error). I approved them, then the loop was implemented in `codecompass/online/tui.py`.
- One bug in the first draft: the error line used `exc or type(exc).__name__`, but an exception object is always truthy, so a message-less error printed a blank. The test caught it; the code now tests `str(exc)`. No test was changed.
- `pytest -m "not model"`: 523 passed.
- Left for T1.2: `readline` line editing. It only works through `input()`, not through a stream I can fake, so it is not in the loop yet (Spec 004 Q3 is still open).

## 2026-11-01 · T1.2 Terminal UI startup and wiring
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_main_t12.py
- **Outcome:** Changed
### What I asked for
Task T1.2 of Spec 004: make `codecompass` find the git repo root from wherever it is run, load the right config, check the generator, build it once, and call the real `ask()`.
### How I checked it
TODO (member)
### What I kept or changed
- Tests first: 23 tests; 22 fail with `NotImplementedError` from a stub `main`, and one passes (importing the module loads no model library, a guard). I approved them, then `main()` was implemented in `codecompass/online/tui.py`; all 23 passed on the first run.
- Covered: repo root from the root, a subdirectory and an explicit path; not-a-repo and missing-path errors; config order (`--config`, repo root, `$XDG_CONFIG_HOME` or `~/.config`, built-in defaults); `--profile`; the banner (terminal only); the generator warning with the `llama-server` start command; one generator per session; and one end-to-end test through the real `ask()` and citation checker with stub models.
- The generator health check is a warning, never a failure, so the session starts even with no server; the warning includes the `llama-server` start command built from the profile (reusing `launch_command`).
- `pytest -m "not model"`: 546 passed.
- Left out on purpose: `readline` (arrow keys and history). It only works through `input()`, which T1.1's approved stream-based loop does not use, so adding it would change that design. I will raise it separately.

## 2026-11-01 · T1.3 The `codecompass` command
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** tests/online/test_tui_entry_t13.py, pyproject.toml
- **Outcome:** Changed
### What I asked for
Task T1.3 of Spec 004: make typing `codecompass` in the terminal start the TUI, and put all the TUI work on one branch.
### How I checked it
TODO (member)
### What I kept or changed
- All TUI commits now sit on a single branch, `feat/tui`. The earlier stacked branches (`feat/tui-t0.1`, `feat/tui-t1.1`, `docs/spec-004-tui`) were ancestors of it, so deleting them lost nothing.
- Tests first: 6 tests; 4 fail because `pyproject.toml` has no `[project.scripts]`, `[build-system]` or package list, and 2 pass as guards (the help text and "no runtime dependency"). I approved them, then `pyproject.toml` got a pinned `[build-system]` (setuptools==84.2.1), a `[project.scripts]` entry and a package list limited to `codecompass*`. All 6 pass; `pytest -m "not model"`: 552 passed. `pip install -e .` has not been run yet.
- I added a check that the build backend is pinned (`setuptools==<version>`), since the repo pins everything that affects results (Article VIII.3).

## 2026-11-01 · T1.4 README for interactive mode, stub index removed, speed measurements
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** README.md
- **Outcome:** Changed
### What I asked for
Task T1.4 of Spec 004 (README "Interactive mode"), deleting the old stub-built index of this repo, and finding out why the first question is slow and what would speed it up. I also asked for streaming output.
### How I checked it
TODO (member)
### What I kept or changed
- README: a new section 7 "Interactive mode (`codecompass`)" (install, repo-root rule, config order, options, stdout/stderr split, keys, no streaming or memory), a line in Known limitations about the slow first question, and `tui.py` in the project structure.
- Deleted `~/.local/share/codecompass/a2a4a6a635a2691a` after checking it was the only entry, built with `stub@stub-1`, and stale. No other index was touched.
- Measured on this machine (192 repo chunks, real embedder): CPU 2.6 chunks/s, CUDA 72.3 chunks/s (27x faster); the vectors agree to 12 decimal places. Setting `[embedder] device = "cuda"` does not change the index identity or config fingerprint, so it needs no re-index.
- Found that the installed `llama-server` (Arch `llama-cpp` 0.6.0) has no GPU backend (`--list-devices` shows none), so generation runs on CPU. `-ngl 99` has no effect.
- Not done: streaming. It conflicts with Article VI.1 (nothing is shown before the citation check) and is out of scope in Specs 002 and 004, so it needs a decision and a spec change first.

## 2026-11-01 · Spec 004 phase 2: draft streaming, warm-up and layered config (spec only)
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md, ~/.config/codecompass/codecompass.toml (outside the repo)
- **Outcome:** Changed
### What I asked for
Streaming output, a way to speed up the slow first question, and to know whether putting the re-ranker on the GPU is worthwhile.
### How I checked it
TODO (member)
### What I kept or changed
- Measured per stage (`queries/*.json`): first question 352 s = index 193 s + re-rank 65 s + generation 94 s; after moving the embedder and re-ranker to CUDA the same question took 97 s = index 1 s + re-rank 4 s + generation 85 s. The re-ranker alone was 52 s on CPU and 2 s on the GPU (same top-8, score difference 4e-8, peak 3.2 GiB VRAM). Generation is now the main cost because the installed `llama-server` has no GPU backend.
- I chose the stderr draft for streaming, so the checked answer is still the only thing on stdout. Whether this fits Article VI.1 is open question Q5 in the spec for the reviewer.
- Found that a repo's own `codecompass.toml` hides the user-level file, so personal GPU and profile settings would not reach this repo. The spec proposes layering (Q6), which changes what I approved in Q4.
- Created `~/.config/codecompass/codecompass.toml` (profile `dev-7b`, embedder and re-ranker on `cuda`). It applies in repos without their own config, or with `--config`.
- Phase 2 is spec and tasks only; no tests or code yet. Nothing is committed for `codecompass.toml`.

## 2026-11-01 · T2.1 Layered config
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/config.py, tests/online/test_tui_layers_t21.py
- **Outcome:** Changed
### What I asked for
Task T2.1 of Spec 004 (Q6 approved): make my personal settings (profile, GPU devices) apply in a repo that has its own `codecompass.toml`, by layering the user-level file under the repo file.
### How I checked it
TODO (member)
### What I kept or changed
- New `load_online_config_layers(paths)` (lowest priority first), kept separate from `load_online_config` so the approved T0.1 loader tests are untouched.
- Tests first: 14 tests; 12 fail (8 with `NotImplementedError` from a stub loader, 4 on the old behaviour of the TUI) and 2 pass as guards (the repo still wins a conflict, and `--config` still uses only its own file). I approved them, then `load_online_config_layers` and the TUI wiring were implemented; all 14 pass.
- Banner format chosen so the approved T1.2 test still holds: `config: <repo file>, <user file>`, highest priority first.
- Implementation: `load_online_config` was split into reading the file and `_build_online_config(raw, anchor)` (behaviour unchanged, the approved T0.1 tests still pass); the layers function merges parsed tables, makes each file's relative `index.dir` absolute first, and names the file in a TOML syntax error.
- One decision to review: an unknown top-level section (for example a mistyped `[embeder]`) is rejected by the new layered loader but was silently ignored by the old one. I kept the old loader as it was to avoid changing what teammates' files do; the TUI always uses the layered one.
- `pytest -m "not model"`: all passing.

## 2026-11-01 · T2.2 Streaming in the generator
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/generator/llama.py, tests/support/fake_http.py, tests/online/test_stream_generator_t22.py
- **Outcome:** Changed
### What I asked for
Task T2.2 of Spec 004: let the generator wrapper stream the model's text to a callback, so the terminal can show a clearly labelled unchecked draft (Q5), with all `llama-server` streaming kept inside the one wrapper (Article VIII.2).
### How I checked it
TODO (member)
### What I kept or changed
- Tests first: 12 tests in the new file; 10 fail (the callback is never called, there is no `stream` flag in the request, and a lost stream does not raise) and the 5 existing T7.2 generator tests plus 2 new guards pass. A stub `on_text=None` parameter, which is ignored, was added to `generate()` so the tests fail on assertions rather than on an unexpected-argument error. I approved them, then `post_stream` (in `generator/http.py`) and the streaming branch of `generate()` were added; all 12 pass.
- `tests/support/fake_http.py` gained streaming modes (text deltas, hand-written event bytes, a dropped stream, an open error, a stream-only error).
- My first version of the connection and timeout tests failed for the wrong reason: the readiness check runs first and reports "not ready" for an unreachable server, so those tests now fail only the streaming request, as a real mid-session loss would.
- Implementation: `post_stream` parses the event stream (ignores comments, blank lines and `event:` lines, stops at `[DONE]`, raises if the stream ends without it) and yields a plain-JSON reply as one event when the server ignores `stream`. An HTTP error on opening raises the new `StreamRefused`, which `generate()` answers with one normal call.
- Checked against the real `llama-server` (7B): the streamed pieces joined equal the returned text, which equals the non-streamed reply, and pieces arrived about 0.08 s apart.
- `pytest -m "not model"`: 578 passed.

## 2026-11-01 · T2.3 Draft through the harness and ask()
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/agent/harness.py, codecompass/online/logging.py, codecompass/online/__init__.py, tests/support/stub_generator.py, tests/online/test_draft_t23.py
- **Outcome:** Changed
### What I asked for
Task T2.3 of Spec 004: pass the model's text, as it is written, from the generator up to an optional `on_draft` callback in `ask()`, without ever forwarding tool-call text, and without changing any result or audit log when no callback is given.
### How I checked it
TODO (member)
### What I kept or changed
- Tests first: 15 tests; 10 fail on assertions (nothing is forwarded yet) and 5 pass as guards (no callback means no streaming, and the same run). The full suite still has no other failures.
- Inert `on_draft` / `on_text` parameters were added to `run_agent`, `ask` and `TimedGenerator` (ignored for now) so the tests fail on assertions rather than on unexpected arguments. `StubGenerator` can now stream its canned text in small pieces.
- Design choice to review: the filter forwards everything before a `<tool>` tag and nothing from it onwards, holding back at most five characters that might be the start of a tag. Prose written before a tool request is therefore shown.
- Two of my own tests had bugs (a path type and a fake profile missing a field) and were fixed before review. I approved them, then the filter and the plumbing were implemented; all 15 pass.
- Implementation: a small `_DraftFilter` in `agent/harness.py` (forward text up to a `<tool>` tag, hold back at most five characters that could start one, flush a held tail that never became a tag), `_generate()` that gives the generator a callback only when `on_draft` is set, and the callback passed down through `ask()`, `_agent()`, `_retrieve_and_answer()` and `TimedGenerator`. `pytest -m "not model"`: 593 passed.
- From here on I told the assistant to treat test approval as given and finish the remaining tasks without stopping at each gate; tests are still written and committed before the code.

## 2026-11-01 · T2.4 The draft in the terminal
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_draft_t24.py, docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md
- **Outcome:** Changed
### What I asked for
Task T2.4 of Spec 004: show the model's text live on stderr as an unmistakable, unchecked draft (Q5), with only the checked answer on stdout, and a `--no-draft` option.
### How I checked it
TODO (member)
### What I kept or changed
- Spec change before the tests: I dropped the live "Drafting… N s" counter (it would need a timer thread rewriting a line that is already receiving text) and used closing lines instead: `Draft finished after N s.` and `── Checked answer (replaces the draft above) ──`. Also added: control characters from the model are removed so a draft cannot restyle or overwrite the screen.
- Tests first: 21 tests, 13 failing on assertions at first. Two of my own assertions were wrong (they ignored the next `> ` prompt and the status-line clear sequence), so I corrected them in a separate `test(T2.4)` commit before the implementation commit. The behaviour under test did not change.
- `run_session` takes a `draft` flag and calls `answer(question, on_draft=...)` only when it is set and stderr is a terminal, so the approved T1.1 tests, whose fake answers take only a question, still pass unchanged.
- `pytest -m "not model"`: 614 passed.

## 2026-11-01 · T2.5 Background warm-up
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/__init__.py, codecompass/online/tui.py, tests/online/test_warmup_t25.py
- **Outcome:** Changed
### What I asked for
Task T2.5 of Spec 004: bring the index current and load the models in the background while I type my first question.
### How I checked it
TODO (member)
### What I kept or changed
- New `online.warm_up(repo, config=...)`: runs `ensure_current`, opens the index and embeds one query (loads the embedder), and runs the re-ranker once, on the shared models from T0.1, printing nothing. The TUI runs it in a daemon thread on a terminal only, after a good start-up.
- A question asked while it runs shows `Preparing index and models…` and waits; a warm-up error is dropped in the thread and the question reports its own; `/exit` never waits (daemon thread); piped input and failed start-ups start nothing.
- Tests first: 11 tests, 7 failing on the missing behaviour and 4 guards. I tightened one test that passed vacuously because `pytest.raises(Exception)` also caught the stub's `NotImplementedError`. The threaded tests passed 8 runs out of 8.
- Risk to know about: a daemon thread that is still loading a model when the process exits could in principle misbehave at interpreter shutdown. I did not see it, and a clean `/exit` normally comes after the warm-up has finished.
- `pytest -m "not model"`: 625 passed.
