# Tasks 002: Online Query Pipeline

**Implements:** Plan 002 / Spec 002 | **Constitution:** v1.2.0

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

**T0.2 Extended fixture repo**
- Goal: extend the Sprint 1 fixture-repo builder with additional commits that have meaningful commit messages (e.g. "fix auth timeout by adding retry logic") so verifier-tool tests can assert on `git log` / `git blame` output.
- Tests first: the builder creates commits with known messages, authors, and dates; `git log` on a fixture file returns the expected entries; `git blame` on a fixture file returns the expected commit info.
- ACs: enables US3 testing. | Touches: `tests/support/fixture_repo.py`. | Depends on: T0.1.

**T0.3 Stub generator**
- Goal: a deterministic `StubGenerator` that returns canned responses (configurable per test). Supports: a plain answer with valid citations, an answer with a tool-call request, an answer with invalid citations, an answer with no `Sources` section, a malformed tool-call response.
- Tests first: stub returns the configured response; calling `generate()` with messages returns the expected text; multiple calls cycle through configured responses (for multi-round tests).
- ACs: enables Article IX.7. | Touches: `tests/support/stub_generator.py`. | Depends on: T0.1.

**T0.4 Stub re-ranker**
- Goal: a deterministic `StubReranker` that scores chunks by a fixed function (e.g. text length descending) so re-ranking tests are model-free.
- Tests first: stub returns scores in deterministic order; same input gives the same output; scores are floats.
- ACs: enables Article IX.7. | Touches: `tests/support/stub_reranker.py`. | Depends on: T0.1.

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
- Tests first: the query is embedded with the same embedder instance used for the index; the result is a single vector of the correct dimension; a mismatched embedder identity between the query embedder and the index is refused by `open_index` (already tested in Sprint 1, but confirm the online path triggers it).
- ACs: AC-2.2, FR-1. | Touches: `retrieval/embedder.py`. | Depends on: T2.1.

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
- Tests first: each chunk is formatted as a block with file path, line range, language, and indexed commit; the generator sees plain text with metadata, never raw vectors or chunk ids; the format matches the plan's D3 template.
- ACs: AC-1.4, FR-5. | Touches: `context.py`. | Depends on: T0.1.

**T4.2 Context budgeting**
- Tests first: chunks are added in re-ranker score order until the token budget is exceeded; the remaining chunks are dropped; the token count uses the embedder's tokenizer; `final_k` is capped by the budget (fewer chunks if the budget is tight); a very small budget results in zero chunks (handled gracefully); `generation_reserve` is subtracted from the context window.
- ACs: AC-2.6, plan D4. | Touches: `context.py`. | Depends on: T4.1, T3.2.

## S5: Verifier tools

**T5.1 Tool argument validation**
- Tests first: a path with `..` is rejected; a path starting with `/` is rejected; a path containing shell metacharacters (`; | & $ \` \\ ( )`) is rejected; a valid repo-relative path passes; a line range `42-58` passes; a reversed range `58-42` is rejected; a non-numeric range is rejected; a path not in the repo is rejected.
- ACs: AC-3.3, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T0.2.

**T5.2 git_blame executor**
- Tests first: `git_blame` on a fixture file returns blame output containing the expected commit hash and author; with a line range, only those lines are blamed; the command runs with `shell=False`; a timeout produces an error message, not a crash; the executor returns text output.
- ACs: AC-3.2, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T5.1.

**T5.3 git_log executor**
- Tests first: `git_log` on a fixture file returns log entries with commit hash, author, date, subject; the output is limited to the configured `n` commits; the command runs with `shell=False`; a timeout produces an error message; an empty log (file with no history) returns an empty result.
- ACs: AC-3.2, AC-3.4. | Touches: `agent/tools.py`. | Depends on: T5.1.

