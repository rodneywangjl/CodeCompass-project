# Tasks 005: GPU inference on an 8 GB card

**Implements:** Plan 005 / Spec 005. Same rules as Tasks 002 (tests first, red, then code; test commit before the implementation commit; never weaken an approved test).

**T3.1 Re-ranker precision setting**
- Tests first: default is `float32`; `float16` + `cuda` loads from both loaders and merges across layers; an unknown value and `float16` on CPU fail with clear messages; `BgeReranker` passes no extra load argument for `float32` and `model_kwargs={"dtype": "float16"}` for `float16`; `ask()` records model, revision, device and dtype in the audit log; one model-marked CUDA test.
- ACs: AC-1.1 to AC-1.6. | Touches: `online/config.py`, `online/retrieval/reranker.py`, `online/__init__.py`, `tests/online/test_reranker_dtype_t31.py`. | Depends on: none.

**T3.2 The `dev-7b-gpu` profile**
- Tests first (against the real `codecompass.toml`): the fields and the checksum equal to `dev-7b`; the budget check passes and leaves room for 5 chunks of 512 tokens; the printed start command contains `-c 8192` and every server flag.
- ACs: AC-2.1 to AC-2.4. | Touches: `codecompass.toml`, `tests/online/test_gpu_profile_t32.py`. | Depends on: none.

**T3.3 Docs, user config and a real run**
- README section; update the user-level config; run the TUI against the GPU server and record the measured per-question time and peak GPU memory in the AI log.
- ACs: AC-3.1. | Touches: `README.md`, `ai-log/`. | Depends on: T3.1, T3.2.
