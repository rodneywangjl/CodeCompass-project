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

## 2026-10-30 · T14.1 open_file tool
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_open_file_t141.py
- **Outcome:** Kept
### What I asked for
T14.1 from the design (plan D18): an `open_file(path, lines)` tool that reads code at the indexed commit and returns it with the same header as retrieved chunks, cut to whole lines when it does not fit the 768-token tool limit, and `open_file(path)` without lines returning an outline of functions with line numbers.
### How I checked it
Reviewed the 14 tests first and ran them on Windows: all failed because `open_file` did not exist yet. After the code: 14 passed. Full required suite in WSL (Ubuntu, Python 3.14): 474 passed. Did not push the red tests, so CI stayed green. Asked whether passing means the feature is done: it does not; the agent cannot call the tool until T14.3 adds it to the allowed tools, the prompt and the citation checker.
### What I kept or changed
Kept. The tool reads the file from git, not the working folder, so it matches the indexed chunks; it grows the range one line at a time and stops at the first line that does not fit, so the citable range is exactly what was shown. `ToolOutput` gained a `chunks` field, so code the model was shown can reach the citation checker (Article VI.4); `cap_output` drops chunks if it ever has to cut a result, because cut code is no longer citable. The file is decoded as UTF-8 explicitly, because the Windows default is not UTF-8. The outline takes a `symbols` function so it can be tested without an index; it is connected to the index in T14.3.

## 2026-10-31 · T14.2 search_again tool
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_search_again_t142.py
- **Outcome:** Kept
### What I asked for
T14.2 from the design (plan D18): a `search_again(query)` tool that lets the agent write its own search query when the first search missed the right code. It runs the query through our existing hybrid retrieval and re-ranker, skips chunks the model already has, and returns as many new chunks as fit the 768-token tool limit, in the same format as retrieved chunks.
### How I checked it
Reviewed the 11 tests first. They build a small real index of the fixture repo with the stub embedder and re-ranker, so they test our actual search engine. Ran them in WSL because the index uses tantivy, which Windows blocks: all 11 failed because `search_again` did not exist yet. After the code: 25 passed (with the 14 open_file tests). Full required suite in WSL (Ubuntu, Python 3.14): 485 passed. Kept the red tests local and pushed only once green.
### What I kept or changed
Kept. It reuses `retrieve` and `rerank_chunks` instead of a new search, as our v2 plan says ("run it through the existing embedder + vector store + BM25 index"). Chunks already in context are skipped before re-ranking, so no round is wasted on code the model already has. If everything is already known it says "Nothing new found" (not an error). If even the best new chunk is too big, it tells the model which `open_file` call reads part of it, so the two tools work together. The query must be a non-empty string of at most 200 characters (constitution V.2, "query length bounded"). The agent cannot call it yet; that is T14.3.

## 2026-10-31 · T14.3 Wire open_file and search_again into the agent
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, codecompass/online/agent/harness.py, codecompass/online/__init__.py, codecompass/online/config.py, codecompass/offline/stores/vector.py, codecompass/offline/__init__.py, tests/online/test_tool_wiring_t143.py, tests/online/test_tool_allowlist_t54.py, tests/online/test_tool_settings_t05.py, tests/online/test_harness_messages_t85.py, docs/specs/002-online-retrieval/tasks.md, docs/specs/002-online-retrieval/spec.md
- **Outcome:** Kept
### What I asked for
T14.3: make the two tools usable by the agent. Allow them in the config and the dispatcher, describe them in the system prompt and the malformed-call hint, take the open_file outline from the index, give search_again the index, re-ranker and the chunks already shown, and pass the code shown by tools to the citation checker (Article VI.4). Update Spec 002's tool list.
### How I checked it
Claude found that three approved tests check the old two-tool rules (test_tool_allowlist_t54, test_tool_settings_t05, and the D14 prompt in test_harness_messages_t85). I agreed to update only the outdated lines and record them in tasks.md as approved test changes needing reviewer sign-off, as T9.7 did, because Constitution 1.4.0 made them out of date. Ran the tests in WSL first: 16 failed for the right reasons (missing ToolContext, old prompt, two tools instead of four, and citing open_file code gave G instead of F); the "same citation without the tool is G" test already passed. After the code: 43 passed, full suite 500 passed.
### What I kept or changed
Kept. The key proof is a pair of end-to-end tests: citing code the model read with open_file is verified (F), and the same citation without reading it is flagged (G), so the tools add evidence without letting the model cite code it never saw. Every chunk a tool shows is added to a "seen" list, so search_again never repeats code. The outline uses a small read-only `symbols_for_path` in the offline vector store (outside my area, noted in the PR). Each tool has a one-line description of when to use it in the prompt, which should help a small model like the 14B.

