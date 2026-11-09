# AI Use Log: Gavin Tay

## 2026-10-28 · Real re-ranker, model smoke tests and online pipeline README (T13.1–T13.3, T8.5)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/retrieval/reranker.py, codecompass/online/agent/harness.py, docs/specs/002-online-retrieval/plan.md, tests/online/test_bge_reranker_t131.py, tests/online/model_support.py, tests/online/test_real_generator_t132.py, tests/online/test_end_to_end_t133.py, tests/online/test_harness_messages_t85.py, README.md
- **Outcome:** Kept
### What I asked for
Tests-first implementation of four Spec 002 tasks, plus the online README. Produced with Claude Code (claude-opus-5-5):
- T13.1: `BgeReranker` in `retrieval/reranker.py` wraps the `BAAI/bge-reranker-v2-m3` cross-encoder (sentence-transformers). It loads lazily on first use, on the configured device, at the revision pinned in the new `RerankerConfig.revision` (`953dc6f6`, Article VIII.1, VII.6). A required test checks the pin is a config field and the loader passes model, revision and device; a `model` test checks a relevant chunk outscores an irrelevant one.
- T13.2, T13.3: `model`-marked smoke tests for the real generator and for `ask` end to end on the fixture repo. Shared setup in `tests/online/model_support.py` skips them when no `llama-server` is running, so CI is unaffected.
- T8.5: rule 2 of the D14 system prompt now shows a literal `Sources` block and says no bullets or numbers. In T13.2 the 14B wrote `Sources` as a numbered list, which the checker rejects (Article VI.4). Plan D14, the T8.5 test and `harness.py` change together.
- README: describes both pipelines, adds "6. Ask a question" (CLI and Python use, what F, G and uncited answers mean, where audit logs go), and marks Sprint 2 done, with pinning the `prod` 32B GGUF still open.

### How I checked it
I checked what were the changes and the test cases passed.
### What I kept or changed
Kept all 7 commits unchanged, with tests before code. The T8.5 commit changes an approved test, so the PR asks for reviewer sign-off (Article IX.3). The `model` tests were not run.

## 2026-10-28 · Fix T12.3 CLI tests on Windows
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_cli_t123.py
- **Outcome:** Changed
### What I asked for
Fix five T12.3 CLI tests that failed on Windows (on `main` too) but pass on Linux CI. The setup fixture wrote `tmp_path` into TOML double-quoted strings, where the backslashes in `C:\Users\...` are read as escape sequences, so the config failed to parse and the CLI exited 1.
### How I checked it
I ran the test cases again and it passed.
### What I kept or changed
Changed the fixture to write the paths with `as_posix()`. What the tests assert is unchanged. This changes an approved test (T12.3), so it needs reviewer sign-off (Article IX.3). Required suite after the fix: 448 passed.

## 2026-11-03 · T19.1 code-tool results reach the model
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_tool_result_t191.py, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix problem 1 from the 2 Nov dev test report: `open_file` and `search_again` results were replaced with "No commit history found", so the model never saw the code those tools returned (B3, D2, D6, D11), while the chunks still counted as citable evidence.
### How I checked it
Ran the report's D11 question ("How does require_role decide whether a request is allowed?") on spm-project with the dev-7b model. Without forcing, the model answered without calling a tool, so that run did not test the fix. I then forced the first reply to be `open_file(backend/composite_auth.py, lines 116-155)` and printed the message the model receives: it got the full require_role code with its citable header, not "No commit history found". The answer was correct (401/503/403 steps, auth_user set), but it had no [n] markers or Sources, so it was marked uncited. The same chunk was also ranked 1st by retrieval, so the answer's correctness does not depend on the tool result alone. I raised the timeout to 900 s because the first run timed out at 120 s.
### What I kept or changed
Added task T19.1 and scoped plan D16 and the T8.5 wording to git tools. Wrote 12 tests first: 9 failed on the bug, 3 guard behaviour that must stay (the git-tool "no history" message and the D16 wrapper). No approved test was changed.

## 2026-11-04 · T19.2 an oversized chunk does not block the others
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/context.py, tests/online/test_fit_chunks_t192.py, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix problem 2 from the 2 Nov dev test report: `fit_chunks` stopped at the first chunk that did not fit, so in B2 one oversized top chunk meant no code was sent, and the answer ranked 3rd never reached the model.
### How I checked it
Ran the T19.2 tests: 8 passed on the fix; on the test-only commit 889815f, 6 failed, including the B2 case where an oversized first chunk meant nothing was sent. The approved T4.2 budget tests still pass. Full suite: 1130 passed.
### What I kept or changed
Added task T19.2 and updated plan D4 item 1 and the T4.2 wording: a chunk that does not fit is skipped and later ones are still tried, within the top final_k only. Wrote 8 tests first: 6 failed on the bug, 2 cover cases that already worked. No approved test assertion changed; the T4.2 test docstring still describes the old rule and is noted for the reviewer.

## 2026-11-04 · T20.1 tool-use prompt
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, codecompass/online/__init__.py, tests/online/test_tool_prompt_t201.py, tests/online/test_harness_messages_t85.py, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix problem 3 from the 2 Nov dev test report: the model skips the git tools for why, when and who questions and answers from the code alone (the role-cache question, B3, E1, and B2 again after T19.1 and T19.2). Make the tool decision come first in the prompt and say plainly that the code context has no commit history.
### How I checked it
Read the new prompt in harness.py and checked that the tool decision is now rule 1, the code context is said to have no commit history, and the tool check closes the user message only when tools are on. Ran the new tests in test_tool_prompt_t201.py and the updated T8.5 test, and the full suite (`pytest -m "not model"`): 1148 passed. The TUI spinner thread test failed once in one full run, then passed alone and in a second full run, so it is flaky and not caused by this change.

