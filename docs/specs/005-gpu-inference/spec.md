# Spec 005: Running the 7B generator and the re-ranker together on one 8 GB GPU

**Project:** CodeCompass (SE201 G1-T1) | **Status:** Implemented (T3.1 to T3.3); measured end to end 2026-11-01
**Constitution version:** 1.4.0 | **Constitution articles touched:** VII.3, VII.5, VIII.1, VIII.2, VIII.4, VIII.5, IX, XI

## 1. Purpose

On a development laptop with an 8 GB GPU, the 7B generator on `llama-server` and the cross-encoder re-ranker do not both fit as the project stands. Measured (RTX 3070 Ti, llama.cpp b11960 with CUDA 13.4, Qwen2.5-Coder-7B-Instruct Q4_K_M):

| Setup | Per question (retrieval + re-rank + generate) |
|---|---|
| CPU-only `llama-server`, re-ranker on GPU (fp32) | about 100 s (generation 85 to 99 s) |
| GPU `llama-server`, re-ranker on CPU | about 55 s (re-rank 52 s) |
| GPU `llama-server` (8192 context, q8 cache) + fp32 re-ranker on GPU | does not fit: out of memory |
| GPU `llama-server` (8192 context, q8 cache, all 29 layers) + fp16 re-ranker | works for one question, then **out of memory** on the second (about 180 MiB free) |
| the same with **26 layers** on the GPU and `-ub 256`, fp16 re-ranker on GPU, embedder on CPU | **about 5 s per question** (re-rank 0.7 s, generation about 4 s); six repeated re-ranks pass with about 400 MiB to spare |

The generator alone is 27x to 40x faster on the GPU build (prompt 3,951 tok/s, generation 102 tok/s). The fp16 re-ranker peaks at 1.6 GiB against 3.2 GiB for fp32, and on three test questions it kept the same top-8 set, with the same order on two and a swap of near-ties on the third (score difference under 0.0005).

This spec adds the two things that make the last row possible and nothing else.

## 2. Scope

**In scope**
- A `[reranker] dtype` setting (`float32` default, or `float16`).
- A `dev-7b-gpu` generator profile and the `llama-server` flags it needs.
- Recording the new setting in the per-query audit log, and the `llama.cpp` build in the profile.
- README: how to install the GPU build and what fits.

**Out of scope**
- Changing the default behaviour of any existing profile or config (defaults are unchanged).
- Quantising the re-ranker below fp16, `bfloat16`, or changing the embedder's precision.
- Choosing a different re-ranker, generator, or `llama.cpp` version for everyone. The b11960 build is a local, documented choice (Article VIII.2).
- Any evaluation results (Article VII.1: no evaluation set exists yet, so nothing is tuned or reported).

## 3. User stories and acceptance criteria

### US1 (P1): Choose the re-ranker's precision

- **AC-1.1** `[reranker] dtype` accepts `"float32"` (default) or `"float16"`. Any other value fails at config load with an error that lists the allowed values (Article VIII.1; fail loudly).
- **AC-1.2** `float16` with a CPU device (`cpu`, `cpu:0`, any case) fails at config load with an error saying it needs a GPU device and naming `cuda` and `mps`. Any other device is accepted, so the code assumes no particular GPU API (Article VIII.2). `float32` works on any device.
- **AC-1.3** With the default `float32` the model is loaded exactly as before (no extra load argument). With `float16` the cross-encoder is loaded in half precision, at the same pinned model and revision.
- **AC-1.4** Both config loaders (`load_online_config` and `load_online_config_layers`) accept the setting, and layering merges it like any other key.
- **AC-1.5** Every per-query audit log records the re-ranker model, revision, device and dtype in force (Article VII.3, VII.5).
- **AC-1.6** A model-marked test confirms that on a CUDA machine the fp16 re-ranker still ranks a clearly relevant chunk above an irrelevant one.

### US2 (P1): A profile that fits next to the re-ranker

