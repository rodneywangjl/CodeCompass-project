# AI Use Declaration: SE201 G1-T1 (CodeCompass), final submission

**Status:** Final. Last updated 2026-11-10 by Nicole Goh, from the `ai-log/` files on `main` at `7d2fdff`, plus the architecture-diagram entry (135 entries). Final submission is due Tue 10 Nov 2026, 12:00.

Format follows SE201 AI Use Disclosure Policy v1.00, §5.1: a short declaration, **one per team**, that summarises the AI use logs and states which tools were used, for what purpose, and how their output was checked. The checkpoint version is in `docs/checkpoint/ai-use-declaration.md`. Each member's §5.2 reflection is in `docs/final/ai-reflections/`. Everything after the declaration is working notes, not part of the submission.

## Declaration (to paste into the final report)

We used AI coding assistants throughout the project, mostly Claude Code. All five members used Claude Code with claude-opus-5-5 to draft specs, plans and task lists; to write tests and then the code for the online query pipeline (Spec 002), the terminal interface (Spec 004), GPU support (Spec 005) and the evaluation harness (Spec 003); to review pull requests; and to draft constitution amendments, evaluation material and documentation. Rodney also used claude-sonnet-5-5 for the terminal interface, GPU support and several pipeline fixes. At the start of the project, Rodney used the Claude chat interface (claude-sonnet-5-5) to draft the constitution, AGENTS.md and the Spec 001 documents, and OpenCode for the Sprint 1 offline indexing pipeline (Spec 001): Space Bunny, a stealth model whose provider and version are not known, wrote the tests first, and Muse Spark v1.6 (free tier) wrote the code against them. Swen used Claude Code with claude-haiku-5-5 for the SCIS GPU cluster notebook and five pipeline fixes (T11.1, T19.3 to T19.6). Kelsey and Swen used Antigravity (Gemini 3.8 Flash) for the first online package skeleton, early planning and guidelines, the documentation fallback (T22.1, T22.2) and the retrieval-evaluation runner (T4.2), each then reviewed with Claude Code. Nicole used Claude in the Claude app (claude-opus-5-5) to draft the project context and the first evaluation definitions.

We checked the output in five ways. For code, we read the tests and ran them to confirm they failed before any code was written; afterwards we ran the task's tests and the full required suite (`pytest -m "not model"`) and confirmed they passed, on Windows, WSL, macOS or the SCIS GPU cluster. Sprint 1 (Spec 001) was checked less closely: its commits put each test before its code, but Rodney read those tests only roughly and ran them once the code was in, and he skimmed the AI-drafted constitution and AGENTS.md rather than reviewing every line. Many changes were also tried against a real 7B or 14B model through `llama-server`, locally or on the cluster. Spec and constitution text was compared against the constitution, and constitution amendments drafted by AI were applied by hand, one edit at a time. All 88 evaluation questions are marked `ai_assisted`, and every reference answer and ground-truth line range was checked by hand against the Flask source at commit `85c5d93`; the complexity tags of the other member's core questions were tagged a second time, blind. No evaluation answer was graded by AI: two members graded the 56 rows independently and settled disagreements in writing, and AI was used only to check the sheets' format. Most pull requests were reviewed or merged by a second member; 11 were merged by their own author with no recorded review, one of which (#52) was reviewed after the merge. Commits containing AI-assisted work carry an `Assisted-by` or `Co-Authored-By` trailer, except Rodney's 97 Sprint 1 commits (4 Oct), whose AI use is disclosed in his log instead. Each use is recorded in the `ai-log` folder (135 entries).

## Working notes (not submitted)

### Log status by member (on `main` at `2719f46`)

