# Tasks 002: Online Query Pipeline

**Implements:** Plan 002 / Spec 002 | **Constitution:** v1.4.0

## How to use this list

Do **one task at a time, in order** (respect "Depends on"). Every task follows the constitution's TDD cycle (Article IX.3):

1. **Write the tests listed under "Tests first".** Run them and show that they fail for the expected reason (missing behaviour, not a typo or import error). **Stop. A human approves the tests.**
2. Write the minimum code to satisfy the tests. Re-run and fix the code until **all** pass.
3. Refactor with tests green. Run the full required suite: `pytest -m "not model"`.
4. Commit the tests first, then the implementation (two commits, in that order).

**Never edit an approved test to make it pass.** If a test looks wrong, stop and raise it.
**Stay inside "Touches".** If another file needs to change, stop and ask.
**Done when** always includes: the task's tests pass, the full required suite is green, no skipped or xfail tests without a written reason, no new unpinned dependencies.

Paths are under `codecompass/online/` (code) and `tests/online/` (tests) unless stated. "Fixture repo" means the scripted git repository from Sprint 1 (extended in T0.2 if needed). The offline pipeline's public API (`ensure_current`, `open_index`, `status`) is imported from `codecompass.offline`.

---

## S0: Skeleton and test support

**T0.1 Online package skeleton and config**
- Goal: package layout from the plan, online-specific config loader (retrieval params, generator profiles, tool settings), merged with offline config.
- Tests first: package imports; default retrieval params loaded (`vector_k=50`, `keyword_k=50`, `rrf_constant=60`, `rerank_k=50`, `final_k=8`); profile loader returns `dev` and `prod` profiles; unknown profile raises a loud error; `MAX_VERIFIER_ROUNDS` is 3; all k values, RRF constant, and tool settings are named config values, not hard-coded.
- ACs: AC-2.5, AC-5.9, FR-4, FR-17. | Touches: `__init__.py`, `config.py`, `models.py`. | Depends on: Sprint 1 complete.
- **Follow-up (resolved, Q2):** `max_verifier_rounds` and `allowed_tools` stay configurable (constitution 1.3.0); validation is added by T0.5. The approved test is unchanged.

**T0.2 Extended fixture repo**
- Goal: extend the Sprint 1 fixture-repo builder with additional commits that have meaningful commit messages (e.g. "fix auth timeout by adding retry logic") so verifier-tool tests can assert on `git log` / `git blame` output.
- Tests first: the builder creates commits with known messages, authors, and dates; `git log` on a fixture file returns the expected entries; `git blame` on a fixture file returns the expected commit info.
- ACs: enables US3 testing. | Touches: `tests/support/fixture_repo.py`. | Depends on: T0.1.

**T0.3 Stub generator**
- Goal: a deterministic `StubGenerator` that returns canned responses (configurable per test). Supports: a plain answer with valid citations, an answer with a tool-call request, an answer with invalid citations, an answer with no `Sources` section, a malformed tool-call response. Also implements `count_tokens` (whitespace-separated tokens) for budgeting tests (plan D4).
- Tests first: stub returns the configured response; `count_tokens` is deterministic; calling `generate()` with messages returns the expected text; multiple calls cycle through configured responses (for multi-round tests).
- ACs: enables Article IX.7. | Touches: `tests/support/stub_generator.py`. | Depends on: T0.1.

**T0.4 Stub re-ranker**
- Goal: a deterministic `StubReranker` that scores chunks by a fixed function (e.g. text length descending) so re-ranking tests are model-free.
- Tests first: stub returns scores in deterministic order; same input gives the same output; scores are floats.
- ACs: enables Article IX.7. | Touches: `tests/support/stub_reranker.py`. | Depends on: T0.1.

**T0.5 Tool settings validation**
- Tests first: the default `max_verifier_rounds` is 3; a configured 5 and a configured 0 load; `-1`, `2.5`, `"3"` and `true` fail loudly naming Article V.1; `allowed_tools` defaults to both tools; a configured `["git_log"]` loads; a list naming any other tool (e.g. `"cat"`) fails loudly naming Article V.2; `execute` refuses a call to a tool switched off in `settings.allowed_tools`, with a clear error output, and still refuses an unlisted tool (T5.4).
- ACs: AC-3.9, FR-6. | Touches: `config.py`, `agent/tools.py`. | Depends on: T5.4.

## S1: RRF merge

**T1.1 RRF scoring and merge**
- Tests first: two ranked lists with no overlap produce correct RRF scores (`1/(60+rank)` per item); two lists with full overlap produce summed scores; a chunk in both lists appears once with the sum of both contributions; the result is sorted by score descending; ties broken deterministically (by chunk id); the output is truncated to k items.
- ACs: AC-2.3, AC-2.4. | Touches: `retrieval/rrf.py`. | Depends on: T0.1.

**T1.2 RRF configuration**
- Tests first: changing the RRF constant changes scores; changing k changes the output length; an empty input list returns an empty result; a single-item list returns that item.
- ACs: AC-2.5. | Touches: `retrieval/rrf.py`. | Depends on: T1.1.

## S2: Retrieval wrappers

**T2.1 Vector search wrapper**
- Tests first: given a query vector and read-only vector store handles, returns the top-k chunk ids ranked by cosine similarity; k is configurable; an empty index returns an empty list.
- ACs: AC-2.1 (vector side). | Touches: `retrieval/vector.py`. | Depends on: T0.1.

**T2.2 Keyword search wrapper**
- Tests first: given a query string and read-only keyword index handles, returns the top-k chunk ids ranked by BM25; k is configurable; an empty index returns an empty list; exact identifier lookup works (e.g. `get_user_by_id`).
- ACs: AC-2.1 (keyword side). | Touches: `retrieval/keyword.py`. | Depends on: T0.1.

**T2.3 Query embedding**
- Tests first: the question is embedded with `handles.embed_query` (plan §3, D1), never by importing `codecompass.offline.embedding`; the result is a single vector of the index's dimension; the embedder instance given to `ensure_current` is the same one given to `open_index` (O2); an `EmbedderMismatchError` from `open_index` propagates as a clear error and is never caught and ignored (the refusal itself is tested offline in `tests/offline/test_query_embedder.py`).
- ACs: AC-2.2, FR-1. | Touches: `retrieval/embedder.py`. | Depends on: T2.1 and PR `fix/query-embedder` (plan §3).

