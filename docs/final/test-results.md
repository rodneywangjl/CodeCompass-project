# Test results (final submission)

The required test suite on `main`, run before the final submission.

| | |
|---|---|
| **Commit** | `main` at `0518a82` |
| **Command** | `pytest -m "not model" -q` |
| **Result** | **1502 passed**, 10 deselected, 0 failed, 0 skipped, 0 xfail, 3 warnings |
| **Time** | 103.74 s |
| **Machine** | WSL (Ubuntu 26.04), Python 3.14, run by Nicole Goh on 2026-11-09 |

Last lines of the output:

```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1502 passed, 10 deselected, 3 warnings in 103.74s (0:01:43)
```

## What this run covers

- **The required suite** (constitution Article IX.7) is deterministic and needs no GPU, `llama-server`, model download or network access. It uses the stub embedder, generator and re-ranker in `tests/support/`, and the fixture repositories.
- **The 10 deselected tests** are marked `model`: they need a real model and are not required for merge. They were not run here. Swen ran the model tests on the SCIS GPU cluster with the `dev` (14B) profile (10 passed, recorded in `ai-log/swen.md`).
- **The 3 warnings** are deprecation warnings from libraries (one is `huggingface_hub`'s `hf_xet.download_files()`), not test failures.

## CI

GitHub Actions was blocked from 4 Nov (billing), so CI did not run on later pull requests. For each of those, the required suite was run locally in WSL instead and the result was recorded in the PR.