**T5.4 Tool allow list**
- Tests first: requesting `git_blame` or `git_log` succeeds; requesting any other tool name (e.g. `git_diff`, `cat`, `ls`) is rejected with a clear error message appended to context.
- ACs: AC-3.2. | Touches: `agent/tools.py`. | Depends on: T5.2, T5.3.

**T5.5 Tool-result caching**
- Tests first: calling the same tool with the same args twice returns the cached result; the cache records `cache_hit=True` on the second call; different args produce different cache keys; the cache is a per-call dictionary (not shared across `ask` calls).
- ACs: AC-3.5, plan D8. | Touches: `agent/cache.py`. | Depends on: T5.2.

## S6: Tool-call parser

**T6.1 Parse tool calls from model output**
- Tests first: `<tool>git_blame(path="src/auth.py", lines="42-58")</tool>` is parsed into `ToolCall(tool="git_blame", args={"path": "src/auth.py", "lines": "42-58"})`; `<tool>git_log(path="src/auth.py", n=10)</tool>` is parsed correctly; a response with no `<tool>` tag is classified as a final answer; a response with malformed `<tool>` content (e.g. missing closing tag, bad syntax) is treated as a final answer, not a crash; multiple tool calls in one response: only the first is executed (Article V.1 allows one tool per round).
- ACs: AC-3.8, FR-13. | Touches: `agent/tool_parser.py`. | Depends on: T0.1.

## S7: Generator

**T7.1 Model profile loading**
- Tests first: loading `dev` profile returns the 14B config; loading `prod` returns the 32B config; an unknown profile name raises a loud error; the default profile is `dev`; `GENERATOR_PROFILE` env var overrides the default; each profile has all required fields (model_id, context_window, temperature, max_tokens, stop_tokens).
- ACs: AC-5.1, AC-5.2, AC-5.9, FR-17. | Touches: `generator/profiles.py`. | Depends on: T0.1.

**T7.2 LlamaServerGenerator**
- Tests first (mocked HTTP): `generate(messages)` sends a POST to `/v1/chat/completions` with the correct chat format; the response is parsed and the assistant content returned; stop tokens from the profile are included in the request; temperature and max_tokens from the profile are sent; a connection error raises a clear error, not a hang; a timeout raises a clear error.
- ACs: AC-5.3, AC-5.4, AC-5.6, FR-12. | Touches: `generator/llama.py`. | Depends on: T7.1.

**T7.3 Health check**
- Tests first (mocked HTTP): `health_check()` pings `/health` and returns True on 200; returns False on connection error; the generator refuses to generate if the health check fails.
- ACs: AC-5.10. | Touches: `generator/server.py`. | Depends on: T7.2.

**T7.4 Localhost binding**
- Tests first: the default server URL is `http://127.0.0.1:<port>`; a config with a non-localhost URL is accepted (for flexibility) but logged as a warning.
- ACs: AC-5.5. | Touches: `generator/llama.py`. | Depends on: T7.2.

## S8: Agent harness

**T8.1 Single-round answer (no tools)**
- Tests first (stub generator returns an answer directly): the harness calls `generate` once; the response is returned as the answer; round count is 0; no tool calls in the audit log.
- ACs: AC-3.1 (no-tool path). | Touches: `agent/harness.py`. | Depends on: T6.1, T7.2.

**T8.2 Multi-round tool loop**
- Tests first (stub generator returns a tool call on round 0, then an answer on round 1): the harness executes the tool, appends the result to messages, calls generate again; the audit log shows round 0 with a tool call and round 1 with the answer; tool results are appended as tool messages in context.
- ACs: AC-3.1, AC-3.5, AC-3.6. | Touches: `agent/harness.py`. | Depends on: T8.1, T5.4, T5.5.

**T8.3 Round limit enforcement**
- Tests first (stub generator always requests tools): after 3 tool rounds, the harness stops and treats the last response as the final answer; the audit log records all 3 rounds; the system proceeds to the citation checker with whatever answer text it has.
- ACs: AC-3.1, FR-6. | Touches: `agent/harness.py`. | Depends on: T8.2.