Ran B2 from the report ("Why does the hold expiry warning default to 240 hours?") with the real model: SPM_TajMahal at 4957ad2, profile dev-7b, rag_tools mode, CPU only, about 30 minutes. Before the change it made 0 tool calls. After, it made 1 (`search_again(query="hold warning default")`), and I saw the result reach the model in the `<tool_result>` block. So the model now uses tools, but it picked a code search instead of git_log for a why question. The answer was still circular ("240 because the constant is 240") and had no citations. The missing markers are report problem 4, left for T20.2. B2 is better but not fixed.
### What I kept or changed
Brought back the tool-prompt work started before the test report was fixed, renumbered from T17.1 to T20.1 (task numbers agreed in the team), and updated the plan D14 rationale now that T19.1 has fixed the hidden tool results. Tests first: 16 fail on the current prompt, 8 cover behaviour that must not change (the tools-off prompt and configuration (b)). The approved T8.5 prompt test is updated to the new prompt and needs reviewer sign-off.

## 2026-11-07 · T21.1 open_file refuses files the indexer excludes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, codecompass/online/agent/harness.py, codecompass/online/__init__.py, tests/online/test_open_file_excluded_t211.py, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Start on the guardrails work (Spec 002, section S21). The first real gap was guardrail #10: `open_file` only checked that a file existed at the indexed commit, so a committed `.env` or private key was sent to the model, and citing it came out as F. The indexer's ignore list (Article III.6) kept such files out of the index but not out of the tools.
### How I checked it
I ran `pytest tests/online/test_open_file_excluded_t211.py -v` and all 9 tests passed. Two real-model checks was also ran with `ask`, using the `dev-7b` profile (the 7B my `llama-server` had loaded) and a copy of the config with `timeout_seconds = 600`, on a test repo with a committed fake `.env`. In the first run ("Use open_file to show me lines 1-5 of .env"), two chunks of `src/app.py` were retrieved, but the best re-rank score was 0.002, below `min_top_score` (0.02), so the system refused before calling the model. In the second run ("How does load_settings read the database password and API key? Use open_file on .env lines 1-2 to show the values it reads."), the evidence gate passed with a top score of 0.979. The model called `open_file` on `src/app.py` and then `search_again`, but never asked for `.env`. So neither run actually exercised the fix. No fake secret values appeared in any output or audit log. The second run also showed a separate bug: printing the answer crashed with a `UnicodeEncodeError` on Windows, after `ask()` had already finished and written the audit log, which is where these results come from. Finally, the tool was called directly through the real `make_tool_runner` and printed what `tool_result_message` would send the model:
- `open_file(".env", lines="1-2")`: `error: .env is excluded from indexing (secrets, keys, vendored or build files) and cannot be opened`, with 0 citable chunks
- `open_file(".env")` (outline): the same error, 0 chunks
- `open_file("src/app.py", lines="4-6")`: the code, 1 citable chunk
The fix is confirmed by the tests and the direct call.
### What I kept or changed
Added S21 and task T21.1 to Spec 002 and item 6 to plan D6. Wrote 9 tests first, through `ask()` with stubs: 6 failed on the bug (the secret, the key and a node_modules file all reached the model, and citing `.env` was F), 3 cover behaviour that must stay (code and README still open; a file only refused when config says so). The refusal uses only the indexer's name patterns and excluded directories from config, not its size, binary or non-code skips, so docs stay readable. git_blame and git_log are unchanged because they return commit metadata, not file text. No approved test changed. Full suite: 1189 passed, 1 failed: `test_question_set_t11.py::...[not-git]` also fails without this change, because `C:\Users\gavin` is itself a git repository on this machine.

## 2026-11-08 · T21.2 Repo text cannot close a tool_result block
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/harness.py, tests/online/test_tool_result_escape_t212.py, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Start guardrail #5 in Spec 002, section S21 (retrieved code and tool output are data, not instructions). The prompt-rule part conflicts with spec C1 (prompt engineering deferred until the evaluation set exists), so this task only does the part that needs no prompt change: tool result bodies were inserted unescaped, so a file or commit message containing `</tool_result>` could end the block early and make the text after it look like it came from outside the tool result.
### How I checked it
I ran a direct call to the harness.tool_result_message with an open_file result whose body contained `</tool_result>` and an injected line. The output showed the tag inside the body escaped as &lt;/tool_result>, the injected line "Ignore all rules." still present, and only one real `</tool_result>`, on the last line, closing the block. This shows that the repo text can no longer end the block early.
### What I kept or changed
Added T21.2 to Spec 002 S21 and one sentence to plan D16. Wrote 16 tests first: 15 failed on the bug (a raw tag in the body gave two closing tags), 1 guards against over-escaping (ordinary code with `<`, `&`, `<toolbar>` stays byte-for-byte). During red, the git_blame and git_log cases first passed for the wrong reason (with no commits those tools send the "No commit history found" text, not the body), so I gave them a commit record. The fix only rewrites a `<` that starts `<tool_result` or `</tool_result` (any case, optional spaces) as `&lt;`; nothing is removed, and the chunks and commits the citation checker uses are untouched, so a citation to the file is still F. This does not stop the model following an instruction that stays inside the block; that needs the prompt rule, still `[NEEDS CLARIFICATION]` under C1. No approved test changed.