| Member | Entries | Tools (models) logged | Main purposes | How checked (from the log) | Missing |
|---|---|---|---|---|---|
| Rodney Wang | 59 (project start, then 26 Oct to 2 Nov) | Claude chat interface (claude-sonnet-5-5); OpenCode (Space Bunny, stealth model; Muse Spark v1.6); Claude Code (claude-opus-5-5, claude-sonnet-5-5) | Constitution, AGENTS.md and Spec 001 docs; Sprint 1 offline indexing pipeline (tests by Space Bunny, code by Muse Spark); Spec 002 tasks S0, S1, S5, S6, S9 (stubs, RRF, tools, citation checker); constitution 1.2.1 and 1.3.0; Spec 004 terminal UI; Spec 005 GPU support; chunker, evidence gate and unreferenced-sources fixes | Spec 002, 004 and 005 tasks: tests run red then green; edge cases tried by hand (rejected paths, `git log` parsing, fixture rebuilt twice); terminal UI checked in a real terminal; final manual reviews light given the volume. Constitution, AGENTS.md and Sprint 1: skimmed, tests read breifly and run after the code | None (reflection done) |
| Kelsey (La Hue Van) | 26 (7 Oct to 9 Nov) | Antigravity (Gemini 3.8 Flash); Claude Code (claude-opus-5-5) | T0.1; generator (T7) and agent loop (T8); constitution 1.4.0; `open_file` and `search_again` (T14); T17, T18 fixes; 20 core evaluation questions; docs fallback (T22); Spec 003 retrieval ablations (T4.1, T4.2); official evaluation runs and experiments; grading | Tests reviewed and run red first, then task tests and the full suite green (Windows and WSL); Antigravity's tests read by hand; constitution edits applied by hand; questions checked against the code; cluster outputs checked against tag, commit, config hash and row counts | None (reflection done) |
| Swen Teo | 11 (7 Oct to 9 Nov) | Antigravity (Gemini 3.8 Flash); Claude Code (claude-opus-5-5, claude-haiku-5-5) | Spec 002 planning; AGENTS.md guidelines; hybrid retrieval, re-ranking and context budgeting (T2.3, T2.4, T3.2, T4.2); GPU cluster notebook and guide; T11.1, T19.3 to T19.6 | Cross-checked against the constitution; ran the notebook on the cluster; task tests and the full suite on macOS (1,174 passed) and the cluster (1,460 passed); real long-line and prompt-flag checks on the cluster | None (reflection done) |
| Gavin Tay | 7 (28 Oct to 8 Nov) | Claude Code (claude-opus-5-5) | Real re-ranker and model smoke tests (T13); T12.3 Windows test fix; T19.1, T19.2, T20.1, T21.1; injection guard (T21.2) | Task tests and the full suite (1,130 passed); real-model runs with `ask` on the `dev-7b` profile; direct harness check of the injection guard | None (reflection done) |
| Nicole Goh | 32 (7 Oct to 10 Nov) | Claude app (claude-opus-5-5); Claude Code (claude-opus-5-5) | Project context; AI log and declarations; Spec 002 block 4 (T9.6, T10, T11, T12: `ask()`, audit log, CLI, evaluation modes); PR reviews; Spec 003 spec, question set, checker (T1.1), SWE-QA conversion and tagging, LLM runner (T5.1 to T5.6), report figures (T6.1, T6.2), grading support (format checks only), strict-rate fix | Tests run red then green, full suite in WSL (1,502 passed); references checked by hand at `85c5d93`; blind second tagging; checker reports 88 questions, 0 problems; graded by hand | None (reflection done) |

### Commit trailers (`main`, merge commits excluded, at `2719f46`)

Most AI-assisted commits carry a trailer. Commits without one are not necessarily a problem (for example, hand edits and merges of others' work), but each member should check their own:

| Git author | Commits | With trailer | Without |
|---|---|---|---|
| rodneywangjl | 171 | 74 | 97 (all on 4 Oct, Sprint 1; AI use disclosed in his log) |
| rw (Rodney) | 91 | 87 | 4 |
| Hue Van La / La-Hue-Van (Kelsey) | 76 | 53 | 23 |
| swen-teo | 44 | 32 | 12 |
| gavintay03 | 29 | 18 | 11 |
| nicole | 71 | 69 | 2 |

### Pull requests merged by their own author with no recorded review

#1, #2, #3, #13, #14, #18, #20, #39, #41, #42, #52 (#52 was reviewed after the merge). From `gh pr list --state merged` at `2719f46` (unchanged since `b04894b`).

### Still needed for the final submission (policy §5)

- [x] Swen: fill in the T19.4 "How I checked it" section.
- [x] Rodney: fill in his "How I checked it" sections and answer the Sprint 1 question (PR #66).
- [x] Each member: a §5.2 **reflection** in `docs/final/ai-reflections/<member>_reflection.md`. Done: all five (Kelsey #64, Gavin #65, Rodney #66).
- [ ] Each member: add log entries for any work after this date.
- [x] Nicole: rebuild the declaration from `ai-log/` just before the deadline and delete the TODO box.

### Policy checklist (v1.00)

- **§4.2 log format:** heading with date and title; Tool (model), Files and Outcome fields; What I asked for, How I checked it, and What I kept or changed sections. Outcome is one of Kept, Changed or Rejected.
- **§4.1 commit trailers:** `Assisted-by: <tool> (<model>)`, or the tool's own `Co-Authored-By:` line.
- **§5 final deliverables:** the `ai-log` folder, a team declaration, and a §5.2 reflection from **each member**.
- **§6:** undisclosed AI use is treated as a breach of academic integrity; disclosed use is not penalised.