**T2.4 Hybrid retrieval integration**
- Tests first (stub embedder, real stores on fixture repo): a question retrieves results from both vector and keyword paths; results are passed through RRF merge; the merged list contains chunks from both sources; a chunk found by both is not duplicated; the output has at most `rerank_k` items.
- ACs: AC-2.1, AC-2.3, AC-2.4. | Touches: `retrieval/` integration test. | Depends on: T1.1, T2.1, T2.2, T2.3.

## S3: Cross-encoder re-ranker

**T3.1 Re-ranker protocol and stub**
- Tests first: `StubReranker` scores each chunk deterministically; re-ordering by score produces a predictable order; the interface accepts a query string and a list of chunk texts and returns a list of scores.
- ACs: AC-2.7 (protocol). | Touches: `retrieval/reranker.py`, `tests/support/stub_reranker.py`. | Depends on: T0.4.

**T3.2 Re-ranker integration**
- Tests first (stub re-ranker): the re-ranker receives only the merged shortlist, never the whole index; the output is truncated to `final_k`; the re-ranker is not called if the shortlist is empty; chunk ordering after re-ranking differs from the RRF ordering (proves re-ranking happened).
- ACs: AC-2.7, AC-2.4. | Touches: `retrieval/reranker.py`. | Depends on: T3.1, T2.4.

## S4: Context assembly

**T4.1 Chunk formatting**
- Tests first: each chunk is formatted as a block with file path, line range, language, and indexed commit; the header text before ` | ` is exactly the `Sources` code-citation form (`path, lines X-Y (indexed at abc1234)`); the generator sees plain text with metadata, never raw vectors or chunk ids; the format matches the plan's D3 template.
- ACs: AC-1.4, FR-5. | Touches: `context.py`. | Depends on: T0.1.

**T4.2 Context budgeting**
- Tests first: chunks are added in re-ranker score order while they fit the chunk budget; a chunk that does not fit is dropped and later chunks are still tried (T19.2); token counts come from `Generator.count_tokens`; `final_k` is capped by the budget (fewer chunks if the budget is tight); a very small budget results in zero chunks (handled gracefully); the profile's `max_tokens` and `MAX_VERIFIER_ROUNDS × max_tool_output_tokens` are reserved before chunks are added; a configured `max_verifier_rounds` whose reserve leaves no room for chunks fails loudly at startup, naming Article V.1; two profiles that differ only in `context_window` yield different chunk counts for the same input, and `context.py` names no model (the budget comes only from the active profile).
- ACs: AC-2.6, AC-5.7, plan D4. | Touches: `context.py`. | Depends on: T4.1, T3.2, T0.3.

## S5: Verifier tools

**T5.1 Tool argument validation**
- Tests first: a path with a `..` component is rejected; an absolute path is rejected; a path starting with `-` is rejected; a path that does not exist at the indexed commit is rejected; a valid repo-relative path passes, including names with `(`, `)` or `$` (e.g. `app/(auth)/page.tsx`); a line range `42-58` passes; a reversed range `58-42` is rejected; a range past the file's last line is rejected; a non-numeric range is rejected; `n` outside 1..`git_log_limit` is rejected.
- ACs: AC-3.3, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T0.2.

**T5.2 git_blame executor**
- Tests first: `git_blame` runs `--porcelain` against the indexed commit (not HEAD); the result carries parsed commit records (hash, author, date, subject) with the expected values; with a line range, only those lines are blamed; the command runs with `shell=False` and `--` before the path; a timeout produces an error message, not a crash; the rendered text is one line per commit.
- ACs: AC-3.2, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T5.1.

**T5.3 git_log executor**
- Tests first: `git_log` runs against the indexed commit; fields are split on the 0x1F separator, so an author name with spaces and a subject with commas parse exactly; the output is limited to `n` commits; the command runs with `shell=False`; a timeout produces an error message; an empty log (file with no history) returns an empty result.
- ACs: AC-3.2, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T5.1.

**T5.4 Tool allow list**
- Tests first: requesting `git_blame` or `git_log` succeeds; requesting any other tool name (e.g. `git_diff`, `cat`, `ls`) is rejected with a clear error message appended to context.
- ACs: AC-3.2. | Touches: `agent/tools.py`. | Depends on: T5.2, T5.3.

**T5.5 Tool-result caching**
- Tests first: calling the same tool with the same args twice returns the cached result; the cache records `cache_hit=True` on the second call; different args produce different cache keys; the cache is a per-call dictionary (not shared across `ask` calls).
- ACs: AC-3.5, plan D8. | Touches: `agent/cache.py`. | Depends on: T5.2.

**T5.6 Tool output cap**
- Tests first: a tool result over `max_tool_output_tokens` is truncated and ends with `[output truncated: N more lines]`; a result under the cap is unchanged; truncation never splits a commit record line.
- ACs: AC-3.5, plan D4. | Touches: `agent/tools.py`. | Depends on: T5.2, T5.3, T0.3.

## S6: Tool-call parser

**T6.1 Parse tool calls from model output**
- Tests first: `<tool>git_blame(path="src/auth.py", lines="42-58")</tool>` is parsed into `ToolCall(tool="git_blame", args={"path": "src/auth.py", "lines": "42-58"})`; `<tool>git_log(path="src/auth.py", n=10)</tool>` is parsed correctly; a response with no `<tool>` tag is classified as a final answer; a response with malformed `<tool>` content (e.g. missing closing tag, bad syntax) is treated as a final answer, not a crash; multiple tool calls in one response: only the first is executed (Article V.1 allows one tool per round).
- ACs: AC-3.8, FR-13. | Touches: `agent/tool_parser.py`. | Depends on: T0.1.

## S7: Generator

**T7.1 Model profile loading**
- Tests first: loading `dev` profile returns the 14B config; loading `prod` returns the 32B config; an unknown profile name raises a loud error; the default profile is `dev`; `GENERATOR_PROFILE` env var overrides the default; each profile has all required fields (model_id, backend, context_window, server_args, temperature, seed, max_tokens, stop_tokens, cache_prompt); a `backend` other than `llama.cpp` is rejected loudly; with default config every local model device is `cpu` (re-ranker, embedder) and no profile field requires a GPU, so CPU-only operation works out of the box.
- ACs: AC-5.1, AC-5.2, AC-5.9, AC-5.11, FR-17. | Touches: `generator/profiles.py`. | Depends on: T0.1.

