# Dev model setup (local notes)

Record of what was installed and configured to run the CodeCompass generator
(Qwen2.5-Coder-14B-Instruct via llama.cpp `llama-server`) on one development
machine. Constitution references: Article VIII.1 (all model settings in
config), VIII.2 (llama.cpp only, pinned GGUF, localhost), VIII.4 (switchable
profiles).

- **Date:** 2026-10-21
- **Machine:** Apple M3, 16 GiB unified memory, macOS 27.0.1 (arm64)
- **Scope:** local setup only. No application code, tests, specs, or docs were
  modified. The only repo changes are `codecompass.toml` and this file, both
  committed on 2026-10-26.

## 1. Model artifact

| | |
|---|---|
| Model | Qwen2.5-Coder-14B-Instruct (the `dev` profile) |
| Source repo | `Qwen/Qwen2.5-Coder-14B-Instruct-GGUF` |
| File | `qwen2.5-coder-14b-instruct-q4_k_m.gguf` |
| Quantisation | `Q4_K_M` |
| Size | 8,988,110,272 bytes (8.36 GiB) |
| SHA-256 | `c1e659736d89ac1065fb495330fb824d94001974a4bfa78e7270e43476a8d940` |
| Location | `~/.cache/codecompass/models/` (outside the repo; `*.gguf` is gitignored) |

Downloaded with the Hugging Face CLI:

```bash
mkdir -p ~/.cache/codecompass/models
hf download Qwen/Qwen2.5-Coder-14B-Instruct-GGUF \
  qwen2.5-coder-14b-instruct-q4_k_m.gguf \
  --local-dir ~/.cache/codecompass/models
```

Integrity check: the computed SHA-256 and the byte count both match the values
Hugging Face records for that file (LFS oid), so the download is complete and
not a truncated resume.

## 2. Inference runtime

| | |
|---|---|
| Package | `llama.cpp` 0.7.0 (Homebrew bottle) |
| Build | 11669, commit `620d2225c` |
| Compiler | AppleClang 21.0.0.21000334, Darwin arm64 |
| Binary | `/opt/homebrew/bin/llama-server` |

```bash
brew install llama.cpp
llama-server --version
```

GitHub releases for v0.7.0 do not ship prebuilt macOS binaries (only
`nightly-tag.txt`), so Homebrew or a source build is the install route.

Note: llama.cpp 0.7.0 changed `llama-server`'s default port to **9931**. The
project default is `http://127.0.0.1:8080`, so `--port 8080` must be passed
explicitly.

## 3. Configuration

`codecompass.toml` in the repo root records the pinned artifact and defines
two 14B profiles that share the same GGUF file and checksum:

| Profile | Context | For |
|---|---|---|
| `dev` (default) | 32768 | machines with enough memory; matches `plan.md` |
| `dev-lowmem` | 8192 | 16 GiB machines like this one (see §5) |

Select the low-memory profile with `GENERATOR_PROFILE=dev-lowmem`. The default
stays `dev` (Article VIII.4). Both load through the real loader
(`load_online_config` + `get_generator_profile`): `dev` resolves to 32768,
`dev-lowmem` to 8192, and `prod` keeps its built-in defaults. The `-c` value
passed to `llama-server` must match the selected profile's `context_window`.

Nothing reads `gguf_file` / `gguf_checksum` yet — `LlamaServerGenerator` is
not implemented, and the GGUF path is passed to `llama-server` on the command
line.

## 4. Running it

Start (own terminal, leave running). This is the `dev-lowmem` command; for
`dev`, pass `-c 32768` instead:

```bash
llama-server \
  -m ~/.cache/codecompass/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 8080 -c 8192 --jinja
```

`--host 127.0.0.1` is required (Article VIII.2, localhost only). `--jinja` is
the default in 0.7.0 and is accepted for clarity; it enables the ChatML template
shipped in the GGUF.

Verify:

```bash
curl -s http://127.0.0.1:8080/health          # {"status":"ok"}
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hi"}],"max_tokens":32}'
```

Stop with `Ctrl-C`, or `pkill -f llama-server`.

Server lifecycle is **manual** in Sprint 2 (spec C9): nothing in the repo starts
or stops the server.

## 5. Measured behaviour and known limitations

Verified working: model loads, `/health` returns ok, the OpenAI-compatible chat
endpoint answers correctly through the model's ChatML template, and
`finish_reason` / stop-token handling behaves as expected. Example:

> "The Python built-in `enumerate()` function adds a counter to an iterable and
> returns it as an enumerate object…" — 45 completion tokens, `finish_reason: stop`

Two things were found the hard way:

1. **16384 context does not fit this machine.** Weights (8.4 GiB) plus a 16k f16
   KV cache (~3 GiB) plus Metal buffers exceeded GPU memory; llama.cpp reported
   `ggml_metal_synchronize: error: command buffer 0 failed with status 5 /
   Insufficient Memory (kIOGPUCommandBufferCallbackErrorOutOfMemory)` and
   prefill fell back to processor speed. A 9k-token prompt had not finished
   prefill after ~170 s (≈37 tok/s), and the request was cancelled. At 32768 the
   KV cache alone would be ~6 GiB, so it cannot fit either.
2. **Prefill is slow even at 8192** on this machine: ~38 tok/s, e.g. a
   2,636-token prompt took ~70 s before the first token. GPU layers are assigned
   to `MTL0`, so this is not an obvious "no GPU offload" case; the cause was not
   isolated. Candidate factors: unified-memory pressure on a 16 GiB machine,
   `llama-server`'s default of 4 slots with a unified KV cache, and llama.cpp
   0.7.0 Metal behaviour.

This does **not** block current work: the required test suite runs on
`StubGenerator` with no server, GPU, or model download (Article IX.7). It will
matter when `LlamaServerGenerator` and real end-to-end queries are built. Open
options at that point: quantised KV cache (`--cache-type-k q8_0`), `-np 1`,
partial GPU offload, a smaller quant, or a machine with more memory. Changing
the pinned dev model itself is an Article VII.5 model change, not a local tweak.

## 6. Follow-ups (not done)

- `codecompass.toml` is committed with the dev pins. The `prod` (32B) profile
  still has no pinned GGUF file or SHA-256, which Article VIII.2 requires before
  any reported result; record them when the 32B is downloaded.
- When T7.1 lands, profiles gain `backend`, `server_args` and `seed`; add them
  here.
- `.gitignore` comments claim a sample `codecompass.toml` is committed; it is
  not. Same for `codecompass.local.toml` / `config.local.toml`, which are
  ignored but never loaded by any code.
- `LlamaServerGenerator` (plan D13) is unwritten, so none of this is exercised
  by the pipeline yet.
- The `dev-lowmem` profile and the measured prefill rate should be
  stated in the PR that implements the generator task (Article IX.7).