- **AC-2.1** `codecompass.toml` defines `dev-7b-gpu`: the same model id family, GGUF file and SHA-256 as `dev-7b`, `context_window = 8192`, `max_tokens = 1024`, and `server_args` for `-ngl 26`, `-ub 256` and the q8 key/value cache. (First written as `-ngl 99`; measurement showed that runs out of memory, see section 1.)
- **AC-2.2** The profile passes the start-up budget check (Article V.1) with the default tool settings and leaves room for at least 5 retrieved chunks of 512 tokens.
- **AC-2.3** The warning shown when `llama-server` is down prints a start command for this profile that includes `-c 8192` and all of its `server_args`.
- **AC-2.4** The profile comment records the `llama.cpp` build used (b11960, `0.8.0-dev`, commit `8642541b2`) and marks results from this profile as development signals only (Article VIII.5).

### US4 (P1): Works on Linux, Windows and macOS (Article VIII.2)

The GPU work above was measured only on Linux with an NVIDIA card. The constitution requires the project to run on Linux, Windows and macOS with the GPU API chosen per machine and CPU-only always possible. The code must not stand in the way, and the documentation must say what is and is not tested.

- **AC-4.1** The precision setting does not depend on CUDA (AC-1.2): Apple's `mps` works.
- **AC-4.2** The start command printed when `llama-server` is down is quoted for the platform: Windows quoting on Windows, POSIX quoting elsewhere, with a placeholder path in the platform's own style.
- **AC-4.3** On Windows the terminal is switched to understand ANSI escape sequences before anything is printed, so the dimmed draft and status line do not show as stray characters.
- **AC-4.4** On every platform, writing to stdout or stderr never fails because the terminal's encoding cannot represent a character (`⚠`, `│`, `─`, `…`): unrepresentable characters are replaced.
- **AC-4.5** The user-level config file is looked up in `%APPDATA%\codecompass\codecompass.toml` on Windows (falling back to `~/.config/codecompass/`), and in `$XDG_CONFIG_HOME` or `~/.config` elsewhere. This amends Spec 004 AC-1.13 for Windows only.
- **AC-4.6** CI runs the required suite on Ubuntu, Windows and macOS, so a platform bug fails a pull request. The required suite stays model-free and network-free.
- **AC-4.7** The README says, per platform, which `llama.cpp` build to use, what was tested, and what was not.

### US3 (P2): Documentation

- **AC-3.1** The README gives the NVIDIA-on-Linux GPU install steps (download the b11960 CUDA 13.4 archives, check their SHA-256, extract, copy the CUDA runtime next to the binaries), the start command, the measurements above, and which combinations do not fit.

## 4. Constitution check

| Article | How this spec respects it |
|---|---|
| VII.3, VII.5 | The dtype is recorded in every query log. Changing it is a pipeline change: no evaluation set exists yet, so there is nothing to re-run now, but any later evaluation must record it. |
| VIII.1 | Model, revision and device stay configuration; the pinned revision is untouched. |
| VIII.2 | The `llama.cpp` build is recorded; server flags live in the profile; only the generator wrapper talks to the server. |
| VIII.4, VIII.5 | A new named profile, no code change to switch; marked as a 7B development profile, not mixable with 14B results. |
| XI.1 | No new component or dependency. |
| VIII.2 *(US4)* | No GPU API is assumed in code; the GPU API is chosen per machine in the profile's launch settings; CPU-only keeps working. |

## 5. Decisions

| # | Question | Notes |
|---|---|---|
| Q1 | Is a swap of near-tied chunks in the top 8 acceptable for the fp16 re-ranker? | It happened on one of three questions with a score difference under 0.0005. It is opt-in (`float32` stays the default) and recorded in the log. |
| Q2 | **RESOLVED.** Where should the embedder run? | On the CPU at query time. With it on the GPU too the total peaked at 7.8 GiB and a question ran out of memory. To index a new repository quickly, run once with the embedder on `cuda` and the server stopped. It is a setting, not code. |