## 2026-11-03 · T17.1 Reject questions with no words (report problem 11)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/__init__.py, tests/online/test_empty_question.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix problem 11 from Rodney's 2 Nov test report: an empty or blank question (D9, D10) ran the whole pipeline for about 2 minutes and the model answered about lines containing only `}`. I asked Claude to explain the problem, and write the tests first.
### How I checked it
I asked about questions that are only spaces, “.”, “?” or symbols like !@$()^&*(), which are not real questions, and whether we should treat them as an error or give a friendly message. I agreed with Claude to make it an error, so that no audit log is written because nothing was processed. I also checked whether each test input was needed, and we removed the ones that caught the same mistake. I ran the red tests in WSL: 35 failed, all because the pipeline ran when it should not have, and 3 passed (the real-question guards). After Claude wrote the code, all 38 tests passed and the full suite passed (1099). I saw a warning in the output and asked Claude to explain it. It comes from the chromadb library (a Python 3.16 deprecation), not from our code.

### What I kept or changed
Changed the first proposal in three places. (1) I asked about "." and other symbols: checking only for empty or whitespace text would let them through, so the rule became "the question must contain at least one letter or digit" (`isalnum`, which also accepts Chinese). (2) We kept an error because the TUI already skips blank lines silently, and the CLI shows it as one friendly line; a normal answer would be counted as a real answer in evaluation. Because a user may type "?" when confused by an answer, the message also says that each question is answered on its own. (3) I asked that every test input have a reason: we dropped two inputs that caught the same mistake as another ("..." and "?!"), did not add four more that Claude suggested (a full-width "？", two invisible space characters, and a TUI test that an existing test already covers), kept "\n\t" because it catches a check that forgets newlines and tabs, and wrote the reason for each input as a comment in the test file. No audit log is written, because nothing was processed. Added AC-9.3 and an edge case to Spec 002.

## 2026-11-03 · T18.1 Write the audit log when a question fails (report problem 7)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/__init__.py, tests/online/test_audit_log_on_failure_t181.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
Fix problem 7 from Rodney's 2 Nov test report: when a question failed (A2 first try timed out, B4 was stopped), `ask()` wrote no audit log, so nobody could see which stage failed. Article V.4 and AC-7.1 say every query must be logged. Tests first, without touching Gavin's files.
### How I checked it
I asked what logging Ctrl-C means: everything done before the interrupt is recorded, so the log shows how far the question got and where it stopped. I also asked what happens if writing the log itself fails, and agreed that the original error should still be shown. I researched pre-query logging (the trussed.ai RAG audit checklist and an AI overview) to decide whether rejected questions should be logged; we kept “no log” for v1 because nothing is processed, and noted logging rejected input with user identity as future work for a shared deployment. I ran the red tests in WSL: 5 failed (no log was written) and 4 passed (the guards). After Claude wrote the code, all 9 passed and the full suite passed (1108).
### What I kept or changed
Kept. The work after the log is created now sits in a `try`; on any error, including Ctrl-C, the log gets `error` (type and message) and the total time, is written, and the same error is raised again, so users see the same message as before. If writing the log also fails, the original error still wins. Errors before any work starts (a bad setting, an empty question) write no log, because no query was processed. A process killed outright still cannot log, which the spec now says. Added AC-7.6 and an edge case to Spec 002, and reworded the T17.1 note in tasks.md to "agreed in the team".

## 2026-11-04 · T18.2 Log a failure while counting tokens
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/__init__.py, tests/online/test_audit_log_token_count_t182.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Kept
### What I asked for
After T18.1, I tested it for real with llama-server not answering. The CLI showed `llama-server timed out after 120s: .../tokenize` but no log was written. I asked Claude why, and to fix it with a test first.
### How I checked it
I found this gap myself by testing T18.1 for real: with llama-server not answering, ask failed on token counting and wrote no log, because that step had wrongly been treated as a settings check and ran before the try. I ran the red test first: 1 failed (“expected one audit log, found 0”) and 1 passed. After the fix, both tests passed and the full suite passed (1122). Then I repeated the real run with llama-server off: a new log was written (20261104T034137…) with GeneratorError: llama-server timed out after 120s and every stage at 0.0 with a total of 120.25 s, which shows it failed before indexing. I also found that the 120 s wait happens because WSL mirrored networking drops the connection instead of refusing it (curl -m 5 timed out).
### What I kept or changed
Kept. The first call to llama-server is `count_tokens` inside `check_round_reserve`, which ran before the T18.1 `try`. Claude had treated it as a settings check; it now runs inside the `try`, so the error is logged and raised again. A round reserve that is too big for the context is now logged too, which is fine because the log already exists. Updated AC-7.6 and added T18.2 under S18.

