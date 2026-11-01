# Plan 005: GPU inference on an 8 GB card

**Implements:** Spec 005 | **Constitution:** v1.4.0

## 1. Design

- `RerankerConfig` (online/config.py) gets `dtype: str = "float32"` and a `__post_init__` that rejects unknown values (AC-1.1) and `float16` on a device that does not start with `cuda` (AC-1.2). Both loaders build `RerankerConfig(**section)`, so both accept it with no further change (AC-1.4).
- `BgeReranker._load` (online/retrieval/reranker.py) passes `model_kwargs={"dtype": cfg.dtype}` to `CrossEncoder` only when the dtype is not `float32`, so the default call is byte-for-byte what it is today (AC-1.3). The string form is accepted by transformers, so the module still imports no torch.
- `ask()` adds `log["reranker"] = {model, revision, device, dtype}` next to the existing profile fields (AC-1.5).
- `codecompass.toml` gets the `dev-7b-gpu` profile (AC-2.1). Its numbers come from the budget arithmetic: 8192 context, 1024 answer tokens, about 2300 tokens reserved for three tool rounds and about 430 for the prompt leaves about 4400 tokens for chunks (at least 5 of 512, AC-2.2). `launch_command` already appends `server_args`, so the printed start command (AC-2.3) needs no code.

## 2. Memory budget (measured, 8 GiB card, about 0.9 GiB used by the desktop)

| Component | GPU memory |
|---|---|
| `llama-server`, 7B Q4_K_M, 8192 context, q8 cache, all layers | about 4.6 GiB (5.5 GiB in `nvidia-smi` including the desktop) |
| fp16 re-ranker | 1.6 GiB peak |
| fp32 re-ranker | 3.2 GiB peak (does not fit) |
| embedder on the GPU | about 0.7 GiB (to be measured in the full run) |

## 3. Test layers

| Layer | Tests |
|---|---|
| Unit | config validation, both loaders, layering; `BgeReranker` load arguments with a fake `CrossEncoder`; the audit log field |
| Profile | the real `codecompass.toml`: fields, checksum equal to `dev-7b`, budget check, start command |
| Model (`-m model`, CUDA only) | fp16 re-ranker ranks the relevant chunk first |
