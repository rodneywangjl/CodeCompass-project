# AI Use Log: Nicole Goh

## 2026-10-07 · Project context, evaluation definitions and Claude Code setup
- **Tool (model):** Claude, in the Claude app (claude-opus-5-5)
- **Files:** AGENTS.md, .gitignore, CLAUDE.local.md (local only, git-ignored)
- **Outcome:** Kept
### What I asked for
I gave Claude our project proposal, the course brief, the AI-use policy, the log template and a copy of the repo, and asked it to pull out my responsibilities as evaluation, documentation and AI-log owner. I asked it to draft a personal Claude Code context file and to propose shared evaluation rules for AGENTS.md, including a definition of a hallucinated answer and the metric definitions. I also asked it to list cross-team gaps that affect evaluation without changing my teammates' code.
### How I checked it
Claude worked only on an unpacked copy of my ZIP, never my real repo. I reviewed its diff for AGENTS.md and .gitignore (43 lines added, none removed), and `git check-ignore -v CLAUDE.local.md` confirmed the file was ignored. When an automatic hook asked it to commit, it refused because I hadn't given permission. After I copied the changes into my repo, a Claude Code check (`git status`, `git diff --ignore-cr-at-eol --stat`, `git check-ignore -v`) showed that the .gitignore lines were missing, CLAUDE.local.md was empty and the hit-rate wording in §4.3 was out of date. I fixed all three, and the re-check passed: only AGENTS.md and .gitignore changed, AGENTS.md only gained lines, and both files use CRLF. I also compared §4.3 against the constitution and Spec 002 myself, using Claude Code's list of gaps.
### What I kept or changed
I dropped the first context file it drafted from the proposal because it predated the repo and was out of date: it listed Whoosh and voyage-code as undecided and used the 32B model with a 14B fallback. I kept the AGENTS.md additions, including §4.3, which is marked provisional until the team reviews it. I also kept the .gitignore entries and the git-ignored CLAUDE.local.md.

## 2026-10-07 · Setup verification, review of §4.3 and AI log
- **Tool (model):** Claude Code (Claude Opus 5.5, claude-opus-5-5)
- **Files:** ai-log/nicole-goh.md, docs/checkpoint/ai-use-declaration.md, ai-log/rodney-wang.md, ai-log/gavin-tay.md, ai-log/kelsey-la.md, AGENTS.md (§4.3 open questions; also reviewed .gitignore, CLAUDE.local.md)
- **Outcome:** Kept
### What I asked for
I asked Claude Code to check that the earlier session's changes were in my repo as intended, and to check the new §4.3 evaluation rules against the constitution and Spec 002 without editing them. I also asked it to create this log file and draft both entries, and to prepare a commit without running it. Later I asked it for a reminder message and a blank log template for teammates without a log, and for a draft of the team AI-use declaration that summarises only what is in each member's log.
### How I checked it
I read the git output it showed and agreed with its findings: the missing .gitignore lines, the empty CLAUDE.local.md and the hit-rate wording that didn't match. I checked its list of §4.3 gaps against the constitution and Spec 002 myself. I reviewed this log file and the final diff before each commit.
### What I kept or changed
I shared all of its §4.3 findings with the team and added them to AGENTS.md §4.3 as open questions for Spec 003, leaving the existing definitions unchanged. I kept the reminder message, the blank template and the heading-only starter logs for Rodney, Gavin and Kelsey, created with their agreement. After I gave it the AI-use policy, I had the declaration draft reworked to the policy's §5.1 format: one short paragraph covering only what is in the logs.