## 2026-11-04 · Spec 003 core questions: localisation, runtime-behaviour and design-rationale 1-4
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** eval/questions/flask-core-kelsey.jsonl
- **Outcome:** Changed
### What I asked for
My 20 of the 40 core evaluation questions on Flask at commit 85c5d93: 8 localisation, 8 runtime-behaviour and design-rationale 1-4. I wrote the questions. I asked Claude to check them against the Flask code and history, find the evidence for each (file, lines, commit) and explain it in plain words, check my answers, and convert the set into the same JSONL format as Nicole's file.
### How I checked it
I compared my questions against the 48 SWE-QA Flask questions and replaced the one that duplicated question 46. I rewrote my answers after each review until they matched the evidence, and checked each one against the code notes (file, lines and what the code does). When Claude said an online answer wasn't in the repository, I checked why (for example the `download_name` commit gives no reason) and rewrote it to say only what the repository shows.
### What I kept or changed
Changed my first drafts. Claude's check found that some questions were about CodeCompass instead of Flask, some had a wrong premise (`g['key']` does not exist, `app.py` has no `@setupmethod`, `request.is_json` is in Werkzeug, not Flask), and one duplicated SWE-QA question 46 (session lifecycle), so I replaced or dropped them. I removed wording that told the system where to look ("Look at ...", "Find the commit ..."). I wrote the reference answers myself, partly using online sources to understand the topics; Claude then found four that said things the repository does not (for example a reason for the `download_name` rename that no commit gives), and made five small factual corrections at my request. Kept all questions marked `ai_assisted: true`. Tags: 10 code-tracing, 10 simple.

## 2026-11-08 · T22.1 Docs as context fallback
- **Tool (model):** Antigravity (Gemini 3.8 Flash); reviewed by Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/agent/harness.py, codecompass/online/__init__.py, tests/online/test_docs_fallback_t221.py, docs/specs/002-online-retrieval/tasks.md, docs/specs/002-online-retrieval/spec.md
- **Outcome:** Changed
### What I asked for
Implementation of Task T22.1 (Docs as context): add docs_fallback, doc_languages, and docs_margin
to RetrievalConfig with validation and TOML list-to-tuple parsing; update _retrieve_and_answer to
prioritize code chunks and add doc chunks when asked, when docs score higher by docs_margin, or when
code fails the evidence gate; record docs_fallback in the audit log when enabled; add
asks_about_docs whole-word and extension checker; add DOCS_NOTE to harness and pass docs flag
through
user_message and run_agent, including D4 token prefix counting.
### How I checked it
Agreed the design with Rodney (code is the source of truth; docs added when asked
or clearly better).
Reviewed the red tests first and asked for two edge cases (repos with no docs, and repos with docs
only). Had the code reviewed and fixed the TOML string parsing bug, the duplicated tail in
`_retrieve_and_answer`, required docs on "asked" to pass the evidence gate, and sorted imports. Ran
the test suite in WSL: all 20 task tests passed, and the full required suite passed with 1210 passed
and 0 failed. Ran a real verification on my laptop against Flask with the real embedder and
re-ranker (dummy model): the code question sent code only; the README question triggered "asked" and
sent README.md; the deployment question sent code only because 0.985 - 0.808 = 0.177 < margin 0.2,
showing the 0.2 margin is too strict and should be tuned during evaluation.
### What I kept or changed
Changed after Claude Code’s review:
1. Fixed TOML string parsing in `_build_online_config` so `doc_languages` is only converted to a
   tuple when it is a `list`. A TOML string (e.g. `doc_languages = "md"`) now correctly raises
   `ValueError` naming `retrieval.doc_languages` instead of converting into `("m", "d")`.
2. Refactored `_retrieve_and_answer` so flag-off and flag-on paths only select the chunk list and
   the `docs` flag, sharing one tail for token prefix calculation, `fit_chunks`, retrieved chunk
   logging, tool runner construction, and agent invocation. Restored Plan D7 and Article III.6
   comments.
3. Updated the "asked" branch to require `best_doc >= min_top_score`, preventing irrelevant
   documentation chunks from entering context just because a question mentions a doc keyword.
4. Alphabetized `import re` in `codecompass/online/__init__.py`.
5. Added tests covering the TOML string configuration validation and the "asked" doc score gate
   check (bringing the test suite to 20 tests).
