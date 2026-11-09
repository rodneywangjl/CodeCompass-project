# Short Reflection on AI Usage for the Project

| | |
|---|---|
| **Name** | Nicole Goh |
| **Date written** | 2026-11-09 |
| **AI use log** | [`ai-log/nicole-goh.md`](../../../ai-log/nicole-goh.md) |

---

## 1. What did you learn about how to use these tools effectively?

Putting the rules into Markdown files (the constitution, AGENTS.md, the specs and my own CLAUDE.local.md) gave the AI context that carried over between sessions. The files also became a shared point of reference: both the AI and I could check a decision against the same written source, instead of relying on what either of us remembered. I didn't have to re-explain the test-first workflow, which files I owned, or the evaluation rules each time. When it drifted, I could point it back to a specific line instead of arguing with it. It also worked best when I gave it one small task with a clear acceptance criterion.

## 2. Where were the tools strong, and where were they weak?

**Strong**

- Refactoring, organising files and documents, and repetitive steps. For example, it converted the 48 SWE-QA questions into our question format, with the ground-truth files pulled from each answer. It also ran a format check on my 56-row grading sheet (valid values, `n/a` cells, a reason for every 0) without scoring anything. And it updated nine presentation slides, checking every figure against the report file.

**Weak**

- It sometimes fixed the wrong thing, and it didn't check its own work. When we first read the official report figures, it explained that the strict hallucination gain "mostly disappears" with tools, and treated that as a real finding. The number didn't make sense to me, so I traced it. The report was counting answers we had settled as abstentions as format slips. I had the bug fixed test-first, and the corrected strict rate fell from 75% to 50% with tools, a gain of 25 points. The AI had explained a wrong number instead of questioning it.

## 3. What went wrong, and what would you do differently?

**What went wrong**

- **Code that passed its tests but failed on a real file:** the AI-written grading merge passed all its tests. Kelsey's review of #53 found that a sheet saved from Excel as "CSV UTF-8" starts with a hidden byte-order mark, which would have broken the merge. The tests only used files the AI had made itself, so they never covered this. It was fixed test-first before the official merge.
- **Unchecked claim:** the first draft of our team AI declaration said every pull request was reviewed. Checking GitHub showed that 11 PRs were merged by their own author with no recorded review, so the claim had to be rewritten.

**What I would do differently**

- Ask the AI to show its evidence (test output, a recount, a link to the source) before I accept a result, and check important numbers myself.
- Treat a surprising result as a possible bug before writing it up.
- Test with real inputs as well as made-up ones, for example a sheet exported from Excel, not just a file the AI generated.