**T8.4 Tool error handling**
- Tests first: a rejected tool call (bad args, disallowed tool) produces an error message in context; the model sees the error and gets another round; a tool timeout produces an error message; the harness does not crash on any tool failure.
- ACs: AC-3.3, AC-3.4. | Touches: `agent/harness.py`. | Depends on: T8.2.

**T8.5 Message building**
- Tests first: the system prompt is the first message; context chunks are in the user message; tool results are appended as separate messages; the conversation history grows with each round; the system prompt matches the plan's D14 template.
- ACs: AC-1.4, plan D14. | Touches: `agent/harness.py`. | Depends on: T4.1.

## S9: Citation checker

**T9.1 Source entry parser**
- Tests first: `[1] src/auth/client.py, lines 42-58 (indexed at a1b2c3d)` is parsed as a code source with path, start_line=42, end_line=58, commit_prefix=`a1b2c3d`; `[2] Commit a1b2c3d, "handle flaky upstream", Alice, 2024-03-14` is parsed as a commit source; a malformed entry is flagged as unparseable; an answer with no `Sources` section returns an empty source list.
- ACs: AC-4.5. | Touches: `citation/parser.py`. | Depends on: T0.1.

**T9.2 Citation checker: outcome F (all valid)**
- Tests first: an answer where every code source matches a retrieved chunk (path matches, line range overlaps, commit prefix matches) and every commit source matches a tool result → outcome F; the answer is shown normally.
- ACs: AC-4.1, AC-4.3. | Touches: `citation/checker.py`. | Depends on: T9.1.

**T9.3 Citation checker: outcome G (invalid citation)**
- Tests first: a code source citing a file not in retrieved context → outcome G; a code source with a wrong line range → outcome G; a commit source citing a hash not in any tool result → outcome G; an inline marker `[N]` with no corresponding `Sources` entry → outcome G; a `Sources` entry with no matching inline marker → outcome G; no `Sources` section at all → outcome G.
- ACs: AC-4.1, AC-4.4, AC-4.5. | Touches: `citation/checker.py`. | Depends on: T9.2.

**T9.4 Flagged answer formatting**
- Tests first: a flagged answer has a banner: `⚠ WARNING: Some citations in this answer could not be verified...`; each unverified source is prefixed with `[UNVERIFIED]`; a flagged answer is never rendered identically to a cited answer (banner is always present for G).
- ACs: AC-4.4, FR-10. | Touches: `citation/formatter.py`. | Depends on: T9.3.

**T9.5 Harness-copied commit metadata**
- Tests first: when the answer contains a commit source `[N] Commit hash, ...`, the harness replaces the model's subject, author, and date with values from the matching `git log` tool result; if the hash is not in any tool result, the source is marked unverified; the replacement is exact (no model-generated commit details survive).
- ACs: AC-4.6, FR-16. | Touches: `citation/checker.py`. | Depends on: T9.3, T5.3.

**T9.6 Citation checker is non-bypassable**
- Tests first: the `ask` function always runs the citation checker; there is no config flag to skip it; calling `ask` with a stub generator that returns invalid citations always produces a G outcome.
- ACs: AC-4.2. | Touches: `citation/checker.py`, integration test. | Depends on: T9.3.

## S10: Index freshness

**T10.1 ensure_current integration**
- Tests first: `ask` calls `ensure_current` before retrieval; if `ensure_current` returns `ok=True`, retrieval proceeds normally; if it returns `ok=False` with `status="failed"`, the stale flag is set and retrieval proceeds from the existing index.
- ACs: AC-6.1, AC-6.2. | Touches: `__init__.py`. | Depends on: T8.1, T9.2.

**T10.2 Stale-index fallback**
- Tests first: when `ensure_current` fails, the answer includes a stale-index warning: `⚠ WARNING: The index may be out of date...`; the `QueryResult.stale_index` is True; the `QueryResult.stale_message` contains the failure reason; the answer is still produced (not an error).
- ACs: AC-6.3, FR-14. | Touches: `__init__.py`. | Depends on: T10.1.

