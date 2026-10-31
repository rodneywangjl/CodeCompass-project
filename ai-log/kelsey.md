# AI Use Log: Kelsey

## 2026-10-07 · Online package skeleton, config loader, and models (T0.1)
- **Tool (model):** Antigravity (Gemini 3.8 Flash)
- **Files:** tests/online/test_config_t01.py, codecompass/online/__init__.py, codecompass/online/config.py, codecompass/online/models.py
- **Outcome:** Kept
### What I asked for
Implementation of Task T0.1 from Tasks 002: test-first implementation of the online package skeleton, typed config loader (retrieval parameters, generator profiles, tool settings, merged offline config), and core data models.
### How I checked it
Confirmed tests failed first with `ModuleNotFoundError: No module named 'codecompass.online'`. After implementation, verified that all 9 tests in `test_config_t01.py` passed, followed by running the full required suite (`pytest -m "not model"`), with all 143 tests passing (134 offline + 9 online) and zero regressions.
### What I kept or changed
Kept the complete dataclass models (`QueryResult`, `CitationResult`, `SourceEntry`, `ToolCall`, `ToolResult`), default retrieval parameters, generator profile resolver (`dev`/`prod`) with loud `ValueError` on unknown profiles, and the offline configuration merge logic.

## 2026-10-27 · Spec 002 block 3 overview
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** ai-log/kelsey.md
- **Outcome:** Kept
### What I asked for
Completed block 3 of the Spec 002 rollout on feat/llama-server-generator-agent-loop. This phase integrates the core Llama-server generator (T7) and the multi-round agent loop (T8) based on recent team design discussions. The code reflects our agreed-upon constraints for model profiles, HTTP client stability, round limits, and append-only message handling.
### How I checked it
All commits applied cleanly. Ran pytest -m "not model" --continue-on-collection-errors on Windows: 350 passed, including every test added in this block. (The known 13 failures and 30 errors are related to Windows Application Control blocking the tantivy DLL and a pre-existing path issue in test_config_merge, which are outside the scope of this block). Re-ran the full required suite (pytest -m "not model") in WSL (Ubuntu, Python 3.14) on the same branch: all 410 selected tests passed, including the tantivy and test_config_merge tests, confirming the Windows failures were environment-only.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T7.1 Model profile loading
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/generator/__init__.py, codecompass/online/generator/profiles.py, tests/online/test_profiles_t71.py
- **Outcome:** Kept
### What I asked for
T7.1: Asked for the implementation of predefined model profiles (dev for the 14B model on laptops, and prod for the 32B model). The system must default to dev unless the GENERATOR_PROFILE environment variable is set. It strictly requires the llama.cpp backend, runs on CPU by default, and fails loudly with a clear error on an unknown profile name rather than silently falling back.
### How I checked it
test_profiles_t71.py passed. Read the config.py change: it adds backend, server_args, seed and cache_prompt to ModelProfile and rejects any backend other than llama.cpp; it does not change path handling.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T7.2 llama-server HTTP client
- **Tool (model):** Claude Code (claude-opus-5-5).
- **Files:** codecompass/online/generator/http.py, codecompass/online/generator/llama.py, codecompass/online/generator/protocol.py, tests/support/fake_http.py, tests/online/test_llama_generator_t72.py
- **Outcome:** Kept
### What I asked for
T7.2: Asked for an HTTP client for llama-server. It POSTs directly to /v1/chat/completions (mirroring the OpenAI API format) and transmits the profile’s configuration (temperature, max tokens, stop tokens, and cache_prompt). Added strict error raising instead of infinite hanging if the server is down or timing out.
### How I checked it
test_llama_generator_t72.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T7.3 Health check and launch command
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/generator/server.py, tests/online/test_health_check_t73.py
- **Outcome:** Kept
### What I asked for
T7.3: Asked for pre-flight health check validations. The generator must ping /health (expecting a 200 OK) and check /props to guarantee the server's context window is sufficient for the profile and the correct model file is loaded, failing loudly if incorrect. It also cleanly constructs the launch command with -c <context window>, --host 127.0.0.1, and necessary profile arguments.
### How I checked it
test_health_check_t73.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T7.4 Localhost binding warning
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/generator/server.py, tests/online/test_localhost_t74.py
- **Outcome:** Kept
### What I asked for
T7.4: Asked to enforce privacy baselines. The server correctly defaults to 127.0.0.1. While pointing at another address is permitted for deployment flexibility, the system must log a clear warning when the server is not bound to localhost.
### How I checked it
test_localhost_t74.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · D15 generator-call count fix
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
Docs fix to plan decision D15 based on team discussion: corrected the math on the round-limit rule. The maximum number of model calls is N + 2 (not N + 1): this accounts for one call per tool round, one reply that still requests a tool, and the final forced answer call.
### How I checked it
Docs only; checked the commit touches only plan.md and tasks.md.
### What I kept or changed
Kept unchanged

