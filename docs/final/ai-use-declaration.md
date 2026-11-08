# AI Use Declaration: SE201 G1-T1 (CodeCompass), final submission

**Status:** DRAFT. Last updated 2026-11-08 by Nicole Goh, from the `ai-log/` files on `main` at `ce4d98b`. Final submission is due Tue 10 Nov 2026, 12:00.

Format follows SE201 AI Use Disclosure Policy v1.00, §5.1: a short declaration, **one per team**, that summarises the AI use logs and states which tools were used, for what purpose, and how their output was checked. The checkpoint version is in `docs/checkpoint/ai-use-declaration.md`. Everything after the declaration is working notes, not part of the submission.

## Declaration (to paste into the final report)

We used AI coding assistants throughout the project, mostly Claude Code. All five members used Claude Code with claude-opus-5-5, and Rodney also used claude-sonnet-5-5. We used it to draft specs, plans and task lists, to write tests and then the code for the online query pipeline (Spec 002), the terminal interface (Spec 004) and GPU support (Spec 005), to review pull requests, to draft constitution amendments, and to draft evaluation material (Spec 003). Swen used Claude Code with claude-haiku-5-5 for the SCIS GPU cluster notebook and three pipeline fixes. Kelsey and Swen used Antigravity (Gemini 3.8 Flash) for the first online package skeleton, early planning and guidelines, and the documentation fallback (T22.1, T22.2), which was then reviewed with Claude Code. Nicole used Claude in the Claude app (claude-opus-5-5) to draft the project context and the first evaluation definitions.

We checked the output in four ways. For code, we read the tests and ran them to confirm they failed before any code was written; afterwards we ran the task's tests and the full required suite (`pytest -m "not model"`) and confirmed they passed, on Windows, WSL or macOS. Several changes were also tried against a real 7B or 14B model through `llama-server`, locally or on the SCIS GPU cluster. Spec and constitution text was compared against the constitution, and constitution amendments drafted by AI were applied by hand, one edit at a time. Every evaluation reference answer and ground-truth line range was checked by hand against the Flask source at commit `85c5d93`; questions drafted with AI help are marked `ai_assisted` in the question files, and a sample of the complexity tags was tagged a second time, blind, by another member. Commits containing AI-assisted work carry an `Assisted-by` or `Co-Authored-By` trailer, and each use is recorded in the `ai-log` folder (114 entries).

> TODO before submitting (delete this box):
> - Rodney's 57 entries all have "How I checked it" as `TODO`. The code-checking sentence above is confirmed only for Gavin, Kelsey, Nicole and Swen. Confirm it holds for Rodney once he fills them in, or reword it.
> - Ask Rodney whether AI was used for Sprint 1 (Spec 001, 4 Oct). Those commits have no trailer and no log entry. If it was used, it must be logged and named here (policy §6).
> - Update the entry count and the `main` commit just before the deadline.

## Working notes (not submitted)

### Log status by member (on `main` at `ce4d98b`)

| Member | Entries | Tools (models) logged | Main purposes | How checked (from the log) | Missing |
|---|---|---|---|---|---|
| Rodney Wang | 57 (26 Oct to 2 Nov) | Claude Code (claude-opus-5-5, claude-sonnet-5-5) | Spec 002 tasks S0, S1, S5, S6, S9 (stubs, RRF, tools, citation checker); constitution 1.2.1 and 1.3.0; Spec 004 terminal UI; Spec 005 GPU support; chunker, evidence gate and unreferenced-sources fixes | **Not written:** all 57 are `TODO` | All 57 "How I checked it" sections; Sprint 1 question above |
| Kelsey (La Hue Van) | 24 | Antigravity (Gemini 3.8 Flash); Claude Code (claude-opus-5-5) | T0.1; generator (T7) and agent loop (T8); constitution 1.4.0; `open_file` and `search_again` (T14); T17, T18 fixes; 20 core evaluation questions; docs fallback (T22) | Tests reviewed and run red first, then task tests and the full suite green (Windows and WSL); constitution edits applied by hand; questions checked against the code | None |
| Swen Teo | 8 | Antigravity (Gemini 3.8 Flash); Claude Code (claude-opus-5-5, claude-haiku-5-5) | Spec 002 planning; AGENTS.md guidelines; hybrid retrieval, re-ranking and context budgeting (T2.3, T2.4, T3.2, T4.2); GPU cluster notebook; T11.1, T19.3, T19.4 fixes | Cross-checked against the constitution; ran the notebook on the cluster (GPU vs CPU re-ranker); full suite on macOS (1,174 passed) | 1 `TODO`: 2026-11-07 "Repeated tool calls are not run again (T19.4)" |
| Gavin Tay | 6 | Claude Code (claude-opus-5-5) | Real re-ranker and model smoke tests (T13); T12.3 Windows test fix; T19.1, T19.2, T20.1, T21.1 | Task tests and the full suite (1,130 passed); real-model runs with `ask` on the `dev-7b` profile | None |
| Nicole Goh | 19 | Claude app (claude-opus-5-5); Claude Code (claude-opus-5-5) | Project context; AI log and declarations; Spec 002 block 4 (T9.6, T10, T11, T12: `ask()`, audit log, CLI, evaluation modes); PR reviews; Spec 003 question set, checker (T1.1), SWE-QA conversion and tagging | Tests run red then green, full suite in WSL; references checked by hand at `85c5d93`; blind second tagging; checker reports 88 questions, 0 problems | 1 line for the 8 Nov entry, not yet committed |

### Commit trailers (`main`, merge commits excluded)

Most AI-assisted commits carry a trailer. Commits without one are not necessarily a problem (for example, hand edits and merges of others' work), but each member should check their own:

| Git author | Commits | With trailer | Without |
|---|---|---|---|
| rodneywangjl | 171 | 74 | 97 (all from early October, mostly Sprint 1) |
| rw (Rodney) | 90 | 87 | 3 |
| Hue Van La / La-Hue-Van (Kelsey) | 58 | 36 | 22 |
| swen-teo | 30 | 22 | 8 |
| gavintay03 | 23 | 15 | 8 |
| nicole | 31 | 30 | 1 |

### Still needed for the final submission (policy §5)

- [ ] Rodney: fill in his 57 "How I checked it" sections, and answer the Sprint 1 question.
- [ ] Swen: fill in the T19.4 "How I checked it" section.
- [ ] Each member: a §5.2 **reflection** (what they learned, where the tools were strong and weak, what went wrong, what they would do differently). Nicole collects them.
- [ ] Each member: add log entries for any work after this date (including Spec 003 evaluation work).
- [ ] Nicole: rebuild the declaration from `ai-log/` just before the deadline and delete the TODO box.

### Policy checklist (v1.00)

- **§4.2 log format:** heading with date and title; Tool (model), Files and Outcome fields; What I asked for, How I checked it, and What I kept or changed sections. Outcome is one of Kept, Changed or Rejected.
- **§4.1 commit trailers:** `Assisted-by: <tool> (<model>)`, or the tool's own `Co-Authored-By:` line.
- **§5 final deliverables:** the `ai-log` folder, a team declaration, and a §5.2 reflection from **each member**.
- **§6:** undisclosed AI use is treated as a breach of academic integrity; disclosed use is not penalised.
