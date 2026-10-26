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
