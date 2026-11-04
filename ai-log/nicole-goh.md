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