**T10.3 Empty index**
- Tests first: when the index is empty (no chunks), `ask` returns an answer saying no evidence is available; no retrieval or generation is attempted; the answer is not flagged as stale (it's just empty).
- ACs: AC-6.3 (edge case). | Touches: `__init__.py`. | Depends on: T10.1.

## S11: Audit logging

**T11.1 Per-query audit log**
- Tests first: every `ask` call produces an audit log dict containing: question text, active profile name, model id, list of retrieved chunks with RRF and reranker scores, list of tool calls with round number, tool name, args, cache hit/miss, citation outcome (F or G), and per-stage timings (retrieval, reranking, generation, tool execution, citation check).
- ACs: AC-7.1. | Touches: `logging.py`. | Depends on: T8.2, T9.2.

**T11.2 Audit log persistence**
- Tests first: the audit log is written to a JSON file under the configured `query_log_dir`; the file name includes a timestamp; the file is valid JSON; the stale-index warning, if triggered, is recorded.
- ACs: AC-7.2, AC-7.3. | Touches: `logging.py`. | Depends on: T11.1.

**T11.3 Profile and model in log**
- Tests first: the audit log records the active profile name and resolved model id; the profile is recorded on every query log.
- ACs: AC-5.8, AC-7.1. | Touches: `logging.py`. | Depends on: T11.1.

## S12: Public API and CLI

**T12.1 `ask` function**
- Tests first (stub generator, stub reranker, stub embedder): `ask(repo, question, config=config, profile="dev")` returns a `QueryResult` with answer, sources, citation outcome, stale flag, and audit log; the function does not print to stdout; the result contains all fields from the spec.
- ACs: AC-9.1, AC-9.2. | Touches: `__init__.py`. | Depends on: T10.2, T11.1.

**T12.2 Full pipeline integration test**
- Tests first (stub generator, stub reranker, stub embedder, real stores on fixture repo): an `ask` call goes through: ensure_current → open_index → embed query → vector search → keyword search → RRF → rerank → context assembly → generate → tool loop → citation check → result. Assert the result has the expected structure and the audit log has all stages.
- ACs: all P1 and P2 ACs (integration). | Touches: integration test only. | Depends on: T12.1.

**T12.3 CLI entry point**
- Tests first: `python -m codecompass.online.cli ask <repo> "<question>"` runs and prints the answer; `--profile prod` selects the prod profile; `--verbose` prints retrieval details; flagged answers display the banner; stale-index warnings are displayed before the answer; exit code 0 on success.
- ACs: AC-8.1, AC-8.2, AC-8.3, AC-8.4. | Touches: `cli.py`. | Depends on: T12.1.

## S13: Real model tests (local only, `model` marker)

**T13.1 Real cross-encoder re-ranker**
- Tests first (`model`): `BgeReranker` loads `BAAI/bge-reranker-v2-m3`; re-ranking a question against a relevant chunk and an irrelevant chunk gives the relevant chunk a higher score; batch scoring produces deterministic results.
- ACs: AC-2.7. | Touches: `retrieval/reranker.py`. | Depends on: T3.2.

**T13.2 Real generator smoke test**
- Tests first (`model`): `LlamaServerGenerator` connects to a running `llama-server`; a simple question about the fixture repo produces an answer with a `Sources` section; the citation checker runs and classifies the outcome.
- ACs: AC-5.1–5.11, end-to-end. | Touches: tests only. | Depends on: T12.2.

**T13.3 End-to-end smoke test**
- Tests first (`model`): `ask` on the fixture repo with the real generator and real re-ranker produces a grounded answer; the audit log is complete; the citation checker outcome is recorded; run with both `dev` and `prod` profiles if both are available.
- ACs: whole spec. | Touches: tests only. | Depends on: T13.1, T13.2.

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