## 2026-10-27 · T8.1 Single-round answer
- **Tool (model):** Claude Code (claude-opus-5-5), via Rodney's referHere branch; carried over with help from Claude (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/harness_support.py, tests/online/test_harness_single_round_t81.py
- **Outcome:** Kept
### What I asked for
T8.1: Asked for the baseline agent loop to immediately return the answer when the model answers in one round (zero tools called), generating a clean, single-call audit log.
### How I checked it
test_harness_single_round_t81.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T8.2 Multi-round tool loop
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_harness_tool_loop_t82.py
- **Outcome:** Kept
### What I asked for
T8.2: Asked for the multi-round execution loop. When the model requests a tool (like git blame), the harness executes it, wraps the result in <tool_result> tags as a user message, and calls the model again, accurately recording each round in the audit log.
### How I checked it
test_harness_tool_loop_t82.py passed.
### What I kept or changed
Kept unchanged

## 2026-10-27 · T8.3 Round limit enforcement
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_harness_round_limit_t83.py
- **Outcome:** Kept
### What I asked for
T8.3: Asked to translate D15 into code. The loop runs a maximum of max_verifier_rounds (default 3). If the model exceeds this, it is forced into a final answer-only call, capping executions at N + 2. Any leftover <tool> requests in that final answer are aggressively stripped before reaching the citation checker.
### How I checked it
test_harness_round_limit_t83.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T8.4 Tool error handling
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_harness_tool_errors_t84.py
- **Outcome:** Kept
### What I asked for
T8.4: Asked for improved loop resilience by catching bad tool calls (wrong arguments, unauthorized tools, timeouts) and feeding the error back to the model as a message, allowing it another round to recover rather than crashing the harness.
### How I checked it
test_harness_tool_errors_t84.py passed.
### What I kept or changed
Kept unchanged.

## 2026-10-27 · T8.5 Append-only message building
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_harness_messages_t85.py
- **Outcome:** Kept
### What I asked for
T8.5: Asked to enforce strict conversational rules. Messages are strictly append-only (never edited or reordered) to heavily leverage llama-server's caching. Enforced the allowed roles (system, user, assistant), placed retrieved code chunks in the user message, and mapped empty git results to explicit string responses ("No commit history found for ") instead of blank messages.
### How I checked it
test_harness_messages_t85.py passed.
### What I kept or changed
Kept unchanged

