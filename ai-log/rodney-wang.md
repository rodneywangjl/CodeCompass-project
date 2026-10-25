# AI Use Log: Rodney Wang

## 2026-10-26 · Review of local dev model setup
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
A check of my uncommitted dev model setup: the `codecompass.toml` generator profile and the `MODEL-SETUP.md` notes on running Qwen2.5-Coder-14B through llama.cpp `llama-server`.
### How I checked it
TODO (member)
### What I kept or changed
Kept the pinned GGUF file, checksum and server settings. The AI confirmed the config loads through `load_online_config`, the SHA-256 and file size match the downloaded model, the llama.cpp version and default port match `llama-server`, and `pytest -m "not model"` stays green (143 passed). Fixed three wording errors in `MODEL-SETUP.md`: the C9 reference points to the spec, not the plan; the scope line names both untracked files; the config comment says a profile table must set `model_id`.

## 2026-10-26 · Low-memory generator profile
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass.toml, MODEL-SETUP.md
- **Outcome:** Changed
### What I asked for
A separate generator profile for machines with 16 GiB of memory, instead of lowering the shared `dev` context to 8192.
### How I checked it
TODO (member)
### What I kept or changed
Kept a new `dev-lowmem` profile: the same pinned 14B GGUF with an 8192 context, selected with `GENERATOR_PROFILE=dev-lowmem`. Put `dev` back to the 32768 context in `plan.md` and left `dev` as the default (Article VIII.4). Did not add a profile for machines below 16 GiB: the smallest 14B file is 5.4 GiB, and a 7B model would need a constitution amendment (Article VIII.1).

## 2026-10-26 · Spec 002 design review and fixes
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** docs/specs/002-online-retrieval/spec.md, docs/specs/002-online-retrieval/plan.md, docs/specs/002-online-retrieval/tasks.md
- **Outcome:** Changed
### What I asked for
A review of the constitution, specs and plans for soundness and efficiency, then fixes to spec, plan and tasks 002 on a docs branch before any more online tasks are built.
### How I checked it
TODO (member)
### What I kept or changed
Kept the AI's fixes for citation checking (cited lines must lie inside retrieved chunks, not just overlap them), the round limit (one final answer-only call after the third tool round), context budgeting that reserves room for tool output and counts tokens with the generator's tokenizer, `git blame --porcelain` and a 0x1F-separated `git log` format so commit metadata parses exactly, simpler path validation, and a `/props` check that the running server matches the profile. Did not let it decide three points that need the team: removing the round limit and tool list from config (changes the approved T0.1 test), how the query embedder is reached through the offline public API, and how an uncited "could not determine" answer is shown. These are marked [NEEDS CLARIFICATION]. Kept the one-task, tests-approved-first workflow for the remaining tasks instead of building the rest of the pipeline in one pass.

## 2026-10-26 · T0.2 History fixture repo
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** tests/support/fixture_repo.py, tests/online/test_fixture_repo_t02.py
- **Outcome:** Kept
### What I asked for
T0.2: a fixture repo with meaningful commit messages, known authors and dates, so the verifier-tool tests can assert exact `git log` and `git blame` output. I gave advance approval for the tests instead of reviewing them before implementation; they are reviewed in the PR.
### How I checked it
TODO (member)
### What I kept or changed
Kept a separate `build_history_repo` rather than adding commits to the Sprint 1 fixture, which rewrites its own history and is relied on by the offline tests. The history includes an author name with a space and a subject with a comma (for the 0x1F log format in plan D7) and a final "wip" commit for the no-rationale case (Article V.5). Fixed dates and identities make the shas identical on every build.