## 2026-10-28 · Spec 002 block 4 overview
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** ai-log/nicole-goh.md
- **Outcome:** Kept
### What I asked for
Completed block 4 of the Spec 002 rollout on feat/ask-pipeline-audit-log-cli. This phase wires every online stage into `ask()`, the single entry point for a question (T9.6, T12.1, T12.2), adds index-freshness handling (T10.1–T10.3), the per-query audit log (T11.1–T11.3), the `ask` CLI (T12.3) and the three evaluation modes (T12.4), plus a fix so `ensure_current` defaults to the configured embedder. The code and tests were carried over with help from Claude Code. Before carrying them over, I had Claude Code check that block 3 on `main` matched what block 4 expected, predict conflicts and do a throwaway dry run.
### How I checked it
All 17 commits applied cleanly, with no conflicts and no adaptations; each patch is identical to the original. Block 3 on `main` matched the code (`git range-diff`), so Kelsey's "deviations" were environment-only. On Windows, tantivy and tree-sitter DLLs are blocked by Application Control and two tests have a Windows-only TOML path issue, outside the scope of this block. Re-ran the full required suite (`pytest -m "not model"`) in WSL (Ubuntu, Python 3.14) on the same branch: all 446 selected tests passed (410 on `main` plus 36 from this block).
### What I kept or changed
Until block 5 adds `BgeReranker` (T13.1), `ask()` needs a re-ranker passed in.

## 2026-10-28 · T9.6 Citation checker is non-bypassable
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/ask_support.py, tests/online/test_citation_nonbypassable_t96.py, codecompass/online/__init__.py
- **Outcome:** Kept
### What I asked for
T9.6: Every `ask()` runs the citation checker exactly once, in every mode and on the no-evidence path. No configuration field can switch it off, and a generator citing a file that was not retrieved is always flagged G.
### How I checked it
test_citation_nonbypassable_t96.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T10.1 ensure_current before answering
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_ensure_current_t101.py, codecompass/online/__init__.py
- **Outcome:** Kept
### What I asked for
T10.1: `ask()` calls `ensure_current` before opening the index. If it succeeds, the answer is not stale. If it fails or the index is locked, the answer still comes from the existing index with the stale flag set. If there is no index yet, the answer says so without retrieval or generation, and nothing is raised.
### How I checked it
test_ensure_current_t101.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T10.2 Stale-index fallback
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_stale_fallback_t102.py, codecompass/online/__init__.py
- **Outcome:** Kept
### What I asked for
T10.2: When `ensure_current` fails, the answer starts with the stale-index warning and the failure reason, followed by the normal answer. `stale_index` is True and `stale_message` holds the reason.
### How I checked it
test_stale_fallback_t102.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T10.3 Empty index and no evidence
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/online/test_empty_index_t103.py, codecompass/online/__init__.py
- **Outcome:** Kept
### What I asked for
T10.3: An index with no chunks, or a context budget that fits no chunk, gives the "could not find enough evidence" answer without calling the generator.
### How I checked it
test_empty_index_t103.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T11.1 Per-query audit log
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/logging.py, tests/online/test_audit_log_t111.py
- **Outcome:** Kept
### What I asked for
T11.1: Each query's audit log holds the question, profile, model id, every retrieved chunk with its RRF and re-ranker scores (and whether it was sent), every tool call (round, tool, arguments, cache hit), the citation outcome and per-stage timings.
### How I checked it
test_audit_log_t111.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T11.2 Audit log persistence
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/logging.py, tests/online/test_audit_persist_t112.py
- **Outcome:** Kept
### What I asked for
T11.2: Every `ask()` writes its audit log as JSON under `logging.query_log_dir`, with a file name starting with a UTC timestamp. A stale-index warning is recorded in the log.
### How I checked it
test_audit_persist_t112.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T11.3 Profile and model in the log
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/logging.py, tests/online/test_audit_profile_t113.py
- **Outcome:** Kept
### What I asked for
T11.3: Every audit log records the profile name, resolved model id, `cache_prompt`, pipeline mode and the `max_verifier_rounds` in force.
### How I checked it
test_audit_profile_t113.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T12.1 ask() entry point
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/__init__.py, tests/online/test_ask_t121.py
- **Outcome:** Kept
### What I asked for
T12.1: `ask()` returns a `QueryResult` with the answer, sources, citation outcome, stale flag, stale message and audit log, and prints nothing. The embedder given to `ask()` reaches both `ensure_current` and `open_index`, and an index built with a different embedder is refused.
### How I checked it
test_ask_t121.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T12.2 Full pipeline integration test
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/__init__.py, tests/online/test_full_pipeline_t122.py
- **Outcome:** Kept
### What I asked for
T12.2: One question runs end to end on the fixture repo with stubs and real stores: ensure_current, open_index, embedding, vector and keyword search, RRF, re-rank, budget, a tool round, the citation check, then the rendered answer, sources and audit log.
### How I checked it
test_full_pipeline_t122.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T12.3 ask CLI
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/cli.py, tests/online/test_cli_t123.py
- **Outcome:** Kept
### What I asked for
T12.3: The `ask` command prints the rendered answer and logs the profile and model id once at startup. `--profile` selects a profile and `--verbose` prints retrieved chunks and tool calls. Flagged and stale answers show their warnings before the answer text.
### How I checked it
test_cli_t123.py passed in WSL. On Windows, five of its tests fail because the test writes a Windows path into TOML; this is environment-only and outside this block.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · T12.4 Evaluation modes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/online/config.py, codecompass/online/__init__.py, tests/online/test_modes_t124.py
- **Outcome:** Kept
### What I asked for
T12.4: A `pipeline.mode` setting for the three Article VII.3 configurations. The default is `rag_tools`, and an unknown mode fails loudly. `rag` retrieves and re-ranks but runs no tools. `no_retrieval` sends no chunks. Every mode uses the same model, and the log records the mode.
### How I checked it
test_modes_t124.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-10-28 · ensure_current default embedder fix
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/__init__.py, tests/offline/test_ensure_default_embedder.py
- **Outcome:** Kept
### What I asked for
Fix outside a numbered task, found while wiring `ask()`: with no embedder given, a needed re-index failed. Like `open_index`, `ensure_current` now builds the pinned embedder from config, and only on the re-index path, so the fast path still loads nothing.
### How I checked it
test_ensure_default_embedder.py passed in WSL.
### What I kept or changed
Kept unchanged.