## 2026-10-29 · T8.6 Malformed tool-call retry (v2 E6)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tool_parser.py, codecompass/online/agent/harness.py, tests/online/test_harness_malformed_t86.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
Compared our code against the team's v2 architecture and found E6 (tool-call validator) was only half built: bad arguments were sent back to the model, but a malformed `<tool>` block was silently dropped and the broken reply became the final answer (e.g. just "Let me check the history."). Asked for malformed calls to be sent back with the correct format so the model can retry, and for the spec, plan and tasks to be updated, since they said malformed calls are final answers.
### How I checked it
Approved the tests first and saw them fail for the right reason (10 failed, 1 passed; the harness returned "Let me check the history." as the answer). After the code: all 12 tests in test_harness_malformed_t86.py passed. Full required suite (`pytest -m "not model"`) on Windows: 459 passed, 1 failed in test_config_merge.py, the known Windows path issue unrelated to this change. Re-ran the full suite in WSL (Ubuntu, Python 3.14): 460 passed, including test_config_merge.py, confirming the Windows failure was environment-only. Asked whether the fix depends on the reply's wording: it does not, it detects the `<tool>` tag.
### What I kept or changed
Kept. A malformed attempt uses one of the 3 rounds; I agreed because it also prevents the model from looping forever, and keeps the guarantee of at most 5 model calls per question (each 14B call takes about a minute). Kept replies that only say "let me check" with no `<tool>` tag as the final answer, as a known limitation with a test; I agreed because matching words like "let me" would also catch real answers such as "Let me explain...". Added a separate `malformed_blocks()` helper instead of changing `parse_tool_calls()`, so the approved T6.1 tests stay unchanged and both use the same parser. Considered property-based testing (Hypothesis) and agreed to add it later, once open_file and search_again exist and there are more paths to test.

## 2026-10-30 · Constitution amendment 1.4.0 (tools and 14B evaluation)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, AGENTS.md
- **Outcome:** Kept
### What I asked for
Asked for help amending the constitution to match our v2 architecture (tools box E4): Article V.2 allowed only git blame/log, but the v2 plan has `search_again` and `open_file`, and Arne's feedback expects the agent to beat RAG on code-tracing questions, which git history alone cannot do. Also asked to update Article VIII.5 after the team agreed to evaluate on the 14B instead of the 32B. Asked the team in our group chat first, since this changes team rules; they agreed.
### How I checked it
Because AGENTS.md says AI tools must not modify docs/constitution.md, Claude drafted each change as find/replace text and I applied all 11 edits myself, one at a time, asking why each was needed. Claude found two extra places the new tools would otherwise break: the cache key in V.3 (search_again has a query, not a path) and the citation check in VI.4 (honest citations from open_file would be flagged). Checked the tables in Markdown preview, and reviewed `git diff` to confirm only docs/constitution.md and AGENTS.md changed.
### What I kept or changed
Kept all changes: V.1 (round limit covers all tools), V.2 (four tools, query length bounded), V.3 (cache key), V rationale (v1.4.0 note), VI.4 (citations checked against all code in context), VIII.5 (one 14B profile for the whole evaluation; 32B stays the production model), Appendix A rows 1 and 8, Appendix B, AGENTS.md line 85. Version bumped 1.3.0 to 1.4.0 (MINOR). Asked whether evaluation or production comes first; kept "14B for development and evaluation, 32B for production" since production is future work for this project.

## 2026-10-30 · Design of open_file and search_again (plan D18, tasks S14)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
After constitution 1.4.0 was merged, asked for a design for the two new v2 tools before writing any code, with the options and pros and cons of each decision, and how each compares with our v2 plan (the proposal itself does not mention these tools).
### How I checked it
Asked how open_file works when the model only gets part of a file and whether it can really read the file: the harness reads the file from git at the indexed commit and returns only the requested lines; a longer range needs a second call, and each call uses a round. Asked how the model knows which lines to ask for; it often does not, so we added an outline mode. Asked what search_again does and compared its options. Read the D18 and S14 text before committing. Docs only, no code changed.
### What I kept or changed
Kept: (1) open_file takes a line range limited to the existing 768-token tool cap, not the whole file as in the v2 plan, because a file like Flask's app.py is about twice our 8k context; open_file(path) with no lines returns an outline of functions with line numbers so the model does not guess. (2) search_again returns only chunks not already in context, because repeating a chunk would waste one of the 3 rounds. (3) Code shown by tools is passed to the citation checker, as Article VI.4 now requires, otherwise honest citations would be flagged. (4) Work split into three tests-first tasks T14.1-T14.3.
