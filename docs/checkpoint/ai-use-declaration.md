# AI Use Declaration: SE201 G1-T1 (CodeCompass)

**Status:** DRAFT for the checkpoint (due 2026-10-18, 23:59). Last updated 2026-10-07 by Nicole Goh. Kept as a record of the checkpoint; the final submission uses `docs/final/ai-use-declaration.md`.

Format follows SE201 AI Use Disclosure Policy v1.00, §5.1: a short declaration, **one per team**, placed **in the checkpoint document**, that summarises the AI use logs and states which tools were used, for what purpose, and how their output was checked. Copy the declaration below into the checkpoint document. Everything after it is working notes for keeping it accurate, not part of the submission.

## Declaration (to paste into the checkpoint document)

We used Antigravity (Gemini 3.8 Flash) to analyse the online query pipeline spec (Spec 002) and plan the citation-verification and output-routing work, to draft the AI-use and commit-trailer guidelines in AGENTS.md, and to implement, test first, the online package skeleton, config loader and data models (Spec 002 task T0.1). The planning and guidelines were checked against the project constitution and the Spec 002 task dependencies; for the T0.1 code, the new tests were confirmed to fail before implementation, and afterwards they and the full required suite (143 tests) passed. We used Claude (claude-opus-5-5) in the Claude app to draft our project context and the evaluation rules and definitions in AGENTS.md §4.3, and Claude Code (claude-opus-5-5) to verify that setup, review §4.3 against the constitution and Spec 002, and draft AI-log and declaration material; this output was checked by reviewing every diff and the git status and ignore checks before committing, and by comparing the evaluation rules against the constitution and Spec 002. TODO: add a clause for each of Rodney and Gavin once their logs have entries. Details are recorded in the ai-log folder.

> TODO before submitting:
> - Rebuild the paragraph from `ai-log/` just before the deadline, so it covers only what the logs say.
> - Add a sentence on team-wide review or testing (as in the policy's example) only if it is true for every logged use.
> - Remove all TODO text.

## Working notes (not submitted)

### Log status by member

| Member | Log file | Entries | Tools (models) logged | Purpose | How checked (from the log) |
|---|---|---|---|---|---|
| Rodney Wang | `ai-log/rodney-wang.md` | 0 | No entries yet | No entries yet | No entries yet |
| Gavin Tay | `ai-log/gavin-tay.md` | 0 | No entries yet | No entries yet | No entries yet |
| Kelsey (La Hue Van) | `ai-log/kelsey.md` | 1 | Antigravity (Gemini 3.8 Flash) | Spec 002 T0.1: online package skeleton, config loader and data models, with tests | Confirmed the new tests failed first (`ModuleNotFoundError`); then all 9 T0.1 tests and the full required suite (`pytest -m "not model"`, 143 tests) passed with no regressions |
| Swen Teo | `ai-log/swen.md` | 2 | Antigravity (Gemini 3.8 Flash) | Spec 002 planning for citation verification and output routing; AGENTS.md §4.1–4.2 and own log | Cross-referenced against constitution Articles VI and IX and the Spec 002 task dependencies; checked the trailer format and log structure |
| Nicole Goh | `ai-log/nicole-goh.md` | 2 | Claude app (claude-opus-5-5); Claude Code (claude-opus-5-5) | Project context and evaluation definitions (AGENTS.md §4.3, .gitignore, local Claude Code context); setup verification, review of §4.3 and its open questions, AI log, starter logs, this declaration | Reviewed diffs; `git status`, `git diff` and `git check-ignore` checks; compared §4.3 against the constitution and Spec 002; reviewed the log and diffs before committing |

### Policy checklist (v1.00)

- **§4.2 log format:** heading with date and title; Tool (model), Files and Outcome fields; What I asked for, How I checked it, and What I kept or changed sections. Outcome is one of Kept, Changed or Rejected.
- **§4.1 commit trailers:** `Assisted-by: <tool> (<model>)`, or the tool's own `Co-Authored-By:` line. As of 2026-10-07, `git log` shows trailers on:
  - `18d525f` (Swen): `Assisted-by: Antigravity (Gemini 3.8 Flash)`
  - `53aa4f1` (Kelsey, T0.1): `Assisted-by: Antigravity (Gemini 3.8 Flash)`
  - `eea1007`, `e762913`, `1b963e9` (Nicole): `Assisted-by: Claude (claude-opus-5-5)` and/or `Assisted-by: Claude Code (claude-opus-5-5)`
- **§5 checkpoint:** the `ai-log` folder to date, in the repository, plus this declaration in the checkpoint document.
- **§5 final deliverables:** the `ai-log` folder, a team declaration, and a §5.2 reflection from **each member** (what they learned, where the tools were strong and weak, what went wrong and what they would do differently).
- **§6:** undisclosed AI use is treated as a breach of academic integrity; disclosed use is not penalised.