## 2026-11-02 · Review of PR #27 (modern terminal UI)
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** none changed (review only of PR #27: codecompass/online/tui.py, tui_live.py, tui_view.py, run.py and their tests)
- **Outcome:** Kept
### What I asked for
I asked Claude Code to summarise Rodney's open PRs (#25, #26, #27) without changing any files, and to explain what each one changes and how it affects our evaluation plan. For PR #27, I asked why its CI was failing on Windows and how to test it locally in WSL, including a checklist for trying the live terminal UI with our 14B model.
### How I checked it
I fetched the PR through Windows (WSL had no GitHub login) and confirmed I was on commit 60672b8. `pytest -m "not model"` in WSL gave 981 passed, matching the PR description. I read the Windows CI failure myself (`test_config_t02` UnicodeDecodeError and `test_tui_look_t34`). With our 14B model running, I tried the live terminal UI and every check worked: the prompt box and status line, the spinner, live tool lines, `/tools`, `/theme`, `--plain`, `--no-color`, piped mode, and a flagged answer keeping its banner. Nothing looked wrong apart from the failing Windows CI.
### What I kept or changed
I kept the summary and the test checklist. I did not approve the PR, because its Windows CI still fails (Article IX.7); I left a comment on the PR about it.

## 2026-11-04 · Spec 003 core questions: architectural, unanswerable and design-rationale 5-8
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** eval/questions/flask-core-nicole.jsonl
- **Outcome:** Changed
### What I asked for
I asked Claude Code to draft my 20 of the 40 core evaluation questions on Flask at commit 85c5d93: 8 architectural, 8 unanswerable controls and design-rationale 5-8. They had to avoid Kelsey's topics and the 48 SWE-QA questions, use only code files as ground truth, and cite a commit for each "why" question. I then asked it to reword the questions the way a developer would ask them, draft a reference answer for each, and convert the checked set into the agreed JSONL format. After Kelsey's review of the PR, I asked it to replace two off-topic unanswerable questions with in-repo false-premise traps and to refine the sponsors answer.
### How I checked it
For each answerable question, I opened the "Where" lines in ~/flask at 85c5d93 and confirmed the code says what the answer says. For the 4 design-rationale questions, I read each commit with `git show` and checked that the reasons and quoted words match. For the 8 unanswerable questions, I ran `git grep` checks myself across the whole repo to confirm the answer isn't there. I also saw the automatic checks pass: every file, line range and commit reference was valid, the format check found 0 problems, and the questions and answers in the JSONL file matched my checked file word for word. Those checks were local scripts run during drafting; they are not in the repo yet, and the question-set check will be added test-first as a Spec 003 task (AC-1.2).
I have check that `g` in src/flask/ctx.py (class at line 29) has no `__getitem__`, that `json_body` has no match in the repo (`git grep -n json_body`), and the README Donate section (lines 38-45).
### What I kept or changed
I kept 18 questions, their developer-style wording, their tags and reference answers unchanged after checking them. After Kelsey's review I replaced unanswerable 05 (PyPI downloads) and 06 (GitHub stars) with two in-repo false-premise traps, `g['user_id']` and `request.json_body`, because off-topic questions would mostly be stopped by the evidence gate and so test the gate rather than the model. I also added to the sponsors answer that the README only has a Donate link. Architectural-08 and design-rationale-05 share evidence (sansio/app.py:59, app.py:81); I kept both because one asks what and the other why. Every question stays marked `ai_assisted: true`.

## 2026-11-05 · Spec 003 T1.1: question-set check
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/eval/questions.py, tests/eval/test_question_set_t11.py, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md, docs/specs/003-evaluation/spec.md
- **Outcome:** Changed
### What I asked for
After Kelsey's review pointed out that the "JSONL checker" in my log was not in the repo, I asked Claude Code to add it properly: a plan section and task (T1.1), tests first, then a standard-library checker for the agreed question format, with every reference checked at repo_commit. When I ran it on Windows by mistake (my Flask checkout is in WSL), it printed one confusing error per question, so I asked for a clearer error, again test-first. I also asked it to update Spec 003 so that Kelsey and I own all of it.
### How I checked it
I read the tests and the rules before approving them, saw them fail red for the missing functions, then saw 28 pass, the full suite pass (1158 in WSL), and the checker report 0 problems on our 40 questions. For the error-message fix, I approved 5 new tests after seeing them fail for the right reason; afterwards all 33 passed, the full suite passed (1163 in WSL), the checker still reported 0 problems in WSL with `--repo ~/flask`, and my earlier Windows command now prints a single "is not a git repository" error.
### What I kept or changed
Kept the plan section, the tests and the implementation. Changed the error handling after my Windows run: a `--repo` that is not a git repository now gives one clear error, a commit missing from the repository says "not in this git repository" and names the path, and a short commit asks for the full 40-character SHA. Category counts (8 per category) are left to a later task. Updated Spec 003 §14 and the related acceptance criteria so Kelsey and I own all of Spec 003, replacing the proposal's five-person split.

## 2026-11-08 · Spec 003 question set: SWE-QA conversion, tagging rule, second tagging, freeze
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** eval/questions/flask-swe-qa.jsonl, eval/questions/flask-core-kelsey.jsonl, eval/questions/tagging.md, docs/specs/003-evaluation/tagging-rule.md, docs/specs/003-evaluation/spec.md
- **Outcome:** Changed
### What I asked for
I asked Claude Code to draft review sheets for the 48 SWE-QA Flask questions (question and answer unchanged, `.py` ground truth pulled from each answer and checked at 85c5d93, a suggested tag), to draft a simple vs code-tracing tagging rule, and to make blind second-tagging sheets for Kelsey and me. After second tagging it compared our tags, drafted tagging.md with recommendations, applied the tags Kelsey and I agreed, swapped in Kelsey's replacement for core-runtime-behaviour-02, and converted the sheets to JSONL.
### How I checked it
I was responsible for checking the ground truth and tags of all 48 SWE-QA questions before they were frozen. I opened the flagged references in my Flask checkout at 85c5d93 and read the code myself rather than relying on the script's output. For #3, I found that `send_static_file` in `blueprints.py` starts at line 82, so the two short ranges the answer cited were merged into the whole method (82-102). For #37, I confirmed that `FlaskGroup.get_command` is at line 609 and that the cited lines 615-616 are the branch the question asks about. I also confirmed the file references for #5, #8 and #27, and reviewed the recommended tag for each borderline question against the written rule and agreed with them. Separately, I tagged Kelsey's 20 core questions blind, from the question and reference answer only, without opening her question file. Finally, I saw the question-set checker report 88 questions with 0 problems on the combined set.
### What I kept or changed
I kept the converted text unchanged from SWE-QA, including four dataset quirks (AC-2.1a). I changed the tagging rule after feedback (two independent lookups are simple, no retrieval-based test, history, class relationships, "why" examples) and replaced its examples, which had used real questions. Second-tagging agreement was 16/30 (53%); Kelsey and I settled all 17 disagreements. Removed test files from ground truth unless the question is about that test. Spec 003 now records one tagger for most questions and the sampled agreement (AC-3.2). After Kelsey's review: corrected AC-2.2 to 48/48 and added eval/questions/README.md with the SWE-QA source commit, licence and citation.

## 2026-11-08 · Spec 003 LLM-run plan (§3, S5) and T5.1 run details
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/003-evaluation/spec.md, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md, codecompass/eval/run_meta.py, tests/eval/test_run_meta_t51.py
- **Outcome:** Changed
### What I asked for
A plan for the LLM side of the evaluation (run details, eval config, grading subset, recording wrapper, LLM runner, grading sheet), the spec decisions for §13 C5–C9, and then T5.1: the shared `run_meta()` that both runners call to record what produced a run.
### How I checked it
moved run_meta out → importerror. put back → 21 passed. ran it on my flask → head 85c5d93 right, dirty true bc not committed, dev profile + checksum match, gpu A2000, index empty (no index there). full suite 1293 passed.
### What I kept or changed
I decided C5–C9 myself and Kelsey confirmed them: all 88 questions run in all three modes and 20 are graded, with the subset picked by `sha256(id)` rather than a seeded draw; a format slip is a G answer whose unverified markers are all `unreferenced`, and is not H1; a recording wrapper captures the full context; abstentions count in the hallucination rate. After Kelsey pointed out that AC-10.1 needs graded no-retrieval answers, we added 16 contamination rows from mode (a), so each grader has 56 rows. Changed `run_meta` from the draft to match Kelsey's plan §2.2 (reported runs use a git clone): dropped the commit fallback and added the tag, the index state and `project_dir`. The 21 tests were approved before the code was written; all pass, and the full required suite passed in WSL (1293).

## 2026-11-08 · Spec 003 T5.2 evaluation config
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** eval/codecompass.eval.toml, tests/eval/test_eval_config_t52.py, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md
- **Outcome:** Changed
### What I asked for
The committed config for every reported run (AC-5.4a): a full copy of codecompass.toml with the GPU settings, the fp16 re-ranker, `docs_fallback` stated off and the timeout from the timing run, plus tests that nothing else differs.
### How I checked it
diffed codecompass.toml vs eval config → only the header + the 5 EVAL changes (timeout 120→300, embedder/reranker cuda, reranker float16, docs_fallback false). moved the eval config out → 4 failed, 5 errors. put back → 9 passed. ran run_meta with the eval config on my flask → cuda for both models, float16, timeout 300, dev = Qwen 14B, 32768, pinned checksum, docs_fallback False. full suite on the merged branch 1321 passed.
### What I kept or changed
Kelsey ran the timing run on the cluster (5 `rag_tools` questions outside the evaluation set): the longest wait was 1.8 s, so the 300 s floor applies. She found that a copy of the user config holds only the GPU settings, so the tests now require the full `[generator]` section and the `dev` profile. While writing the tests, Claude found that `load_online_config()` returns the defaults for a missing path, so one test passed with no file; it now checks the file exists first, and I asked Kelsey to check the config path in her retrieval runner. Plan §3.5 now says the runner loads the models once, because loading them per question took about 15 of the 20 s.

## 2026-11-08 · Spec 003 T5.3 grading subset
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/eval/subset.py, tests/eval/test_subset_t53.py, eval/questions/grading-subset.json, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md
- **Outcome:** Changed
### What I asked for
The rule that picks the 20 questions graded by hand (4 per category; 2 core and 2 SWE-QA with one of each tag; 4 core unanswerable), ordered by `sha256(id)` so nobody chooses them, a command that writes `eval/questions/grading-subset.json`, and tests that the committed file is what the rule gives.
### How I checked it
moved subset.py out → 1 error (module missing). put back → 13 passed.
### What I kept or changed
I chose `sha256(id)` over a seeded random draw because it has no seed that could be re-tried. While implementing, Claude found that one approved test hashed the question files' raw bytes, which differ between my Windows checkout (CRLF) and a Linux clone (LF); I approved changing that one line so the hash is taken with line endings normalised to LF, and the plan now says so. The subset file was generated once, before any LLM run, and gives 8 `simple`, 8 `code-tracing` and 4 unanswerable questions.

## 2026-11-08 · Spec 003 T5.4 recording generator
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/eval/recording.py, tests/eval/test_recording_t54.py
- **Outcome:** Kept
### What I asked for
A wrapper passed to `ask(generator=...)` that passes every call to the real generator and keeps a copy of each message list and each output, so graders see the full context the model saw, including full tool results (§13 C8), with no change to Spec 002 code.
### How I checked it
moved recording.py out → ModuleNotFoundError. put back → 11 passed (read through the 11 test names). ran ask() on the fixture repo with the wrapper → 1 call recorded, system + user messages sent, raw output kept with its Sources section, outcome F.
### What I kept or changed
Kept the design from plan §3.4. The wrapper passes `on_text` only when it is given, because the harness also calls `generate(messages)` without it, and it records deep copies because the harness keeps appending to its message list. The tests run `ask()` on the fixture repo with and without the wrapper and check the answer and outcome are the same.

## 2026-11-08 · Spec 003 T5.5 LLM runner
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/eval/llm_run.py, tests/eval/test_llm_run_t55.py, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md
- **Outcome:** Changed
### What I asked for
The runner that sends every question through `ask()` in one mode (`no_retrieval`, `rag` or `rag_tools`): checks before any question, models created once, a fresh recording wrapper per question, one retry, the results file rewritten after each question, `--resume`, `--reported`, and a command line.
### How I checked it
moved llm_run.py out → ImportError. put back → 23 passed, read through the test names: results fields, all 3 modes, models reused with a fresh recorder per question, retry once then record the error, file rewritten after each question, resume, stops before any question on a wrong HEAD/index/question set/config/mode, --reported refuses a dirty tree, CLI. I have also ran the runner on my flask clone (85c5d93) with no llama-server → stopped with "could not read llama-server … Connection refused", exit code 1, nothing written to /tmp/llm-test.
### What I kept or changed
The runner loads the config from `--config` itself, so the config recorded is the one that ran, and a missing file stops the run. Each question also records the mode it ran in and whether the round limit was hit. Three approved tests were wrong and I approved changing them: the test stub copies a retrieved chunk's header, so it crashes in `no_retrieval` (the runner correctly recorded that as an error), and in `rag` an ignored tool request is logged rather than run, so the test now checks that no tool ran and that the ignored request is recorded. The runner code did not change for these.

## 2026-11-08 · Spec 003 T5.6 automatic labels and grading sheet
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/eval/grading.py, tests/eval/test_grading_t56.py, docs/specs/003-evaluation/spec.md, docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md
- **Outcome:** Changed
### What I asked for
The automatic labels (abstention, format slip, H1, strict H1), citation accuracy and per-run counts, and the blind grading sheet: a CSV with empty grader columns, one Markdown file per row with the full context, and a key file, for the 20 subset questions in `rag` and `rag_tools` plus the 16 answerable ones in `no_retrieval`.
### How I checked it
moved grading.py out → ImportError. put back → 26 passed (read the test names). opened R01.md from an end-to-end run (runner in 3 modes → grading sheet) → question, reference answer and citations, system answer with Sources, citation check outcome F with the source verified, full context. noticed the system prompt listed the tools, which gives away the mode → asked for it to be left out; saw the new test fail first, then 27 passed.
### What I kept or changed
I decided that an answer citing nothing that is not an abstention is labelled `uncited`, not H1, because nothing was fabricated (Article VI.3); graders judge its claims under H2. This is now in AC-7.2. The sheet refuses results in the wrong slot or from runs under different conditions, skips errored answers and lists them in the key, and reads `.json.gz` in case a results file has to be compressed (Kelsey's size note). When I opened a row file, its system prompt listed the tools, which gave away the configuration; I chose to leave the system prompt out of the row files (one more test, written first). Tool results in `rag_tools` rows can still reveal it, and the report will state this.

## 2026-11-09 · Spec 003 report figures: plan §4, T6.1 merge and agreement, T6.2 figures
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/003-evaluation/plan.md, docs/specs/003-evaluation/tasks.md, codecompass/eval/report.py, tests/eval/test_report_merge_t61.py, tests/eval/test_report_figures_t62.py
- **Outcome:** Changed
### What I asked for
Plan §4 and two commands for the afternoon: `report merge` (combine my and Kelsey's graded copies, check every value, measure agreement, pre-fill the final columns where we agree) and `report figures` (hallucination rate, Verification Gain, quality, the paired comparison, contamination, citation accuracy, latency and hit rate, each with its n, read from the settled sheet and the key).
### How I checked it
T6.1: report.py missing → ImportError; put back → 21 passed (read the test names). ran report merge on a 4-row example: R01 scores 2 vs 1 → final empty to settle; R02/R03 agree → final filled; R04 both 0 but reasons differ → final score 0, final reason empty; agreement.json: score 3/4, H2 3/3, H3 1/1, reason 0/1, kappa score 0.64 and H2 1.0, disagreements R01 and R04.
T6.2: saw the red output in Claude's message (19 failed: report has no figures), since it shares a module with T6.1 and can't be re-checked by moving the file; then 19 passed (read the test names).
I have also ran the full suite myself in WSL: 1476 passed, 0 failed.
After normalising the line endings and merging main (incl. #52), I ran the full suite again myself in WSL: 1500 passed, 0 failed.
### What I kept or changed
Before any results existed I fixed three rules in plan §4.4: the contamination flag at a difference of 0.5 or more, agreement as % for every field plus Cohen's kappa for the score and H2, and unanswerable questions counted in the overall hallucination rate and as their own group. Each grader's columns are taken only from their own copy, and the final values are filled only where we agree, so disagreements are settled by us and not averaged. The key is read only by `figures`, after grading. Claude also ran the whole chain end to end on the fixture repo (runner, grading sheet, merge, figures) to check the real file shapes fit together.
