# AI Use Log: Rodney Wang

## At the very start · Project architecture, constitution and AGENTS.md
- **Tool (model):** Claude chat interface (claude-sonnet-5-5)
- **Files:** AGENTS.md, docs/constitution.md, docs/specs/001-offline-indexing/*
- **Outcome:** Kept
### What I asked for
Used the Claude chat interface to create the architecture, constitution, AGENTS.md and the Spec 001 docs. I described the project and asked it to question me on the gaps instead of guessing, then went back and forth until it matched what I wanted.
### How I checked it
Skimmed through the files and have a rough sense of what's in them. I didn't review every line closely at this point.
### What I kept or changed
Kept what it produced after the question rounds. Later entries record the fixes made as review found problems.

## At the very start · Offline indexing pipeline (Spec 001)
- **Tool (model):** OpenCode (Muse Spark v1.6, free tier) for the code; OpenCode (Space Bunny, a stealth model) for the test cases
- **Files:** codecompass/offline/*, tests/offline/*
- **Outcome:** Kept
### What I asked for
Used Space Bunny to write the Spec 001 test cases first, then had Muse Spark v1.6 build the offline pipeline to make them pass.
### How I checked it
Read through the test cases roughly and ran them to confirm they pass once the code was in.
### What I kept or changed
Kept the pipeline as built. The Sprint 1 commits have no `Assisted-by` trailer, so this entry is the disclosure that AI wrote both the tests and the code. Space Bunny is a stealth model, so its provider and version aren't known.

## 2026-10-26 · Review of local dev model setup
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
Asked it to check my uncommitted dev model setup for running Qwen2.5-Coder-14B through `llama-server`.
### How I checked it
Compared the GGUF checksum and `llama-server` version myself, loaded the config, and re-ran the test suite.
### What I kept or changed
Kept the pinned model file, checksum and server settings, which all checked out. Fixed three small wording mistakes in `MODEL-SETUP.md`.

## 2026-10-26 · Low-memory generator profile
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
A separate generator profile for 16 GiB machines, instead of lowering the shared `dev` context.
### How I checked it
Checked the new profile uses the same pinned model, and ran it on a 16 GiB machine where memory stayed fine.
### What I kept or changed
Kept a new `dev-lowmem` profile with a smaller context, while `dev` stays the default. Didn't add anything for smaller machines, since that would need a constitution change.

## 2026-10-26 · Spec 002 design review and fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
A review of the constitution, specs and plans, then fixes to Spec 002 before building more online tasks.
### How I checked it
Went through the diffs against the constitution and checked every fix traces back to an article or AC. Made sure the open points were marked [NEEDS CLARIFICATION].
### What I kept or changed
Kept its fixes to citation checking, the round limit, context budgeting and git output parsing. Three points that needed the team were left as [NEEDS CLARIFICATION] instead of letting the AI decide.

## 2026-10-26 · T0.2 History fixture repo
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/fixture_repo.py, tests/online/test_fixture_repo_t02.py
- **Outcome:** Kept
### What I asked for
A fixture repo with known commits, authors and dates for testing the git tools. I approved T0.2 to T9.5's tests in advance since the plan already defined them, and Swen reviewed each one in PRs #6 to #10.
### How I checked it
Built it twice and confirmed the commits come out the same. Checked the tricky cases are there and the Sprint 1 fixture didn't change.
### What I kept or changed
Kept it separate from the Sprint 1 fixture so the offline tests aren't affected. Fixed dates and identities make it identical every build.

## 2026-10-26 · T0.3 Stub generator
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/stub_generator.py, tests/online/test_stub_generator_t03.py
- **Outcome:** Kept
### What I asked for
A fake generator so tests don't need a real model server.
### How I checked it
Made the stub return a few canned replies and checked it keeps repeating the last one. Also checked that messages recorded in round 1 don't change after round 2. The tests failed before the code and passed after.
### What I kept or changed
Kept it as built: it replays canned responses and repeats the last one. It also saves a copy of each call's messages, since a test showed later rounds could overwrite them.

## 2026-10-26 · T0.4 Stub re-ranker
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/stub_reranker.py, tests/online/test_stub_reranker_t04.py
- **Outcome:** Changed
### What I asked for
A fake re-ranker that needs no model.
### How I checked it
Tried a quick example: the chunk sharing more words with the query came out on top. Confirmed the tests went red first and green after.
### What I kept or changed
Changed it to score by shared query words instead of text length, so later tests can check relevant chunks actually move up. It records its inputs so we can prove it only sees the shortlist.

## 2026-10-26 · T1.1 RRF merge
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/rrf.py, tests/online/test_rrf_t11.py
- **Outcome:** Kept
### What I asked for
Merging the vector and keyword search results by rank (RRF).
### How I checked it
Worked out the RRF scores on paper for two short lists, including a chunk in both and a tie, and they matched the output. The tests failed first, then passed.
### What I kept or changed
Kept ranks counted from 0 as the plan says, and noted the difference from the original paper. Ties are broken by chunk id so the result is always the same.

## 2026-10-26 · T1.2 RRF configuration
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_rrf_config_t12.py
- **Outcome:** Kept
### What I asked for
Tests that the RRF settings can be configured, plus empty inputs.
### How I checked it
The tests passed straight away, so I read them to make sure they weren't passing trivially.
### What I kept or changed
T1.1 already covered most of this, so there was nothing to go red on. Kept it as a test-only task and added one test that the config file values are actually used.

## 2026-10-26 · T2.2 Keyword search wrapper
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/keyword.py, tests/online/test_keyword_search_t22.py
- **Outcome:** Kept
### What I asked for
Keyword (BM25) search through the read-only index.
### How I checked it
Threw a few messy queries at the fixture index (brackets, quotes, question marks) and nothing crashed, and a blank query just gave `[]`. Saw the tests fail before the wrapper existed.
### What I kept or changed
Kept a thin wrapper that handles punctuation and blank questions. The vector half (T2.1) was blocked because the index had no vector search yet.

## 2026-10-26 · T3.1 Re-ranker protocol
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/reranker.py, tests/online/test_reranker_protocol_t31.py
- **Outcome:** Kept
### What I asked for
The re-ranker interface, so the fake and the real one can be swapped.
### How I checked it
Checked the fake matches the interface and no real model code got into the required tests.
### What I kept or changed
Kept just the interface. The real re-ranker waits for a later task where it can be tested against the actual model.

## 2026-10-26 · T4.1 Chunk formatting
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/context.py, tests/online/test_context_format_t41.py
- **Outcome:** Kept
### What I asked for
Format retrieved chunks as plain text with file, line and commit info for the model.
### How I checked it
Printed one formatted chunk and lined its header up against the `Sources` format in the constitution. Made sure no vector field shows up anywhere in it.
### What I kept or changed
Kept a header that matches the citation format, with one shared function so the two can't drift apart. Vectors are dropped so they never reach the prompt.

## 2026-10-26 · T5.1 Tool argument validation
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_validation_t51.py
- **Outcome:** Kept
### What I asked for
Validate the arguments the model passes to `git blame` and `git log`.
### How I checked it
Tried paths like `../`, `-rf` and a folder name, and all of them got rejected. Names like `app/(auth)/page.tsx` still went through.
### What I kept or changed
Kept the rule that a path must be a real file in the repo, which blocks anything outside it. Added tests so normal filenames with odd characters still pass.

## 2026-10-26 · T5.2 git_blame executor
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_git_blame_t52.py
- **Outcome:** Kept
### What I asked for
Run `git blame` safely for the model.
### How I checked it
Ran `git blame --porcelain` myself on a fixture file and compared it with what the tool returned. Same commits, same lines.
### What I kept or changed
Kept a short per-commit summary instead of raw blame output. It always uses the indexed commit, and errors come back as messages instead of crashes.

## 2026-10-26 · T5.3 git_log executor
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_git_log_t53.py
- **Outcome:** Kept
### What I asked for
Run `git log` on a file for the model, capped at a set number of commits.
### How I checked it
Compared the parsed records with my own `git log` run on the fixture. The author with a space and the subject with a comma both came through correctly.
### What I kept or changed
Kept a separator format so names with spaces and subjects with commas parse correctly. It shares its output format with `git_blame`.

## 2026-10-26 · T5.4 Tool allow list
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_allowlist_t54.py
- **Outcome:** Kept
### What I asked for
Only the allowed git tools can run, and anything else is refused with a readable message.
### How I checked it
Put `git_diff` into `allowed_tools` in config and it was still refused. Read the dispatch table to be sure only the two git tools are in it.
### What I kept or changed
Kept the allow list in code so config can't add tools. Unexpected arguments are refused too.

## 2026-10-26 · T5.5 Tool-result cache
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/cache.py, tests/online/test_tool_cache_t55.py
- **Outcome:** Kept
### What I asked for
Cache tool results within one question and record cache hits.
### How I checked it
Read the cache key next to Article V.3. The docstring explains why repo and commit aren't in the key, and that reasoning holds since a cache only lives for one question.
### What I kept or changed
Kept a per-question cache keyed on the tool and its arguments. Repo and commit are left out because they're fixed within one question, and the docstring explains why.

## 2026-10-26 · T5.6 Tool output cap
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tools.py, tests/online/test_tool_cap_t56.py
- **Outcome:** Changed
### What I asked for
Cap each tool result so tool output can't overflow the model's context.
### How I checked it
Ran `git blame` on a big fixture file and saw the `[output truncated: N more lines]` marker. Commits from the cut-off lines were gone from the records too.
### What I kept or changed
Kept cutting at whole lines with a visible marker. Added a rule that commits from cut lines can't be cited, and had it refactored to avoid slow repeated counting.

## 2026-10-26 · T6.1 Tool-call parser
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/agent/tool_parser.py, tests/online/test_tool_parser_t61.py
- **Outcome:** Kept
### What I asked for
Read tool requests from the model's text, and treat anything malformed as a final answer.
### How I checked it
Fed it a positional argument, `os.system(...)` and a nested call. Each one came back as a plain final answer and nothing got evaluated.
### What I kept or changed
Kept a strict parser that only accepts simple `name(key=value)` calls and never runs anything. Unknown tool names still parse, so the model gets told they're refused.

## 2026-10-26 · T9.1 Source entry parser
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/parser.py, tests/online/test_source_parser_t91.py
- **Outcome:** Kept
### What I asked for
Parse the answer's `Sources` section into code and commit citations.
### How I checked it
Wrote a few `Sources` sections myself, one with a broken entry and one with `arr[0]` in the text. The broken entry was kept as invalid and `arr[0]` wasn't treated as a citation.
### What I kept or changed
Kept strict matching since the format is fixed. Malformed entries are kept as invalid so they get flagged, and code like `arr[0]` isn't mistaken for a citation.

## 2026-10-26 · T9.2 Citation checker: verified answers
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_citation_checker_f_t92.py
- **Outcome:** Kept
### What I asked for
The checker that marks an answer verified when every citation matches evidence the model was given.
### How I checked it
Wrote an answer citing lines inside one retrieved chunk and another spanning two neighbouring chunks. Both came back as verified (F).
### What I kept or changed
Kept the rule that a cited range must be fully inside retrieved chunks. Commit citations only match real tool results.

## 2026-10-26 · T9.3 Citation checker: flagged answers
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_citation_checker_g_t93.py
- **Outcome:** Kept
### What I asked for
Every way a citation can fail should get the answer flagged.
### How I checked it
Gave it an answer citing a file that was never retrieved, and one whose range ran past the chunk (50-70 against 42-58). Both were flagged (G).
### What I kept or changed
Most tests already passed from T9.2, and the rest covered the new cases. Kept a test for a range that runs past a chunk, which the original plan would have let through.

## 2026-10-26 · T9.4 Flagged answer formatting
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/formatter.py, tests/online/test_citation_format_t94.py
- **Outcome:** Kept
### What I asked for
Show a flagged answer with a banner and a mark on each unverified source, so it never looks verified.
### How I checked it
Rendered a flagged answer and a verified one side by side to make sure you can always tell them apart. Also read the banner wording to check it never says the answer is "true".
### What I kept or changed
Kept the banner and `[UNVERIFIED]` mark, with a test that the banner never claims the answer is "true". Added a line for markers with no source entry, which the plan missed.

## 2026-10-26 · T9.5 Harness-copied commit metadata
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/checker.py, tests/online/test_commit_metadata_t95.py
- **Outcome:** Kept
### What I asked for
Commit details in `Sources` must come from the git tool, never from the model.
### How I checked it
Wrote an answer where the model claims the wrong author and date. The rendered `Sources` line showed the real ones from `git log` instead.
### What I kept or changed
Kept the checker overwriting commit details from the tool result. Unverified entries are left as written so the reader can see what the model claimed.

## 2026-10-26 · Vector search on the read-only index handle
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/stores/vector.py, codecompass/offline/__init__.py, tests/offline/test_vector_search.py
- **Outcome:** Changed
### What I asked for
A review found the read-only index had no vector search, which blocked T2.1. Asked for a tests-first fix.
### How I checked it
Ran a search on a small index by hand and got ranked ids back. Checked the read-only handle still has no write methods.
### What I kept or changed
Added a `search` method that works like the keyword one. It handles empty stores and stays read-only.

## 2026-10-26 · Query embedder on the index handles
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/__init__.py, tests/offline/test_query_embedder.py
- **Outcome:** Changed
### What I asked for
The online side needed to embed questions without importing offline internals, and the embedder check was too loose. Asked for both to be fixed tests-first.
### How I checked it
Compared `codecompass.offline.__all__` before and after, no change. Then opened the index with a mismatched embedder and it was refused.
### What I kept or changed
The embedder now comes attached to the index handles. Both the config and the actual embedder must match the index or it's refused.

## 2026-10-26 · Online config merge without a TOML round trip
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/config.py, codecompass/online/config.py, tests/online/test_config_merge.py
- **Outcome:** Changed
### What I asked for
The online config loader broke on values like Windows paths because it rewrote them to a temp file. Asked for a tests-first fix.
### How I checked it
Loaded a config with a Windows-style path full of backslashes and quotes, plus a relative `index.dir`. The values came out right and the path resolved next to the real config file.
### What I kept or changed
The loader now passes settings directly instead of rewriting a file. This also fixed relative index paths resolving to the wrong folder.

## 2026-10-26 · Spec 002 follow-up fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** AGENTS.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
A second review found more gaps. Asked for them to be fixed without changing finished tasks or approved tests.
### How I checked it
Read each change against the constitution and approved tests. Every AC now maps to a task.
### What I kept or changed
Fixed the plan to match the approved code and gave every AC a task. Dropped one draft change that would have contradicted approved tests.

## 2026-10-26 · Pushed straight to main (self-reviewed)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** branches `fix/vector-search`, `fix/query-embedder`, `fix/config-merge`, `docs/spec-002-followups`
- **Outcome:** Changed
### What I asked for
Merge four branches straight into `main` without opening PRs. I'm recording it here because these didn't go through the usual PR review.
### How I checked it
Reviewed all four branches myself: read the diffs, ran the test suite after the merge, and checked each branch's test commit comes before its fix.
### What I kept or changed
Used merge commits so the test-first order stays visible. The embedder check and config loader changes touch Sprint 1 code, so those most need a teammate's look.

## 2026-10-26 · Review follow-ups: model setup, eval modes, docs fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** MODEL-SETUP.md, codecompass.toml, AGENTS.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Finish the remaining review items and push them straight to `main` without a PR. I reviewed these changes myself.
### How I checked it
Read each docs change, loaded the merged config myself, and re-ran the tests.
### What I kept or changed
Merged the model setup docs, fixed a dead link in AGENTS.md, and added the three evaluation modes to Spec 002. Drafted a constitution fix but didn't apply it, since agents can't edit the constitution. (I later chose to have it applied, see the next entry.)

## 2026-10-26 · Constitution 1.2.1 clarifications
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix the constitution errors the review found. I asked for this on purpose, overriding the rule that agents don't edit the constitution, because these were changes I wanted anyway.
### How I checked it
Checked each clarification matches what the spec and code already do, so it's only a PATCH bump. Left it on a branch for review.
### What I kept or changed
Four wording clarifications (version 1.2.1), none changing meaning. It went into `main` through PR #12, reviewed and merged by Gavin (no review comments).

## 2026-10-26 · T2.1 Vector search wrapper
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/retrieval/vector.py, tests/online/test_vector_search_t21.py
- **Outcome:** Kept
### What I asked for
A wrapper that returns the closest chunks by vector similarity.
### How I checked it
Worked out cosine similarities for the small fixture by hand and the returned order matched.
### What I kept or changed
Kept it as drafted, matching the keyword search wrapper. It takes a vector, since embedding the question is a separate task.

## 2026-10-26 · Constitution gaps and prompt reuse across rounds
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Fix the remaining problems in the constitution and optimise the architecture.
### How I checked it
Checked each change doesn't contradict approved tests or ACs, and that trade-offs were left for the team.
### What I kept or changed
Filled five small gaps in the constitution and added prompt reuse across rounds as a logged setting. Bigger trade-offs were left for the team, and it went in through PR #12, reviewed and merged by Gavin (no review comments).

## 2026-10-26 · T9.7 Uncited answers and uncited parts
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/citation/formatter.py, tests/online/test_uncited_t97.py, tests/online/test_citation_format_t94.py, docs/constitution.md, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Team decision: anything in an answer that cites nothing should be clearly marked so the developer checks it.
### How I checked it
Rendered an answer with no citations and one that's only partly cited, and checked the note and the "(not cited)" marks. Read the changed T9.4 test against the amended AC-4.8.
### What I kept or changed
Answers with no citations get a note instead of the "could not be verified" banner, and uncited paragraphs get "(not cited)". One approved test was changed to match the updated spec, which went in through PR #12, reviewed and merged by Gavin (no review comments).

## 2026-10-26 · T0.5 Configurable round limit and tool settings validation
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/constitution.md, codecompass/online/config.py, codecompass/online/agent/tools.py, tests/online/test_tool_settings_t05.py, docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
Team decision: keep the tool round limit in config so it can be changed later.
### How I checked it
Started the app with `max_verifier_rounds` set to -1, then 1.5, then an unknown tool name. Each one failed loudly at startup.
### What I kept or changed
Amended the constitution to 1.3.0 so the limit is configurable but always bounded. Config can switch tools off but never add one, and no approved tests changed.

## 2026-11-01 · Dev environment, local models and a dev-7b profile
- **Tool (model):** Claude Code (claude-opus-5-5, claude-sonnet-5-5)
- **Files:** codecompass.toml
- **Outcome:** Changed
### What I asked for
Set up the environment and download the real models. The 14B doesn't fit my 8 GB GPU, so I asked for a 7B profile instead.
### How I checked it
Checked the model checksums and revisions, and ran both test suites myself.
### What I kept or changed
Added a `dev-7b` profile, with `dev` still the default; results from it are only development signals. One model test fails because the 7B doesn't put citation markers in its answers, which the checker correctly flags.

## 2026-11-01 · Spec 004 minimal terminal UI (spec, plan, tasks)
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md
- **Outcome:** Changed
### What I asked for
A lightweight terminal UI that starts when I type `codecompass` and answers questions about the repo it's run from.
### How I checked it
Read the spec, plan and tasks against the constitution and checked my answers to the open questions were recorded right.
### What I kept or changed
Kept it small, built on the existing `ask()`, and printing answers as-is so flagged answers never look verified. One question (input history) was left open.

## 2026-11-01 · T0.1 Reuse default models across questions
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** tests/online/test_model_reuse_tui_t01.py, codecompass/offline/embedding.py, codecompass/offline/__init__.py, codecompass/online/__init__.py
- **Outcome:** Changed
### What I asked for
Load the models once per session instead of for every question, without weakening the embedder check.
### How I checked it
Asked three questions in a row and checked the models only load once. Also made sure a mismatched embedder still gets refused even when it's cached.
### What I kept or changed
Added a small cache for the embedder and re-ranker. The first version broke an existing test, so the code was fixed rather than the test.

## 2026-11-01 · T1.1 Terminal UI session loop
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_session_t11.py
- **Outcome:** Changed
### What I asked for
The question-and-answer loop: read a question, print the answer, and quit cleanly.
### How I checked it
Used the loop myself: asked a question, then tried `/exit` and Ctrl-C. Piped the output to a file to check only the answer goes to stdout.
### What I kept or changed
Only the answer goes to stdout, while prompts and errors go to stderr. A test caught a bug where empty error messages printed blank, and the code was fixed.

## 2026-11-01 · T1.2 Terminal UI startup and wiring
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_main_t12.py
- **Outcome:** Changed
### What I asked for
Make `codecompass` find the repo, load the right config, check the model server, and call the real `ask()`.
### How I checked it
Ran `codecompass` from the repo root, from a subfolder and from a folder that isn't a repo. Did it with `llama-server` on and off to see the banner, warning and errors.
### What I kept or changed
A missing model server only gives a warning with the command to start it. Input history was left out because it needs a design change.

## 2026-11-01 · T1.3 The `codecompass` command
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** tests/online/test_tui_entry_t13.py, pyproject.toml
- **Outcome:** Changed
### What I asked for
Make typing `codecompass` start the TUI, and put all the TUI work on one branch.
### How I checked it
Ran `pip install -e .` in a fresh venv, and typing `codecompass` started the TUI. Checked setuptools is pinned in `pyproject.toml`.
### What I kept or changed
Added the command entry and a pinned build backend to `pyproject.toml`. All TUI commits are now on `feat/tui`.

## 2026-11-01 · T1.4 README for interactive mode, stub index removed, speed measurements
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** README.md
- **Outcome:** Changed
### What I asked for
README docs for the TUI, delete an old test index, and find out why the first question is so slow.
### How I checked it
Followed the README steps myself and re-ran the timing once.
### What I kept or changed
Added an "Interactive mode" README section. The embedder is about 27x faster on the GPU, and my `llama-server` build had no GPU support; streaming was skipped because it needed a spec decision first.

## 2026-11-01 · Spec 004 phase 2: draft streaming, warm-up and layered config (spec only)
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md, ~/.config/codecompass/codecompass.toml (outside the repo)
- **Outcome:** Changed
### What I asked for
Streaming output, a faster first question, and whether the re-ranker should run on the GPU.
### How I checked it
Read the spec changes and timing logs, and checked the open questions were recorded.
### What I kept or changed
Moving models to the GPU cut the first question from about 350 s to about 100 s. I chose to show an unchecked draft on stderr, and specced layering user and repo config files; this was spec only, no code.

## 2026-11-01 · T2.1 Layered config
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/config.py, tests/online/test_tui_layers_t21.py
- **Outcome:** Changed
### What I asked for
Let my personal settings still apply in a repo that has its own config file.
### How I checked it
Ran the TUI in a repo that has its own `codecompass.toml`. My personal GPU settings still applied, and the banner listed both files.
### What I kept or changed
Added a new loader that layers the user file under the repo file, leaving the old loader untouched. One thing to review: the new loader rejects typo'd section names where the old one ignored them.

## 2026-11-01 · T2.2 Streaming in the generator
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/generator/llama.py, tests/support/fake_http.py, tests/online/test_stream_generator_t22.py
- **Outcome:** Changed
### What I asked for
Let the generator stream text as it's written, kept inside the one generator wrapper.
### How I checked it
Asked the same question against the real `llama-server` with streaming on and off. The final text matched both times.
### What I kept or changed
Added streaming with a fallback to a normal call if the server refuses. Fixed two of my own tests that were failing for the wrong reason.

## 2026-11-01 · T2.3 Draft through the harness and ask()
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/agent/harness.py, codecompass/online/logging.py, codecompass/online/__init__.py, tests/support/stub_generator.py, tests/online/test_draft_t23.py
- **Outcome:** Changed
### What I asked for
Pass the streamed text up through `ask()` to an optional callback, never forwarding tool-call text.
### How I checked it
Tried a model reply with a `<tool>` tag in the middle. Only the text before the tag got forwarded. I also did a final manual review at the end, though a light one given the volume of changes.
### What I kept or changed
Added a small filter that stops forwarding at a tool tag. From here on I told the assistant to treat test approval as given for the rest of the TUI tasks (T2.4 to T2.6). They were low risk: terminal display, background warm-up and docs, none of which change retrieval or citation checking. They were reviewed and merged by Gavin in PR #23 (no review comments).

## 2026-11-01 · T2.4 The draft in the terminal
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui.py, tests/online/test_tui_draft_t24.py, docs/specs/004-tui/spec.md, docs/specs/004-tui/plan.md, docs/specs/004-tui/tasks.md
- **Outcome:** Changed
### What I asked for
Show the model's text live as a clearly labelled unchecked draft, with only the checked answer on stdout and a `--no-draft` option.
### How I checked it
Asked a question in a real terminal and watched the draft header, the closing lines and then the checked answer. With `--no-draft`, and when piped, no draft showed up.
### What I kept or changed
Updated the spec first to use closing lines instead of a live timer, and to strip control characters from the draft. Fixed two of my own test assertions in a separate commit before the code.

## 2026-11-01 · T2.5 Background warm-up
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/__init__.py, codecompass/online/tui.py, tests/online/test_warmup_t25.py
- **Outcome:** Changed
### What I asked for
Update the index and load models in the background while I type my first question.
### How I checked it
Typed a question while warm-up was still running and got the "Preparing index and models…" message. Typing `/exit` during warm-up quit straight away.
### What I kept or changed
Warm-up runs in a background thread, and an early question just waits for it. One small risk is the thread misbehaving at exit, though I haven't seen it.

## 2026-11-01 · T2.6 Docs for draft, warm-up, layered config and GPU settings; real terminal check
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** README.md, docs/specs/004-tui/spec.md
- **Outcome:** Changed
### What I asked for
Document the new TUI features and check the whole thing in a real terminal.
### How I checked it
Followed the docs and asked a question against the 7B server myself.
### What I kept or changed
Updated the README and marked Spec 004 implemented. The real run worked end to end, and the 7B's missing citation markers were again correctly flagged.

## 2026-11-01 · GPU build, measurements, and Spec 005 / T3.1 re-ranker precision
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** docs/specs/005-gpu-inference/*, codecompass/online/config.py, codecompass/online/retrieval/reranker.py, codecompass/online/__init__.py, tests/online/test_reranker_dtype_t31.py
- **Outcome:** Changed
### What I asked for
Get the 7B and the re-ranker running together on my 8 GB GPU so questions take seconds, not minutes.
### How I checked it
Checked the llama.cpp download's SHA-256 against GitHub's digest and ran `llama-server --list-devices` to see the GPU. Then timed a real question.
### What I kept or changed
Installed a GPU build of llama.cpp, which made generation about 40x faster. Added a half-precision option for the re-ranker so it fits beside the model, with the default unchanged.

## 2026-11-01 · T3.2 dev-7b-gpu profile and T3.3 GPU docs, with end-to-end measurements
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass.toml, tests/online/test_gpu_profile_t32.py, docs/specs/005-gpu-inference/*, README.md, ~/.config/codecompass/codecompass.toml (outside the repo)
- **Outcome:** Changed
### What I asked for
A GPU profile that fits the 7B and the re-ranker on my 8 GB card, plus docs and a real test.
### How I checked it
Started the server from the printed command and asked several questions while watching GPU memory. Read the spec change that came before the test edit.
### What I kept or changed
The first profile ran out of memory, so I measured settings and picked one that worked every time. My own test was updated to match after a spec change, and questions now take 5 to 12 s instead of about 100 s.

## 2026-11-01 · T3.4 to T3.6 Make it work on Linux, Windows and macOS
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/tui.py, tests/online/test_reranker_devices_t34.py, tests/online/test_tui_platform_t35.py, .github/workflows/ci.yml, README.md, docs/specs/005-gpu-inference/*
- **Outcome:** Changed
### What I asked for
Make sure the project works on Windows and Mac, not just my Linux laptop.
### How I checked it
Watched the CI run go green on Ubuntu, Windows and macOS. Read the fixture isolation commit to make sure it doesn't change anything on Linux.
### What I kept or changed
Fixed several Linux-only assumptions and made CI run on all three platforms. To fix the Windows CI failures I edited a shared test fixture from an earlier approved test file; it only isolates the config folders, changes nothing on Linux, and is in its own commit. I couldn't test on a real Windows or Mac machine, so the README marks those as untested; this was reviewed and merged by Gavin in PR #24 (no review comments).

## 2026-11-01 · Indexing a new repo ran out of memory (embedding batches)
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/offline/embedding.py, codecompass/offline/config.py, codecompass/offline/orchestrator.py, tests/offline/test_embed_budget.py, README.md, docs/specs/001-offline-indexing/plan.md
- **Outcome:** Changed
### What I asked for
Indexing another repo hung for 36 minutes, so I asked Claude to find out why and fix it properly.
### How I checked it
Re-ran indexing `spm_proj` under a memory cap and watched peak memory. Read the changed test constant and its commit message before signing off on it.
### What I kept or changed
The cause was batches of very long chunks using too much memory, so batches are now limited by a configurable size budget. Changing the default meant editing one of my approved tests, which was approved in PR #25 by Nicole and Gavin.

## 2026-11-02 · Chunker sized chunks by words, not the embedder's tokens
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/offline/orchestrator.py, tests/offline/test_chunk_embedder_tokens.py
- **Outcome:** Changed
### What I asked for
One oversized chunk still ran out of memory, so I asked Claude to fix that too.
### How I checked it
Re-chunked `spm_proj` with the real tokenizer and nothing was over 8,192 tokens. `codecompass check` said both stores agree.
### What I kept or changed
The chunker was counting words instead of the embedder's tokens, against the spec, so it now uses the real tokenizer. With both fixes the repo indexes under a 6 GB cap; lowering the max chunk size needs a spec decision, so I left it.

## 2026-11-01 · Hide the jina "optimum is not installed" warning
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/offline/embedding.py, tests/offline/test_optimum_warning.py
- **Outcome:** Changed
### What I asked for
Hide a harmless warning the embedder prints on every start, and only that one.
### How I checked it
Started the embedder by hand. The optimum warning was gone and other warnings still showed.
### What I kept or changed
The warning is suppressed only while the model loads. It can still slip through occasionally when threads overlap.

## 2026-11-02 · Evidence gate: refuse when nothing retrieved matches the question
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/__init__.py, tests/online/test_evidence_gate_t151.py, docs/specs/002-online-retrieval/spec.md, plan.md, tasks.md; three approved-test setups (tests/online/ask_support.py, test_cli_t123.py, test_tui_main_t12.py)
- **Outcome:** Changed
### What I asked for
The 7B answered "What is the capital of France?" with no evidence at all, which breaks the grounding rule. I asked for a fix.
### How I checked it
Asked "What is the capital of France?" and got refused with the closest files. A real question about the repo still got answered. Read the setup-only change to the three approved test files.
### What I kept or changed
If the best retrieved match scores below a threshold, the app refuses and lists the closest files instead. The threshold (0.02) is a provisional guess until the evaluation set exists; six approved tests (in three files) needed the gate turned off in their setup, with no assertion or question changed; Nicole and Gavin approved this in PR #26.

## 2026-11-02 · Say what is wrong when a real source is listed but not referenced
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/citation/checker.py, codecompass/online/citation/formatter.py, codecompass/online/models.py, codecompass/online/__init__.py, tests/online/test_unreferenced_t161.py, docs/specs/002-online-retrieval/spec.md, plan.md, tasks.md
- **Outcome:** Changed
### What I asked for
Answers were marked `[UNVERIFIED]` even when the source was real, just never referenced in the text. I asked for the wording to say what's actually wrong.
### How I checked it
Rendered one answer with a real source that's listed but never referenced, and one with a made-up source. Each got its own banner and mark.
### What I kept or changed
These answers are still flagged, but real sources now get `[NOT REFERENCED IN ANSWER]` and a matching banner. No approved test needed editing.

## 2026-11-02 · TUI: show how many tools an answer used, and a more modern look
- **Tool (model):** Claude Code (claude-sonnet-5-5)
- **Files:** codecompass/online/tui_view.py (new), codecompass/online/tui.py, tests/online/test_tui_tools_t31.py, test_tui_color_t32.py, test_tui_answer_color_t33.py, test_tui_look_t34.py, README.md, docs/specs/004-tui/spec.md, plan.md, tasks.md
- **Outcome:** Changed
### What I asked for
A more modern TUI in a Rosé Pine colour scheme, with a count of the tools each answer used. Later I asked for a `/theme` command and a look more like Claude Code.
### How I checked it
Went through it in a real terminal: the tool count, `/tools`, both themes, `/theme`, `--no-color`, `NO_COLOR` and piped output. Checked the flagged banner's words didn't change. I also did a final manual review at the end, though a light one given the volume of changes.
### What I kept or changed
- Claude asked me to settle a few spec conflicts first, so clicking became a `/tools` command and the flagged banner keeps its exact wording. The spec was updated before any code.
- Added colour themes (dark and a light version), with contrast checked so text stays readable. Colour is only used on a real terminal, so piped output stays plain.
- Added a `/theme` command to switch colour on or off for the session.
- For the Claude Code-style look (boxed prompt, spinner, live tool lines, styled markdown), I let Claude do T4.2 to T4.5 without stopping for approval, since this was low-risk display work that doesn't touch retrieval or citation checking. It still wrote tests first and fixed its own code instead of an approved test when one failed.
- A real-terminal check found two small spinner glitches, which were fixed with a new test. Everything went through PR #27, which Nicole reviewed and Gavin merged.