**T7.2 LlamaServerGenerator**
- Tests first (mocked HTTP): `generate(messages)` sends a POST to `/v1/chat/completions` with the correct chat format; the response is parsed and the assistant content returned; stop tokens from the profile are included in the request; temperature and max_tokens from the profile are sent; the profile's `cache_prompt` value is sent with every request (plan D13 item 10); a connection error raises a clear error, not a hang; a timeout raises a clear error.
- ACs: AC-5.3, AC-5.4, AC-5.6, FR-12. | Touches: `generator/llama.py`. | Depends on: T7.1.

**T7.3 Health check**
- Tests first (mocked HTTP): `health_check()` pings `/health` and returns True on 200; returns False on connection error; it fails loudly when `/props` reports a per-slot `n_ctx` smaller than the profile's `context_window`, or a model path that does not end with the profile's `gguf_file`; the generator refuses to generate if the health check fails; the launch command built from the profile contains `-c <context_window>`, `--host 127.0.0.1` and the profile's `server_args`.
- ACs: AC-5.10, AC-5.12. | Touches: `generator/server.py`. | Depends on: T7.2.

**T7.4 Localhost binding**
- Tests first: the default server URL is `http://127.0.0.1:<port>`; a config with a non-localhost URL is accepted (for flexibility) but logged as a warning.
- ACs: AC-5.5. | Touches: `generator/llama.py`. | Depends on: T7.2.

## S8: Agent harness

**T8.1 Single-round answer (no tools)**
- Tests first (stub generator returns an answer directly): the harness calls `generate` once; the response is returned as the answer; round count is 0; no tool calls in the audit log.
- ACs: AC-3.1 (no-tool path). | Touches: `agent/harness.py`. | Depends on: T6.1, T7.2.

**T8.2 Multi-round tool loop**
- Tests first (stub generator returns a tool call on round 0, then an answer on round 1): the harness executes the tool, appends the result to messages, calls generate again; the audit log shows round 0 with a tool call and round 1 with the answer; tool results are appended to context as `user`-role messages wrapped in `<tool_result>` tags (plan D16), after the model's `assistant` tool request.
- ACs: AC-3.1, AC-3.5, AC-3.6. | Touches: `agent/harness.py`. | Depends on: T8.1, T5.4, T5.5.

**T8.3 Round limit enforcement**
- Tests first (stub generator always requests tools): exactly `max_verifier_rounds` tools execute (tested with the default 3 and a configured 1 and 5); the harness then makes one final generate call whose messages say no more tools are available; any `<tool>` block in that final response is removed before the citation checker; at most `max_verifier_rounds + 2` generator calls are made (5 by default); the audit log records all 3 tool rounds and the final call; when a response contains two `<tool>` blocks, only the first executes.
- ACs: AC-3.1, FR-6. | Touches: `agent/harness.py`. | Depends on: T8.2.

**T8.4 Tool error handling**
- Tests first: a rejected tool call (bad args, disallowed tool) produces an error message in context; the model sees the error and gets another round; a tool timeout produces an error message; the harness does not crash on any tool failure.
- ACs: AC-3.3, AC-3.4. | Touches: `agent/harness.py`. | Depends on: T8.2.

**T8.5 Message building**
- Tests first: the system prompt is the first message; context chunks are in the user message; tool results are appended as separate `user` messages in the D16 `<tool_result>` wrapper (errors carry an `error` attribute); no message ever has a role other than `system`, `user` or `assistant`; the conversation history grows with each round and is append-only: every earlier message is unchanged, in the same order, in each later call (plan D13 item 10); the system prompt matches the plan's D14 template, including rule 4 (state what could not be determined) and rule 5 (say so when commit history gives no rationale; never invent one); a `git_log` or `git_blame` result with no commits is wrapped with the D16 `No commit history found for <path>` text, never an empty block; the D15 final-call message asks the model to state what it could not determine.
- ACs: AC-1.4, AC-1.3, AC-3.7, plan D14, D16. | Touches: `agent/harness.py`. | Depends on: T4.1.

**T8.6 Malformed tool-call retry** (added after Sprint 2; v2 architecture E6)
- Tests first: `tool_parser.malformed_blocks()` finds `<tool>` blocks that `parse_tool_calls()` cannot read, including an unclosed tail, and finds none in a valid call or a plain answer; a malformed call is sent back as a D16 `<tool_result error="malformed tool call">` message that shows the correct format, and the model gets another round; the malformed attempt uses one round (with `max_verifier_rounds = 1` a following valid call is not run and the D15 final call is made); a model that only ever writes malformed calls makes exactly `max_verifier_rounds + 2` generator calls; the attempt is logged with `malformed: true`, `tool: null`, `error: true`; text with no `<tool>` tag is still the final answer; with tools disabled (D17) malformed blocks are stripped and nothing is retried. T6.1 is unchanged: `parse_tool_calls()` still returns `[]` for malformed blocks.
- ACs: AC-3.3, FR-6; plan D5, D15, D16. | Touches: `agent/tool_parser.py`, `agent/harness.py`. | Depends on: T8.4, T6.1.

## S9: Citation checker

**T9.1 Source entry parser**
- Tests first: `[1] src/auth/client.py, lines 42-58 (indexed at a1b2c3d)` is parsed as a code source with path, start_line=42, end_line=58, commit_prefix=`a1b2c3d`; `[2] Commit a1b2c3d, "handle flaky upstream", Alice, 2024-03-14` is parsed as a commit source; a malformed entry is flagged as unparseable; an answer with no `Sources` section returns an empty source list.
- ACs: AC-4.5. | Touches: `citation/parser.py`. | Depends on: T0.1.

