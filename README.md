# CodeCompass

CodeCompass is a RAG-based Q&A assistant that helps developers understand an unfamiliar git repository. It retrieves real code and commit history, verifies claims with git tooling, and answers with citations that are checked before they are shown.

This repository implements both pipelines. The **offline indexing pipeline** (Spec 001) turns a git repository into two searchable, mutually consistent indexes: a semantic vector index (Chroma/HNSW) and a keyword index (tantivy BM25). The **online query pipeline** (Spec 002) answers questions from them: hybrid retrieval, cross-encoder re-ranking, a local generator (Qwen2.5-Coder via llama-server), a bounded `git blame`/`git log` verifier loop, and a deterministic citation checker.

> Grounding over fluency: if the evidence is insufficient, CodeCompass says what it could not determine rather than guessing. See [`docs/constitution.md`](docs/constitution.md).

---

## Table of contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [User guide](#user-guide)
  - [1. Build or update the index](#1-build-or-update-the-index)
  - [2. Check index status](#2-check-index-status)
  - [3. Verify index consistency](#3-verify-index-consistency)
  - [4. Use the Python API](#4-use-the-python-api)
  - [5. Configure CodeCompass](#5-configure-codecompass)
  - [6. Ask a question](#6-ask-a-question)
  - [7. Interactive mode (`codecompass`)](#7-interactive-mode-codecompass)
- [How indexing works](#how-indexing-works)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Development process](#development-process)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Reference](#reference)

---

## Architecture

```
Git repository
  → Repo scanner (tree-sitter + GitPython, changed files only)
    → Code-aware embedder (jina-embeddings-v2-base-code, local)
      → Vector store (Chroma/HNSW)
    → Keyword index (BM25, tantivy)
```

One pipeline, one code path: **a full build is an incremental run from an empty index**. Before answering each question, the online pipeline will call the single public `ensure_current` entry point, which compares repo HEAD against the last indexed commit and runs an incremental re-index only if they differ.

Module boundaries are strict: only `codecompass.offline`'s `ensure_current` (write-capable), `status`, `open_index`, and `check_consistency` (read-only) are visible to the online pipeline.

---

## Requirements

- Python 3.11+
- Git
- macOS, Linux, or Windows
- No GPU, paid service, or network access required for the core path (indexing and the required test suite run fully locally)

---

## Installation

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

All dependencies are pinned in [`requirements.txt`](requirements.txt). The embedder model revision is pinned (`jinaai/jina-embeddings-v2-base-code @ 516f4baf…`, see `codecompass/offline/config.py`). Do not add `mlx-lm` or MLX — generator inference uses llama.cpp only (online pipeline).

---

## Quickstart

```bash
# 1. Build the index for a repository (first run; downloads ~600MB model once)
.venv/bin/python -m codecompass.offline.cli index /path/to/repo

# 2. Check whether the index is current
.venv/bin/python -m codecompass.offline.cli status /path/to/repo

# 3. Verify both indexes agree
.venv/bin/python -m codecompass.offline.cli check /path/to/repo

# 4. After new commits, just re-run index (only changed files are processed)
.venv/bin/python -m codecompass.offline.cli index /path/to/repo
```

For a fast, model-free trial (uses a deterministic stub embedder, no download):

```bash
.venv/bin/python -m codecompass.offline.cli index /path/to/repo --embedder stub
.venv/bin/python -m codecompass.offline.cli check /path/to/repo --embedder stub
```

### Clone-to-running with `quickstart.py`

`quickstart.py` runs all of the above for you in order: create `.venv` → install `requirements.txt` → `index` → `status` → `check` → `pytest -m "not model"`. It contains no indexing logic itself; it just calls the backend in `codecompass/offline/`.

```bash
# From the project root. <repo> is any git repo you want to search
# (not necessarily this repo). HEAD is indexed; uncommitted edits are ignored.
python quickstart.py /path/to/repo --embedder stub   # fast trial, no download (default)
python quickstart.py /path/to/repo --embedder code    # real search, downloads ~600MB model once

# Options:
#   --skip-install   skip `pip install -r requirements.txt`
#   --skip-tests     skip `pytest -m "not model"`
```

What each step does:

1. `index <repo>` — first run indexes everything at HEAD; later runs only process added/modified/deleted files. Each chunk is saved twice: as a vector in Chroma (`idx/vector`) and as BM25 text in tantivy (`idx/keyword`).
2. `status <repo>` — shows if the index is `current`/`stale`/`empty` and which commit was indexed.
3. `check <repo>` — verifies both stores hold the same chunk ids (`consistent: True (N chunks agree)`), catching partial writes.
4. `pytest -m "not model"` — fast test suite using the stub embedder; skips `model` tests that need the real download.

`stub` = fake 8-number vectors for testing (instant). `code` = real `jina-embeddings-v2-base-code` vectors (768 numbers) for real meaning search.

---

## User guide

All commands share the form:

```
python -m codecompass.offline.cli <command> <repo> [--index-dir DIR] [--config FILE]
```

- `<repo>` — path to the git repository to index (HEAD commit content is indexed; uncommitted edits are ignored).
- `--index-dir` — override where index data is stored. Default is the OS application-data directory (`~/Library/Application Support/codecompass` on macOS, `$XDG_DATA_HOME/codecompass` on Linux, `%LOCALAPPDATA%\codecompass` on Windows), in a subfolder keyed by repository. The index is never stored inside the repo itself.
- `--config` — path to a `codecompass.toml` file (see [Configure](#5-configure-codecompass)).

Exit codes: `0` on success, `1` on failure or inconsistency (error printed to stderr).

### 1. Build or update the index

```bash
# Incremental run (normal use): builds if empty, otherwise processes only changed files
python -m codecompass.offline.cli index /path/to/repo

# Force a full rebuild from scratch
python -m codecompass.offline.cli index /path/to/repo --full

# Preview what would change without writing anything
python -m codecompass.offline.cli index /path/to/repo --dry-run

# Use the stub embedder (no model download; for tests and smoke checks)
python -m codecompass.offline.cli index /path/to/repo --embedder stub
```

Each run prints a human-readable report and saves a machine-readable copy under `<index_dir>/runs/<timestamp>.json`. The report includes: mode (`full`, `incremental`, `up-to-date`, `rebuild`), from/to commits, files added/modified/deleted/renamed/skipped/fallback-chunked, chunks added and removed, embedder and schema versions, and per-stage timings.

What gets indexed:

- **Indexed:** source files at HEAD in configured extensions (Python, JavaScript/TypeScript/TSX/JSX, Java get structure-aware chunking; other configured source languages use a line-window fallback).
- **Skipped and counted:** secrets (`.env*`, private keys, certificates), lockfiles, build/dependency directories, minified bundles, binaries (detected by content), files over the size limit, git-ignored files, and non-code files (markdown, text, JSON/YAML config).
- **Never read from disk:** file content comes from the git object database, so untracked files and uncommitted edits can never leak in.

### 2. Check index status

```bash
python -m codecompass.offline.cli status /path/to/repo
```

Output:

```
state: current | stale | empty
head: <HEAD sha>
indexed: <last indexed sha>
embedder: <model>@<revision> dim <N> (schema <V>)
```

- `empty` — never built. `current` — indexed commit equals HEAD. `stale` — new commits exist; re-run `index`.
- Read-only: makes no writes.

### 3. Verify index consistency

```bash
python -m codecompass.offline.cli check /path/to/repo
# with stub-built indexes:
python -m codecompass.offline.cli check /path/to/repo --embedder stub
```

Compares the vector store and keyword index chunk-id sets (including per-path agreement). Prints `consistent: True (N chunks agree)` and exits `0`, or lists `vector-only` / `keyword-only` ids and exits `1`.

### 4. Use the Python API

Only four names are public to the online pipeline (`codecompass/offline/__init__.py`). `ensure_current` is the single write-capable entry; the rest are read-only.

```python
from codecompass.offline import ensure_current, status, open_index, check_consistency
from codecompass.offline.config import load_config

config = load_config("codecompass.toml")  # or load_config(None) for defaults

# Before answering a question: cheap no-op when already current
result = ensure_current("/path/to/repo", config=config)
if result.ok:
    print(result.status)   # "current"
    print(result.report)   # RunReport (mode, commits, counts, timings)
else:
    # result.status is "failed" or "locked"; existing index is still usable
    # Online pipeline answers from it and flags the answer as stale.
    print(result.status, result.message)

# Read-only status
st = status("/path/to/repo", config=config)
print(st.state)  # "empty" | "current" | "stale"

# Read-only index handles (refuses mismatched embedder or schema with a typed error)
handles = open_index("/path/to/repo", config=config)
try:
    ids = handles.vector.ids()
    hits = handles.keyword.search("get_user_by_id", limit=10)
    result = check_consistency(handles.vector, handles.keyword)
    assert result.ok
finally:
    handles.close()
```

By default `ensure_current` lazily loads the real code embedder from config. Tests pass an explicit stub or factory instead:

```python
from tests.support.stub_embedder import StubEmbedder
result = ensure_current("/path/to/repo", config=config, embedder=StubEmbedder())
```

### 5. Configure CodeCompass

All model names, thresholds, sizes, and paths come from configuration, never hard-coded. Create a `codecompass.toml` (all sections optional; missing keys use defaults):

```toml
[index]
dir = "./.codecompass-index"      # default: OS app-data dir

[chunking]
target_tokens = 512               # target chunk size (embedder tokenizer)
hard_max_tokens = 8192            # never exceed embedder input limit
batch_files = 50

[files]
max_file_bytes = 1048576
source_extensions = [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]
exclude_patterns = [".env*", "*.pem", "*.min.js"]
exclude_dirs = ["node_modules", "__pycache__", ".venv", "build", "dist"]

[languages]
treesitter = ["python", "javascript", "typescript", "tsx", "java"]

[embedder]
model = "jinaai/jina-embeddings-v2-base-code"
revision = "516f4baf13dec4ddddda8631e019b5737c8bc250"
dimension = 768
device = "cpu"
batch_size = 32

[lock]
timeout_seconds = 120
```

Notes:

- Unknown sections or keys are rejected. `target_tokens > hard_max_tokens` is rejected.
- Relative `index.dir` resolves against the config file's directory.
- Changing exclusion rules takes effect on the next run; newly excluded paths have their chunks removed from both indexes. Changing chunking settings triggers re-chunking (vectors reused where chunk text is unchanged).
- The embedder identity (model, revision, dimension) is recorded in index metadata; opening or writing with a different one fails with a clear error. The schema version is gated the same way.

---

### 6. Ask a question

Start `llama-server` with the generator for your profile (see [`MODEL-SETUP.md`](MODEL-SETUP.md); on a 16 GB machine use the `dev-lowmem` profile), then:

```bash
GENERATOR_PROFILE=dev-lowmem python -m codecompass.online.cli ask /path/to/repo "Why does login retry?"
python -m codecompass.online.cli ask /path/to/repo "Where is the token refreshed?" --verbose
```

The index is brought up to date before each question. The answer ends with a `Sources` section, and every entry is checked against the evidence the model was shown:

- **Verified (F):** every citation was found in the retrieved code or the git history the model read.
- **Flagged (G):** a warning banner, with `[UNVERIFIED]` on each source to check by hand.
- **Uncited parts** are marked `(not cited)`. An answer with no citations at all carries a note to verify it against the source.

"Verified" means the cited code was in front of the model, not that the claim is true. Each question writes a JSON audit log under `<index dir>/queries/` (or `[logging] query_log_dir`). From Python:

```python
from codecompass.online import ask
from codecompass.online.config import load_online_config

result = ask("/path/to/repo", "Why does login retry?", config=load_online_config("codecompass.toml"))
print(result.answer, result.citation_outcome, result.audit_log["log_file"])
```

### 7. Interactive mode (`codecompass`)

A small prompt loop over the same pipeline, so you do not retype a long command for each question. Install the command once (needs network to fetch the pinned build backend), then run it inside any git repository:

```bash
.venv/bin/pip install -e .      # once; adds `codecompass` to the venv
cd /path/to/repo                # the repo root or any folder inside it
codecompass                     # or: codecompass /path/to/repo
```

```
> Why does authenticate retry on timeout?
...answer, then a Sources section...
> /exit
```

- **Repo root:** found with `git rev-parse --show-toplevel`, so it is the same from the root or a subfolder. Every index, retrieval and git-tool call uses that root.
- **Config files are layered.** Built-in defaults, then your user-level file `~/.config/codecompass/codecompass.toml` (or `$XDG_CONFIG_HOME/codecompass/`), then `<repo root>/codecompass.toml` on top. A key the repo file sets wins; keys it leaves out keep your value; a `[generator.profiles.NAME]` table replaces the whole profile of that name. `--config PATH` uses only that file, and a path that does not exist is an error. The startup banner lists every file used, repo file first. Put personal choices (for example `default_profile = "dev-7b"` and the GPU settings below) in the user-level file and they apply in every repo; a repo's own `default_profile` still wins where it sets one.
- **Options:** `--profile NAME` (else `GENERATOR_PROFILE`, else the config default), `--config PATH`, `--index-dir DIR`, `--no-draft`.
- **Output:** only the answer goes to stdout, exactly as `ask()` returns it, so a flagged answer always shows its banner and `[UNVERIFIED]` marks. The prompt, a "Thinking…" line, the startup banner, warnings and errors go to stderr, and only on a terminal. Piped input works: `codecompass < questions.txt > answers.txt`.
- **Keys:** `/exit`, `/quit` or Ctrl-D to leave. Ctrl-C at the prompt prints a hint; Ctrl-C during a question abandons it and returns to the prompt. A failed question prints `error: ...` and the session carries on.
- **Generator:** the command never starts `llama-server`. If it is not running, or does not match the profile, you get a warning with the start command and the session still opens.
- **Models:** the generator, re-ranker and embedder are created once per session and reused. Each question is independent (there is no conversation memory).
- **Warm-up:** on a terminal, as soon as the session opens, a background thread brings the index current and loads the models while you type. A question asked before it finishes shows `Preparing index and models…` and waits; one asked afterwards starts at once. Piped input does not warm up, and `/exit` never waits for it.
- **Watching the model write (unchecked draft):** on a terminal, the model's text appears on stderr as it is written, under `⚠ DRAFT — NOT CHECKED. The model is still writing. Do not rely on this text.`, every line starting with `draft │ ` and dimmed. When the answer is ready you see `Draft finished after N s.` and `── Checked answer (replaces the draft above) ──`, and only then does the **checked** answer go to stdout. The draft is never on stdout, has not been through the citation check, and may contain citations that the check will flag. Turn it off with `--no-draft`; it is also off when stderr is not a terminal. Control characters in the draft are removed.

#### Running fast on a GPU

The project runs on Linux, Windows and macOS, with the GPU API chosen per machine and CPU-only always possible (constitution Article VIII.2). What has actually been **tested** is narrower:

| Platform | `llama-server` build (release b11960) | Embedder / re-ranker device | Status |
|---|---|---|---|
| Linux + NVIDIA | `llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz` + `cudart-llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz` | `cuda` | **Tested** (numbers below, RTX 3070 Ti 8 GB) |
| Windows + NVIDIA | `llama-b11960-bin-win-cuda-13.4-x64.zip` + `cudart-llama-bin-win-cuda-13.4-x64.zip` | `cuda` | Not tested on a real machine; see "Windows" below |
| macOS (Apple Silicon or Intel) | `llama-b11960-bin-macos-arm64.tar.gz` / `-x64.tar.gz` (Metal), or `brew install llama.cpp` | `mps` | Not tested on a real machine; see "macOS" below |
| AMD / Intel GPU | the `vulkan` builds (Linux and Windows) | `cpu` (the pinned PyTorch has no ROCm or XPU build) | Not tested |
| CPU only, any OS | any build, or `win-cpu-x64` | `cpu` | Works everywhere, slow: re-ranking one shortlist took 52 s here |

The test suite that CI runs (`pytest -m "not model"`) runs on Ubuntu, Windows and macOS, so platform bugs in the Python code show up in pull requests. CI does not run a model, so it proves nothing about GPU speed or memory. **If you run this on Windows or macOS, please record what you measured** (the commands under "Platform check" below) and open a pull request with the results.

Measured on Linux with an RTX 3070 Ti (8 GB), this repository and the 7B model, one question end to end:

| Setup | Per question |
|---|---|
| CPU-only `llama-server` (the Arch `llama-cpp` package), re-ranker on GPU | about 100 s |
| GPU `llama-server`, re-ranker on CPU | about 55 s |
| GPU `llama-server` and the fp32 re-ranker together | out of memory |
| **GPU `llama-server` (26 layers) and the fp16 re-ranker** (`dev-7b-gpu`) | **5 to 12 s** (re-rank 0.7 s, generation 4 to 11 s) |

The embedder alone is 27x faster on the GPU (73 s to 2.7 s for 192 chunks), and the fp16 re-ranker takes 0.64 s against 52 s on the CPU. The three components do not all fit in 8 GB, so this setup puts the **embedder on the CPU** (at query time it embeds one short question) and the re-ranker on the GPU in half precision.

**1. Install a GPU `llama-server` (Linux + NVIDIA, tested)** (the Arch package has no GPU backend; `llama-server --list-devices` shows none). Official build b11960, CUDA 13.4, no `sudo` needed:

```bash
mkdir -p ~/.local/opt/llama.cpp/download && cd ~/.local/opt/llama.cpp/download
for f in llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz cudart-llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz; do
  curl -L --fail -C - -O "https://github.com/ggml-org/llama.cpp/releases/download/b11960/$f"; done
sha256sum *.tar.gz     # must equal the two values in the comment above [generator.profiles.dev-7b-gpu]
mkdir -p ../b11960-cuda-13.4 && for f in *.tar.gz; do tar -xzf "$f" -C ../b11960-cuda-13.4; done
cp ../b11960-cuda-13.4/cudart-*/*.so* ../b11960-cuda-13.4/llama-b11960/
../b11960-cuda-13.4/llama-b11960/llama-server --list-devices      # should list your GPU
```

Check the size and checksum before extracting: a download can stop early and still report success.

**2. Personal settings** in `~/.config/codecompass/codecompass.toml`:

```toml
[generator]
default_profile = "dev-7b-gpu"     # a repo's own default_profile still wins; use --profile dev-7b-gpu there

[reranker]
device = "cuda"
dtype = "float16"                  # half precision: 1.6 GiB peak instead of 3.2 GiB

[embedder]
device = "cpu"                     # with the embedder on the GPU too, the total ran out of memory
```

**3. Start the server and ask.** The warning that `codecompass` prints when the server is down gives this command with your path filled in:

```bash
~/.local/opt/llama.cpp/b11960-cuda-13.4/llama-b11960/llama-server \
  -m ~/.cache/codecompass/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 8080 -c 8192 -ngl 26 -ub 256 --cache-type-k q8_0 --cache-type-v q8_0
codecompass --profile dev-7b-gpu
```

**Windows + NVIDIA (not tested).** Same idea in PowerShell. The settings file goes in `%APPDATA%\codecompass\codecompass.toml` (the old `~\.config\codecompass` location is also read if `%APPDATA%` is not set):

```powershell
$d = "$env:LOCALAPPDATA\llama.cpp\b11960-cuda"; New-Item -ItemType Directory -Force $d | Out-Null; Set-Location $d
$base = "https://github.com/ggml-org/llama.cpp/releases/download/b11960"
foreach ($f in "llama-b11960-bin-win-cuda-13.4-x64.zip","cudart-llama-bin-win-cuda-13.4-x64.zip") {
  Invoke-WebRequest "$base/$f" -OutFile $f; "$f  $((Get-FileHash $f -Algorithm SHA256).Hash)" }
# expected SHA-256:
#   llama-b11960-bin-win-cuda-13.4-x64.zip     31c75ea62b80f0816c855ea783ef68757bc2d48028edaa57d904e4982bddea4a
#   cudart-llama-bin-win-cuda-13.4-x64.zip     738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668
# extract BOTH into this same folder so the CUDA DLLs sit next to llama-server.exe
Expand-Archive llama-b11960-bin-win-cuda-13.4-x64.zip -DestinationPath . -Force
Expand-Archive cudart-llama-bin-win-cuda-13.4-x64.zip -DestinationPath . -Force
.\llama-server.exe --list-devices
```

Then use the same `[reranker]`, `[embedder]` and `dev-7b-gpu` settings and start command as on Linux (the warning `codecompass` prints is quoted for Windows). The `-ngl 26 -ub 256` numbers were measured on an 8 GB card only. For Vulkan (any GPU) use `llama-b11960-bin-win-vulkan-x64.zip` (SHA-256 `bac6914b5e83523eb008c6789eaa12669f93fbc196c3b9e8237b6672323b33e9`); for CPU only, `llama-b11960-bin-win-cpu-x64.zip` (`73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287`).

**macOS (not tested).** The Metal build offloads to the Apple GPU by default and uses unified memory, so there is no separate GPU memory to split: `brew install llama.cpp`, or download `llama-b11960-bin-macos-arm64.tar.gz` (SHA-256 `58e5a5e1d7c2bf66cedd9c29e0323f3e570660a70a1e2156d32eed08f4cc1e3c`; the Intel build is `-x64`, `d1e6c9dd…f1da5`). Start it as `MODEL-SETUP.md` describes, with the context your RAM allows (`dev-lowmem` for the 14B on 16 GB, or `dev-7b`). In your settings use `[reranker] device = "mps"` and `dtype = "float16"` if you want the faster re-ranker, and `[embedder] device = "mps"`. `MODEL-SETUP.md` records that on a 16 GB M3 the 14B at a 16k context ran out of memory and prefill was slow; those limits are unchanged.

**Platform check.** On a new machine, run these and note the results in the pull request: `pytest -m "not model"`; `codecompass --help`; start the server with the command `codecompass` prints; ask one question and read the per-stage timings in `<index dir>/queries/*.json` (`timings`, and `reranker.device` / `reranker.dtype`); and `nvidia-smi` (or Activity Monitor on macOS) for memory at the peak.

**Memory (Linux + NVIDIA).** About 7.75 GiB of the 8 GiB card is used at the peak (desktop 0.8 GiB, server 4.2 GiB, re-ranker process about 2.5 GiB). With all 29 layers on the GPU, or the default `-ub 512`, the second question ran out of memory. On a tighter card use `-ngl 24` (generation 43 tok/s instead of 54), or put the re-ranker back on the CPU. Indexing a **new** repository is faster with the embedder on the GPU: stop `llama-server` first and run once with a copy of the config that sets `[embedder] device = "cuda"`. The device is not part of the index identity, so the index it builds is the same.

The fp16 re-ranker kept the same top-8 chunks on three test questions (and the same order on two; the third swapped near-tied chunks, score difference under 0.0005). It is recorded in every query's audit log as `reranker.dtype`, and a change like this must be re-checked once an evaluation set exists (Article VII.5). Results from `dev-7b-gpu` are development signals only (Article VIII.5).

## How indexing works

1. **Fast path:** read HEAD and `meta.json`; if equal (and config unchanged), return `up-to-date` with no lock, no file reads, no writes.
2. **Change detection:** `git diff --no-renames <indexed>..<HEAD>` (paths only, from the object DB). Rename detection is off, so a rename is one delete plus one add. An empty index diffs against the empty tree, unifying full and incremental builds.
3. **Filtering (cheap first):** path/dir rules → blob size → binary sniff → non-code gate. Skips are counted by rule in the report.
4. **Journal:** target commit + touched paths recorded in `meta.json` before any write, so a crash or revert between runs still converges on re-run.
5. **Per path:** fetch reusable vectors for unchanged chunk text → delete the path's old chunks from **both** stores → chunk the HEAD blob (tree-sitter, or line-window fallback) → embed only new chunk texts (batched, length-sorted) → insert into both stores.
6. **Commit:** single keyword-index commit, advance `indexed_commit`, clear the journal, write the run report. A failed run never advances the commit.
7. **Locking:** one exclusive file lock guards all writes; a second caller waits up to the timeout, then re-checks (usually nothing left to do) or returns an `index is locked` status.

Chunk identity is `sha256(path | symbol | occurrence | text_hash)` — deterministic and line-number-free, so edits elsewhere in a file don't invalidate unchanged chunks.

---

## Project structure

```
codecompass/online/
  tui.py             `codecompass` interactive mode (prompt loop, repo root, layered config, draft, warm-up)
codecompass/offline/
  __init__.py        public API: ensure_current, status, open_index, check_consistency
  config.py          codecompass.toml loader (all tunables live here)
  models.py          Chunk, ChangeSet, IndexMeta, RunReport
  git_source.py      HEAD, diff, blob reads, ancestry (object DB only)
  exclusions.py      include/skip decision pipeline
  chunking/          tree-sitter chunker, line-window fallback, token sizing, ids
  embedding.py       Embedder protocol + real CodeEmbedder (lazy load)
  stores/vector.py   Chroma wrapper       stores/keyword.py  tantivy wrapper
  stores/consistency.py  two-index agreement check
  meta.py            atomic meta.json + compatibility gate
  lock.py            single-writer file lock
  orchestrator.py    full/incremental run, journal, vector reuse
  report.py          human + JSON run reports
  cli.py             index / status / check commands
tests/
  support/           fixture-repo builder, StubEmbedder, in-memory fakes
  offline/           unit + integration tests mirroring the modules
```

Specs and plans: [`docs/specs/001-offline-indexing/spec.md`](docs/specs/001-offline-indexing/spec.md), [`plan.md`](docs/specs/001-offline-indexing/plan.md), [`tasks.md`](docs/specs/001-offline-indexing/tasks.md), [`docs/summary/SPRINT1-SUMMARY.md`](docs/summary/SPRINT1-SUMMARY.md).

---

## Testing

```bash
# Required suite: deterministic, network-blocked, CPU-only, stub embedder
.venv/bin/python -m pytest -m "not model"

# Real-model tests (local only; downloads the pinned model once)
.venv/bin/python -m pytest -m model
```

Sprint 1 verification: **134 passed** in the required suite, **5 passed** in the model suite, no skipped/xfail tests.

---

## Development process

This repo is built **spec-driven and test-first** (see [`AGENTS.md`](AGENTS.md)):

1. Read the constitution, then the task in `docs/specs/001-offline-indexing/tasks.md` plus the spec/plan sections it references.
2. Do one task at a time. Write the listed tests first, run them, confirm they fail for the expected reason — then stop and wait for approval.
3. After approval, write the minimum code to pass; iterate on the code until green; refactor with tests green.
4. Run `pytest -m "not model"` before finishing. Commit tests first, then implementation, as separate commits.

Hard rules: never edit, weaken, skip, or xfail an approved test to pass; stay inside the task's `Touches`; no new/unpinned dependencies without asking; if the spec is ambiguous, mark `[NEEDS CLARIFICATION]` and ask.

---

## Known limitations

- The verifier is only as useful as the repository's commit history; uninformative messages are reported as-is, never invented.
- Only the branch/HEAD passed in is indexed; there is no branch selection.
- Submodules are skipped and reported. Symlinks are flagged, never followed.
- No numeric performance target yet; run reports and query audit logs record timings so one can be set from measurements.
- Answers describe the code committed at HEAD. Uncommitted changes in the working tree are not indexed.
- A 14B model on a 16 GB laptop takes about a minute per generator call (`MODEL-SETUP.md` §5).
- The first question in a repository with no index builds the index first. With the real embedder on CPU that took about 6 minutes for this repository (3 minutes of it indexing, 1 minute re-ranking, 1.5 minutes generating). On a terminal the warm-up does this while you type; the GPU settings above shrink the embedding and re-ranking parts. Run `python -m codecompass.offline.cli index <repo>` ahead of time to pay it separately.
- Interactive mode has no conversation memory and no arrow-key history. The text streamed while the model writes is an unchecked draft, not an answer (see section 7).
- A daemon warm-up thread that is still loading a model when you exit is abandoned, not waited for.
- On an 8 GB GPU the 7B server, the re-ranker and the embedder do not all fit; see "Running fast on an 8 GB GPU" for the tested split.

---

## Roadmap

- [x] Sprint 1: offline indexing pipeline
- [x] Sprint 2: online pipeline: hybrid retriever (RRF-50/50→50), cross-encoder re-ranker (top 8), generator (Qwen2.5-Coder-Instruct via llama-server), verifier tool loop (`git blame`/`git log`, configurable rounds, default 3), deterministic citation checker, evaluation modes
- [ ] Pin the `prod` (32B) GGUF and check it on the target machine (Article VIII.2, VIII.5)
- [ ] Evaluation question set with reference answers/citations; three-way comparison (no-retrieval vs RAG vs RAG+verification); required before any retrieval/prompt/model tuning
- [ ] Performance target from measured run-report timings

---

## Reference

- `docs/constitution.md` — non-negotiable principles (grounding, two pipelines, index correctness, hybrid retrieval, bounded agent loop, citation integrity, evaluation-first, models/environment, TDD, responsible AI, scope)
- `docs/specs/001-offline-indexing/spec.md` — what the pipeline must do (user stories, acceptance criteria)
- `docs/specs/001-offline-indexing/plan.md` — how it is built (interfaces, design decisions D1–D10, optimisations O1–O9)
- `docs/specs/001-offline-indexing/tasks.md` — ordered task list with per-task tests
- `docs/specs/002-online-retrieval/` — spec, plan and tasks for the online pipeline
- `docs/summary/SPRINT1-SUMMARY.md` — what was built, verification results, and design deviations
