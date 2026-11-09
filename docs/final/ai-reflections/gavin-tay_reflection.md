# Short Reflection on AI Usage for the Project

| | |
|---|---|
| **Name** | Gavin Tay |
| **Date written** | 2026-11-10 |
| **AI use log** | [`ai-log/gavin-tay.md`](../../../ai-log/gavin-tay.md) |

---

## 1. What did you learn about how to use these tools effectively?

A passing test suite is not the same as a working fix. In T19.1 and T21.1 the real model never took the path the fix covered, so I forced the tool call or called the tool directly and read its output. That turned out to be the most reliable check.

Keeping tasks narrow also helped. In T21.2 I fixed only the structural part of a guardrail: repo text containing `</tool_result>` could end a tool-result block early and pass as text from outside it.

## 2. Where were the tools strong, and where were they weak?

**Strong**

- Small fixes with a clear cause, such as `fit_chunks` stopping at the first oversized chunk (T19.2), `open_file` ignoring the indexer's exclude list (T21.1) and Windows paths breaking TOML in the T12.3 tests.

**Weak**

- Anything that depends on how the model behaves. Tests can check a prompt's wording, not how the model reacts to it. In T13.2 the 14B wrote `Sources` as a numbered list, which the citation checker rejects.
- Real-model checks were slow: one CPU run took about 30 minutes.

## 3. What went wrong, and what would you do differently?

### Changes to the plan or approved tests

- **Sources format (T8.5):** changed the system prompt to show a literal `Sources` block, with plan D14 and the approved T8.5 test.
- **Windows CLI tests (T12.3):** wrote fixture paths with `as_posix()`; the assertions are unchanged.
- **Tool-use prompt (T20.1):** made the tool decision rule 1 of the prompt and updated the T8.5 test again.
- **Chunk budget (T19.2):** updated plan D4 so a chunk that does not fit is skipped.

### What went wrong

- **Real-model runs that missed the fix:** in T19.1 and T21.1 the answers looked fine, but the fixed code never ran. I only noticed by reading the tool calls and audit log.
- **A prompt fix that only partly worked:** after T20.1 the model called a tool on B2, but it chose `search_again` instead of `git_log`, and the answer was still circular and uncited.
- **Windows-only failures:** the T12.3 TOML paths, a test that failed because my home folder is a git repository, a `UnicodeEncodeError` and a flaky TUI test. Each time I had to rule out my own change first.

### What I would do differently

- Ask the AI to show its evidence, such as the test output, the audit log or what the model actually received, and verify it myself before I accept the change.
- Force real-model checks down the code path being fixed, or test the component directly.
- Treat prompt-only fixes as partial until they are measured on the evaluation set.
- Log Windows-specific failures as bug tasks when they first appear.
