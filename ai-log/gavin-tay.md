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