**T9.2 Citation checker: outcome F (all valid)**
- Tests first: an answer where every code source is covered by retrieved chunks (same path, every cited line inside the retrieved chunks' ranges, including a range spanning two adjacent chunks; commit prefix matches) and every commit source matches a parsed commit record from a tool result → outcome F; the answer is shown normally.
- ACs: AC-4.1, AC-4.3. | Touches: `citation/checker.py`. | Depends on: T9.1.

**T9.3 Citation checker: outcome G (invalid citation)**
- Tests first: a code source citing a file not in retrieved context → outcome G; a code source with a wrong line range → outcome G; a code source whose range overlaps a retrieved chunk but extends past it → outcome G; a commit source citing a hash not in any tool result → outcome G; an inline marker `[N]` with no corresponding `Sources` entry → outcome G; a `Sources` entry with no matching inline marker → outcome G; no `Sources` section at all → outcome G.
- ACs: AC-4.1, AC-4.4, AC-4.5. | Touches: `citation/checker.py`. | Depends on: T9.2.

**T9.4 Flagged answer formatting**
- Tests first: a flagged answer has a banner: `⚠ WARNING: Some citations in this answer could not be verified...`; each unverified source is prefixed with `[UNVERIFIED]`; a flagged answer is never rendered identically to a cited answer (banner is always present for G).
- ACs: AC-4.4, FR-10. | Touches: `citation/formatter.py`. | Depends on: T9.3.

**T9.5 Harness-copied commit metadata**
- Tests first: when the answer contains a commit source `[N] Commit hash, ...`, the harness replaces the model's subject, author, and date with values from the matching commit record of a `git log` or `git blame --porcelain` tool result; if the hash is not in any tool result, the source is marked unverified; the replacement is exact (no model-generated commit details survive).
- ACs: AC-4.6, FR-16. | Touches: `citation/checker.py`. | Depends on: T9.3, T5.3.

**T9.7 Uncited answers and uncited parts**
- Tests first: an answer with no markers and no `Sources` entries renders with the AC-4.8 note and without the banner; an answer with citations whose paragraphs or list items lack a marker gets ` (not cited)` on each such part and the AC-4.9 note at the top; headings, fenced code blocks and lines ending in `:` are not tagged; a fully cited F answer is unchanged; a G answer with uncited parts shows the banner, then the note; outcomes are unchanged (no-citation answers stay G, partly cited answers with valid citations stay F).
- **Approved test change (needs reviewer sign-off, Article IX.3):** T9.4's `test_no_sources_section_still_gets_banner` expects the banner on an uncited answer; spec AC-4.8 replaces that with the uncited note.
- ACs: AC-4.8, AC-4.9, FR-19. | Touches: `citation/formatter.py`, `tests/online/test_citation_format_t94.py` (the one approved test above). | Depends on: T9.4.

**T9.6 Citation checker is non-bypassable**
- Tests first: the `ask` function always runs the citation checker; there is no config flag to skip it; calling `ask` with a stub generator that returns invalid citations always produces a G outcome.
- ACs: AC-4.2. | Touches: `citation/checker.py`, integration test. | Depends on: T9.3.

## S10: Index freshness

**T10.1 ensure_current integration**
- Tests first: `ask` calls `ensure_current` before retrieval; if `ensure_current` returns `ok=True`, retrieval proceeds normally; if it returns `ok=False` with `status="failed"`, the stale flag is set and retrieval proceeds from the existing index; the same holds for `ok=False` with `status="locked"` (lock timeout): stale flag set, answer from the existing index, never silently unflagged; if `ensure_current` fails and **no index exists yet** (`status()` reports `empty`), `ask` returns an answer saying no index is available yet (with the failure reason), attempts no retrieval or generation, and does not raise.
- ACs: AC-6.1, AC-6.2, AC-6.3. | Touches: `__init__.py`. | Depends on: T8.1, T9.2.

**T10.2 Stale-index fallback**
- Tests first: when `ensure_current` fails, the answer includes a stale-index warning: `⚠ WARNING: The index may be out of date...`; the `QueryResult.stale_index` is True; the `QueryResult.stale_message` contains the failure reason; the answer is still produced (not an error).
- ACs: AC-6.3, FR-14. | Touches: `__init__.py`. | Depends on: T10.1.

**T10.3 Empty index**
- Tests first: when the index is empty (no chunks), `ask` returns an answer saying no evidence is available; no retrieval or generation is attempted; the answer is not flagged as stale (it's just empty); when the index has chunks but retrieval returns none for the question, or the context budget leaves zero chunks, `ask` returns an "I could not find enough evidence" answer without calling the generator.
- ACs: AC-6.3 (edge case), AC-1.3. | Touches: `__init__.py`. | Depends on: T10.1.

## S11: Audit logging

**T11.1 Per-query audit log**
- Tests first: every `ask` call produces an audit log dict containing: question text, active profile name, model id, list of retrieved chunks with RRF and reranker scores, list of tool calls with round number, tool name, args, cache hit/miss, citation outcome (F or G), and per-stage timings (retrieval, reranking, generation, tool execution, citation check).
- ACs: AC-7.1. | Touches: `logging.py`. | Depends on: T8.2, T9.2.

**T11.2 Audit log persistence**
- Tests first: the audit log is written to a JSON file under the configured `query_log_dir`; the file name includes a timestamp; the file is valid JSON; the stale-index warning, if triggered, is recorded.
- ACs: AC-7.2, AC-7.3. | Touches: `logging.py`. | Depends on: T11.1.

**T11.3 Profile and model in log**
- Tests first: the audit log records the active profile name, resolved model id, `cache_prompt` setting and pipeline mode (D17, Article VII.3) and `max_verifier_rounds` (Article V.1); they are recorded on every query log.
- ACs: AC-5.8, AC-7.1. | Touches: `logging.py`. | Depends on: T11.1.

## S12: Public API and CLI

**T12.1 `ask` function**
- Tests first (stub generator, stub reranker, stub embedder): `ask(repo, question, config=config, profile="dev")` returns a `QueryResult` with answer, sources, citation outcome, stale flag, and audit log; the function does not print to stdout; the result contains all fields from the spec.
- ACs: AC-9.1, AC-9.2. | Touches: `__init__.py`. | Depends on: T10.2, T11.1.

**T12.2 Full pipeline integration test**
- Tests first (stub generator, stub reranker, stub embedder, real stores on fixture repo): an `ask` call goes through: ensure_current → open_index → embed query → vector search → keyword search → RRF → rerank → context assembly → generate → tool loop → citation check → result. Assert the result has the expected structure and the audit log has all stages.
- ACs: all P1 and P2 ACs (integration). | Touches: integration test only. | Depends on: T12.1.

**T12.3 CLI entry point**
- Tests first: `python -m codecompass.online.cli ask <repo> "<question>"` runs and prints the answer; `--profile prod` selects the prod profile; `--verbose` prints retrieval details; flagged answers display the banner; stale-index warnings are displayed before the answer; exit code 0 on success; at startup the CLI logs the active profile name and resolved model id once (to stderr, so the printed answer stays clean).
- ACs: AC-8.1, AC-8.2, AC-8.3, AC-8.4, AC-5.8. | Touches: `cli.py`. | Depends on: T12.1.

**T12.4 Evaluation modes**
- Tests first (stub generator, stub re-ranker, stub embedder): `pipeline.mode` defaults to `rag_tools`; an unknown mode raises a loud error at startup; `rag_tools` behaves as T12.2; `rag` retrieves and re-ranks, leaves D14 rule 3 out of the system prompt, runs no tool even when the stub requests one (the block is removed and logged), and the answer still goes to the citation checker; `no_retrieval` calls `ensure_current` but does no embedding, search or re-rank, sends no chunks, and a stub answer citing a file is flagged G; every mode uses the same profile and model id; the audit log records the mode.
- ACs: AC-10.1–10.5, FR-18. | Touches: `config.py`, `__init__.py`. | Depends on: T12.2.

## S13: Real model tests (local only, `model` marker)

**T13.1 Real cross-encoder re-ranker**
- Tests first (`model`): `BgeReranker` loads `BAAI/bge-reranker-v2-m3` at the revision pinned in config (`reranker.revision`, Article VIII.1); re-ranking a question against a relevant chunk and an irrelevant chunk gives the relevant chunk a higher score; batch scoring produces deterministic results. Required-suite test: `reranker.revision` is a config field, and the loader passes it to the model library.
- ACs: AC-2.7. | Touches: `retrieval/reranker.py`, `config.py` (adds `RerankerConfig.revision`). | Depends on: T3.2.

**T13.2 Real generator smoke test**
- Tests first (`model`): `LlamaServerGenerator` connects to a running `llama-server`; a simple question about the fixture repo produces an answer with a `Sources` section; the citation checker runs and classifies the outcome.
- ACs: AC-5.1–5.11, end-to-end. | Touches: tests only. | Depends on: T12.2.

**T13.3 End-to-end smoke test**
- Tests first (`model`): `ask` on the fixture repo with the real generator and real re-ranker produces a grounded answer; the audit log is complete; the citation checker outcome is recorded; run with both `dev` and `prod` profiles if both are available.
- ACs: whole spec. | Touches: tests only. | Depends on: T13.1, T13.2.

## S14: Code tools (Constitution 1.4.0, plan D18)

**T14.1 `open_file`**
- Tests first: `open_file(path, lines)` at the indexed commit returns the D3 header and the requested lines; path and line validation reuse D6 (outside the repo, missing file, out-of-range lines are errors fed back to the model); a range that does not fit `max_tool_output_tokens` returns whole lines from the start of the range plus the `[showing lines X-Y; ...]` marker, and the returned chunk covers only the lines shown; `open_file(path)` without `lines` returns an outline of indexed symbols with line ranges and no citable chunk; results are cached per query.
- ACs: Article V.2, VI.4; plan D6, D7, D18. | Touches: `agent/tools.py`. | Depends on: T5.4.

**T14.2 `search_again`**
- Tests first (stub embedder, stub re-ranker, real stores on the fixture repo): the query runs through hybrid retrieval and the re-ranker; chunks already in context are skipped; returned chunks fit `max_tool_output_tokens` and use the D3 header; an empty or over-200-character query is an error fed back to the model; no new chunks gives a plain "nothing new found" result.
- ACs: Article IV, V.2; plan D18. | Touches: `agent/tools.py`, `retrieval/hybrid.py` (read-only use). | Depends on: T2.4, T3.2, T14.1.

**T14.3 Wiring: prompt, config and citation evidence**
- Tests first: `tools.allowed_tools` defaults to all four tools and still rejects names outside the list; the D14 tool rule describes `open_file` and `search_again` with one example each, and the malformed-call hint (T8.6) shows all four formats; chunks shown by tools are collected by the harness and passed to the citation checker, so a citation to them is F and a citation to unseen code is still G; `rag` and `no_retrieval` modes are unchanged; spec 002 tool list updated.
- **Approved test changes (need reviewer sign-off, Article IX.3):** Constitution 1.4.0 makes three approved tests out of date: `test_tool_allowlist_t54.py::test_allowed_tools_constant` and `test_tool_settings_t05.py` (default allowed tools) now expect all four tools, and `test_harness_messages_t85.py` (D14 template) has the new tool rule 3. No other assertion changes.
- ACs: Article V.2, VI.1, VI.4; plan D14, D17, D18. | Touches: `agent/harness.py`, `agent/tools.py`, `config.py`, `__init__.py`, `offline/stores/vector.py` (read-only `symbols_for_path`), spec 002, and the three approved tests above. | Depends on: T14.1, T14.2, T8.6.

## S15: Evidence gate (plan D19)

**T15.1 Evidence gate**
- Tests first (stub embedder, a stub re-ranker that returns chosen scores, stub generator, real stores on small fixture repositories): a best score below `retrieval.min_top_score` gives the no-evidence answer with **zero** generator calls and no tool run, in `rag_tools` and `rag`; a best score equal to the threshold proceeds to the generator; one good chunk among poor ones proceeds; 0 turns the gate off; the refusal lists up to `retrieval.closest_files` distinct files best first, each once with its best chunk's line range, under the AC-1.7 line, and fewer when the repo has fewer; 0 lists none; the list is never read as citations (no sources, outcome G with no entries); the log has `evidence_gate` with the threshold, the best score and `passed`, and every retrieved entry is `sent: false` when the gate refuses; `no_retrieval` and an empty index have no `evidence_gate` and no list; `retrieval.min_top_score` defaults to 0.02 and `retrieval.closest_files` to 3, both are accepted from the config file, and a bad value (min_top_score: negative, above 1, a string, a bool, None; closest_files: negative, a fraction, a string, a bool, None) raises `ValueError` naming the setting.
- **Existing approved tests:** the stub re-ranker scores by word overlap, so a question sharing no word with any chunk scores 0.0 and would now be refused. Run the full suite after the change. If an approved test fails for that reason, stop and ask (Article IX.3); do not edit it.
- **Approved test changes (need reviewer sign-off, Article IX.3):** with the gate on by default, six approved tests ask a question that shares no word with any chunk ("Why retry?", "Why?"), so the stub re-ranker scores it 0.0 and the gate refuses. They are about citations, stale warnings, modes and the CLI, not the gate, so the gate is switched off in their setup (`min_top_score = 0`): `tests/online/ask_support.py::config()` (used by `test_citation_nonbypassable_t96`, `test_modes_t124`, `test_stale_fallback_t102`), the `setup` fixture of `test_cli_t123.py`, and the inline config of the end-to-end test in `test_tui_main_t12.py`. No assertion and no question changes. The stub re-ranker is left alone: `test_stub_reranker_t04` pins its scoring.
- ACs: AC-1.5, 1.6, 1.7, 7.4, FR-20; Article I.2, I.3, V.4, X.2. | Touches: `config.py`, `__init__.py`, and the three test setups above. | Depends on: T10.3, T11.1.

## S16: Unreferenced sources (plan D20)

**T16.1 Unreferenced sources**
- Tests first (checker and formatter on the T9.3 fixture chunks, then `ask` with a stub generator): an entry that matches the context but whose marker the body does not use is in `unreferenced` and still in `unverified`, outcome G; an entry that fails the evidence check, a duplicate marker, and a marker with no entry are never in `unreferenced`; a commit entry that matches a tool result but is not referenced is; a fully referenced answer has an empty `unreferenced` and outcome F; when every flagged entry is unreferenced the answer starts with the AC-4.10 banner and the entry has `[NOT REFERENCED IN ANSWER] ` and no `[UNVERIFIED]`; with a failed entry as well, the AC-4.4 banner is used and each entry keeps its own prefix; a marker with no entry is unchanged; the banner never says the sources are true; the flagged text is never identical to the cited text; through `ask`, a real source listed without a marker gives G with the new banner, and the log's `citation` has `unreferenced` only in that case.
- **Approved test risk:** `test_entry_without_marker_is_g` requires the entry to stay in `unverified`; `test_full_pipeline_t122` requires `{"outcome": "F", "unverified": []}` for an ordinary answer. Both are kept by design. If another approved test fails, stop and ask (Article IX.3).
- ACs: AC-4.4, 4.10, 7.5; Article VI.3, VI.5. | Touches: `citation/checker.py`, `citation/formatter.py`, `models.py`, `__init__.py`. | Depends on: T9.3, T9.4, T11.1.

## S17: Questions with no words (2 Nov development test, problem 11)

**T17.1 Reject questions with no words**
- Tests first (stub generator, re-ranker and embedder; indexing and retrieval replaced by a stub that fails the test if it is reached): `ask` raises `ValueError` for a question with no letter or digit, using one input per realistic wrong check (`""`, `"   "`, `"\n\t"`, `"."`, `"?"`, a run of ASCII symbols, `"___"`, an emoji); for each, the generator is never called, no audit log is written, and the message says the question has no words and that each question is answered on its own; a question with spaces around it, a Chinese question and `"x"` still run, and the logged question is unchanged; the CLI shows one `error:` line, prints nothing to stdout and exits 1.
- Added after the tests were written, while task numbers were agreed in the team; the tests and code match this entry.
- ACs: AC-9.3, AC-8.1. | Touches: `__init__.py`. | Depends on: T12.1, T12.3.

## S18: Audit log on failure (2 Nov development test, problem 7)

**T18.1 Write the audit log when a question fails**
- Tests first (stub re-ranker and embedder, a stub generator that raises, real stores on the fixture repository): when the generator raises `TimeoutError`, the same exception object reaches the caller and exactly one log is written with the question, `error` = `{"type", "message"}`, the retrieved chunks and a generation time above 0; an exception from `ensure_current` is logged; `KeyboardInterrupt` is logged and re-raised; when `write_log` itself raises during the error, the caller still gets the original error; a successful answer has no `error` key in the returned log or on disk; an unknown `pipeline.mode` raises and writes no log; through the CLI, a generator timeout prints one `error:` line, exits 1 and leaves a log.
- ACs: AC-7.6, AC-7.1, AC-8.1; Article V.4. | Touches: `__init__.py`. | Depends on: T11.2, T12.1, T12.3, T17.1.

**T18.2 Log a failure while counting tokens**
- Found in a real run after T18.1 merged: with `llama-server` not answering, `ask` failed in `check_round_reserve` (the first `/tokenize` call), which ran before the T18.1 `try`, so no log was written.
- Tests first (stub re-ranker and embedder, a stub generator whose `count_tokens` raises `GeneratorError`, real stores on the fixture repository): the same error reaches the caller, exactly one log is written with the question and `error` = `{"type": "GeneratorError", "message": ...}`, and the generator is never asked to answer. Approved tests: none change.
- ACs: AC-7.6; Article V.4. | Touches: `__init__.py`. | Depends on: T18.1.

## S19: Test-report fixes (dev test, 2 Nov 2026)

**T19.1 Code-tool results reach the model**
- Bug (dev test B3, D2, D6, D11): `tool_result_message` sent `No commit history found for <path>` for every result without commits, so the model never saw what `open_file` and `search_again` returned, while their chunks were still added as citable evidence.
- Tests first (stub generator, `FakeTools`, `run_agent`): an `open_file` code result reaches the model with its D3 header and code; an `open_file` outline, and the hint given when no outline exists, reach it as their text; `search_again` chunks reach it with each chunk's header and text; `search_again`'s "Nothing new found" and "too large to show" replies reach it as their text; none of these says `No commit history found`; every chunk the harness adds as evidence (`AgentRun.chunks`) is in a message the model received; a `git_log` or `git_blame` run with no commits still says `No commit history found for <path>` (plus the line range for blame); the D16 wrapper and the `user` role are unchanged.
- **Approved tests:** none change. `test_empty_history_is_stated_plainly` (T8.5) uses `git_log` and must stay green.
- ACs: AC-3.5, 3.7, 4.1; Article I.1, V.3, V.5, VI.1; plan D16, D18. | Touches: `agent/harness.py`, plan D16, the T8.5 entry's wording. | Depends on: T8.5, T14.1, T14.2.

**T19.2 An oversized chunk does not block the others**
- Bug (dev test B2): `fit_chunks` stopped at the first chunk that did not fit. The top-ranked chunk was larger than the whole chunk budget, so no chunk was sent and the answer (ranked 3rd) never reached the model.
- Tests first (`context.fit_chunks` with the stub generator's token count): when the first chunk is over budget, the later chunks that fit are kept, in order; an oversized chunk in the middle is skipped and the chunks around it are kept; a chunk too big for the room left is skipped while a later, smaller one that fits is kept; when every chunk is over budget the result is empty; the kept chunks are always in input order and their total cost never exceeds the budget.
- **Approved test change (needs reviewer sign-off, Article IX.3):** the `test_context_budget_t42.py` module docstring said "the first that does not fit ends it"; it now describes the skip rule. Docstring only: no assertion changes.
- ACs: AC-2.6; Article I.2, IV.2, VIII.4; plan D4. | Touches: `context.py`, plan D4, the T4.2 entry's wording. | Depends on: T4.2.

**T19.3 ask does not time out on slow machines**
- Bug (dev test, item 6): `generate()` without `on_text` made one non-streaming request, so `timeout_seconds` (default 120) capped the whole answer. On a 16 GB laptop, prefill alone is about 38 tok/s (MODEL-SETUP.md section 5), so a normal question can time out before the model finishes. The `ask` CLI, `ask()` in Python, the notebook and the evaluation all take this path.
- Fix: every call streams (`stream: true`), with or without `on_text`, so `timeout_seconds` bounds each wait (before the first piece and between pieces) rather than the whole answer. A new `[generator] connect_timeout_seconds` (default 5) bounds the readiness check, which is the first contact with the server, so a server that never answers fails in seconds. The request payload is otherwise unchanged, and the joined text equals the non-streaming reply.
- Spec change (needs reviewer sign-off): Spec 004 T2.2 and plan (004 section 3, generator) said that without a callback the request is unchanged. Amended to: it streams too. Approved test changes (Article IX.3, sign-off needed): `test_stream_generator_t22.py` `test_a_callback_makes_the_request_stream_and_changes_nothing_else` and `test_without_a_callback_the_request_and_result_are_unchanged` now expect `stream: true` on every call; the module docstring says so.
- Limitation: urllib takes one timeout per socket call, and the wait for response headers is the prefill wait, so the connect bound cannot be set separately for the answer's POST. The POST's connection is bounded by `timeout_seconds`. Only the readiness check (run once per generator, before the first question) uses the connect timeout.
- Tests first (mocked HTTP, `tests/online/test_ask_stream_timeout_t193.py`): no `on_text` still streams and returns the full text; the joined text equals the non-streaming reply; a long answer whose pieces each arrive in time succeeds, and the per-wait timeout is `timeout_seconds`; a server that never answers fails within `connect_timeout_seconds` with the existing "not ready" message; a stream that stops mid-answer raises the existing `GeneratorError`; a refused stream falls back to one normal call; `connect_timeout_seconds` loads, layers and rejects bad values.
- Note: the test for a slow server cannot simulate a socket timeout with the fake; it checks the timeout values passed to `urlopen`.
- ACs: AC-2.5 (Spec 004); Article VIII.1, VIII.2. | Touches: `online/generator/llama.py`, `online/config.py`, `online/__init__.py`, `online/tui.py`, `codecompass.toml`, `README.md`, the T2.2 wording (004 tasks and plan), the two approved tests above, `ai-log/swen.md`, this entry. | Depends on: T2.2 (Spec 004).

**T19.4 A repeated tool call is not run again**
- Bug (re-test after T19.1, reproduced): the per-query cache stopped a repeated call from running twice, but the repeat still used a round, and the model got the full result again with no note that it had already been run.
- Decision (Article V.1, plan D14): a repeat counts against `max_verifier_rounds`. V.1 says tools run at most that many times and the loop must stay bounded; a free repeat could be requested forever. This matches the malformed-call rule (a malformed attempt uses a round, T8.6). Unchanged in count, so the only behaviour change is that the repeat is not run and says so.
- Tests first (scripted stub generator, `FakeTools`, `run_agent`): a repeated call runs once and adds no commit records; the model's next message is a `<tool_result>` saying the call was already run in round N and to use the result from round N, with no "No commit history" line; a call with different arguments still runs; the audit entry has `cache_hit` true, `result_summary` "already run in round 0" and `repeat_of` 0; a repeat uses one round of the limit (`round_limit_hit`, the other call never runs).
- **Approved test change (needs reviewer sign-off, Article IX.3):** `test_harness_round_limit_t83.py` (T8.3) fed the same `git_log` call in every round, so the second round became a repeat and the limit was no longer tested. Each round now asks for a distinct call (`n` varies); the assertions are unchanged.
- **Evaluation:** this changes agent behaviour. The evaluation must be re-run before any result is reported (Article VII.5).
- ACs: AC-3.1, 3.6; Article I.2, V.1, V.4; plan D14. | Touches: `agent/harness.py`, `tests/online/test_repeated_tool_calls_t194.py`, `tests/online/test_harness_round_limit_t83.py` (approved test, sign-off above), `ai-log/swen.md`, this entry. | Depends on: T19.1, T8.2.

**T19.5 Vague questions get a request for a file or function**
- Gap (dev test, item 14): a question that names no file or function, and that the retrieved code does not answer, gets an unhelpful refusal. The model should say what it could not find and ask the developer to name a file or function (Article X.2).
- Decision: a new `[prompt] vague_question_hint = false`. With false, the system prompt is byte-for-byte today's prompt, with and without tools. With true, one numbered rule is appended after the existing rules. The audit log records the `prompt` flags (Article VII.3, VIII.4). Off by default, so the baseline is unchanged (Article VII.5).
- Limitation: the evidence gate (AC-1.5) refuses before the generator is called, so this rule reaches the model only for questions that pass the gate and are still not answered from the context. The gate's refusal text is unchanged.
- Tests first (`tests/online/test_vague_question_hint_t195.py`, stub embedder, re-ranker and generator): with the flag off (and by default) the system prompt equals a snapshot of today's prompt, with and without tools; with the flag on, the prompt is that snapshot plus one numbered rule holding one sentence that asks the developer to name a file or function, and nothing else changes; `[prompt] vague_question_hint` defaults to false, loads from a file, layers in both loaders, and rejects a non-boolean; `ask` sends the flagged prompt and writes `audit_log["prompt"]["vague_question_hint"]`.
- **Evaluation:** this changes the prompt. The evaluation must be re-run before any result is reported (Article VII.5).
- ACs: Spec 002 AC-7.1; Article I.3, V.4, VII.3, VIII.1, VIII.4, X.2; plan D14. | Touches: `agent/harness.py`, `config.py`, `__init__.py`, `tests/online/test_vague_question_hint_t195.py`, `ai-log/swen.md`, this entry. | Depends on: T19.4, T20.1.
- Note: the flag is not added to `codecompass.toml`. `tests/eval/test_eval_config_t52.py` requires the eval config to equal the project config except for the planned differences, so a new `[prompt]` table in the project file fails that test. The default is set in code (`PromptConfig`).

## S20: Tool-use prompt (dev test, 2 Nov 2026, problem 3; plan D14, tool check)

**T20.1 Tool-use prompt**
- Tests first (stub generator, then `ask` with stubs): with tools on, the system prompt has the tool rule first, before the citation rules; it says the code context has no commit history; it names when to call a tool (why/when/who questions → `git_log` or `git_blame`; code the context does not show → `search_again` or `open_file`; cut-off code → `open_file`); it says a tool reply holds the tool call and nothing else; the insufficient-evidence rule applies after using tools; all T14.3 tool examples are still present. With tools off the system prompt is unchanged from T14.3. `user_message(question, chunks, tools_enabled=True)` ends with `TOOL_CHECK` after the code context; with tools off (and by default) the message is unchanged; `run_agent` sends the tool check only with tools on; `ask` counts the tool check in the D4 prefix. Model test (`model`, local only): on the history fixture repo, "Why does authenticate retry?" makes at least one `git_log` or `git_blame` call.
- **Approved test changes (need reviewer sign-off, Article IX.3):** `test_harness_messages_t85.py` (D14 template) gets the new tools-on prompt. No other assertion changes.
- ACs: AC-3.1, 3.7, 3.8; Article I.2, V.1, V.5, VII.3; plan D3, D4, D13 item 10, D14, D17. | Touches: `agent/harness.py`, `__init__.py`, plan D14, the approved test above. | Depends on: T14.3, T8.5, T19.1.

## S21: Guardrails (`docs/guardrails-todo.md`)

**T21.1 `open_file` refuses files the indexer excludes**
- Gap (guardrails #10): `validate_path` only checks that the file exists at the indexed commit, so `open_file(".env")` returned a committed secrets file to the model, and its text became citable evidence. The offline ignore list (Article III.6) kept it out of the index, but not out of the tools.
- Rule: `open_file` refuses a path whose file name matches `files.exclude_patterns` or that has a directory in `files.exclude_dirs` (the same name and directory rules the indexer applies, read from the merged config, not hard-coded). The indexer's other skips (size, binary, non-code extension) do **not** apply, so a README stays readable. The refusal is an error result fed back to the model (D6). It says the file is excluded and contains none of the file's text. It applies with and without `lines`. `git_blame` and `git_log` are unchanged: they return commit metadata, not file text.
- Tests first (stub embedder, re-ranker and generator; `ask` on a small fixture repo with a committed `.env`, `keys/id_rsa`, `node_modules/lib/index.js`, `config/secrets.yaml`, `README.md` and `src/app.py`): a model request for `open_file` on `.env` (with lines), on `.env` (outline), on `keys/id_rsa` and on `node_modules/lib/index.js` each gets an error tool result naming the file as excluded; no message the model receives contains the secret text; the audit log records the call as an error; no chunk of the file is citable, so citing it gives outcome G; `open_file` on `src/app.py` and on `README.md` still returns their text; a pattern added to `files.exclude_patterns` in config (`secrets.yaml`) is refused too, and with the default config the same file is readable.
- **Approved tests:** none change.
- ACs: Article III.6, V.2, VI.1, X.4; plan D6, D18. | Touches: `agent/tools.py`, `agent/harness.py`, `__init__.py`, plan D6, `tests/online/test_open_file_excluded_t211.py`. | Depends on: T14.3, T19.1.

## S22: Docs as context (dev test problem 10; guardrails #8)

**T22.1 Code first, docs when asked, better or needed**
- Tests first (stub embedder and re-ranker, `ask` on fixture repo with Python code and README.md): flag off (default) preserves existing retrieval chunks and audit log; flag on with code passing gate and doc score below code + margin sends only code chunks; flag on with question mentioning documentation keywords ("README", "docs", ".md", etc.) sends docs with code and adds DOCS_NOTE before code context; flag on with doc score >= code score + margin sends docs with code; margin boundary checks (exact margin counts as better, just below does not); flag on with code failing gate but docs passing sends only docs; flag on with neither passing refuses without generator calls; cited doc chunks are verified (outcome F); DOCS_NOTE is absent when no doc chunk is sent; D4 token prefix counts DOCS_NOTE when docs are sent; asks_about_docs checks whole words and extensions without false positives; config defaults and validation for docs_fallback, doc_languages, and docs_margin; flag on with no doc files sends only code; flag on with only docs sends doc chunks and logs code_failed with best_code=None.
- Limitations: (1) the keyword index has no language field, so doc chunks are filtered after retrieval and can take some shortlist slots when docs are indexed; a separate doc index needs a schema change (future work). (2) search_again is unchanged. (3) docs_margin 0.2 is a starting value, to be chosen with the evaluation after the baseline (Article VII.5); the default stays off.
- **Approved tests:** none change.
- ACs: Spec 002 S22; Article I.1, I.2, IV.2, V.4, VI.4. | Touches: `config.py`, `agent/harness.py`, `__init__.py`, `tests/online/test_docs_fallback_t221.py`. | Depends on: T15.1, T20.1.

**T22.2 Label documentation sources**
- Tests first (unit tests on `mark_documentation` and `ask` with fixture repo and stub reranker/generator): verified doc source gets ` (documentation)` label appended to its Sources line and `DOCS_BANNER` prepended at the top; code source in same answer is not labelled; multiple doc sources are all labelled and banner appears once with sorted markers returned; no doc sources returns text unchanged and empty list; unverified doc source in outcome G answer retains `[UNVERIFIED]` prefix, gets doc label, and retains warning banner below `DOCS_BANNER`; commit entries are never labelled; through `ask()` with `docs_fallback=True`, citing README chunk adds banner, labels line, and logs `log["citation"]["documentation_sources"] = [marker]`; citing only code produces no banner/label and no new log key; with `docs_fallback=False`, answer and log are unchanged; body lines starting with markers above Sources section are not labelled.
- Note: `checker.py` unchanged, Article VI.3/VI.4 respected, labels only added when `docs_fallback` is on. Documentation opened with `open_file` (with chunk language 'text') is also detected and labelled via file extension matching `retrieval.doc_languages`.
- **Approved tests:** none change.
- ACs: Spec 002 S22; Article I.1, I.2, IV.2, V.4, VI.3, VI.4. | Touches: `citation/formatter.py`, `__init__.py`. | Depends on: T22.1, T9.4, T16.1.

---

## Completion checklist (spec "definition of done")

- [ ] Every P1 and P2 AC has an approved, passing test.
- [ ] `pytest -m "not model"` is green in CI with no network, no GPU, no `llama-server`.
- [ ] `model` tests pass locally on the `dev` profile machine.
- [ ] Citation checker correctly classifies F and G outcomes on fixture data.
- [ ] A citation to a non-retrieved file is flagged (required regression test, Article IX.5).
- [ ] The round limit terminates the loop (required regression test, Article IX.5).
- [ ] No skipped or xfail tests without a linked reason.
- [ ] All dependencies pinned; `mlx-lm` absent.
