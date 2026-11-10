# CodeCompass

CodeCompass is a RAG-based Q&A assistant that helps developers understand an unfamiliar git repository. It retrieves real code and commit history, verifies claims with git tooling, and answers with citations that are checked before they are shown.

This repository implements both pipelines. The **offline indexing pipeline** (Spec 001) turns a git repository into two searchable, mutually consistent indexes: a semantic vector index (Chroma/HNSW) and a keyword index (tantivy BM25). The **online query pipeline** (Spec 002) answers questions from them: hybrid retrieval, cross-encoder re-ranking, a local generator (Qwen2.5-Coder via llama-server), a bounded loop of read-only tools (`git blame`, `git log`, `open_file`, `search_again`), and a deterministic citation checker. The `codecompass` command (Spec 004) is the interactive front end.

> Grounding over fluency: if the evidence is insufficient, CodeCompass says what it could not determine rather than guessing. See [`docs/constitution.md`](docs/constitution.md).

---

## Table of contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Getting started on a new machine](#getting-started-on-a-new-machine)
  - [What `quickstart.py` does](#what-quickstartpy-does)
  - [Troubleshooting](#troubleshooting)
  - [Indexing by hand](#indexing-by-hand)
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
- [Evaluation](#evaluation)
- [Development process](#development-process)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Reference](#reference)

---

## Architecture

```
Offline (indexing)                              Online (each question)
Git repository                                  Developer question
  → Repo scanner (tree-sitter + GitPython,        → ensure_current (incremental re-index if HEAD moved)
    changed files only)                           → Hybrid retrieval: vector top 50 + BM25 top 50, RRF merge
    → Code-aware embedder                         → Cross-encoder re-ranker (bge-reranker-v2-m3) → top 8
      (jina-embeddings-v2-base-code, local)       → Generator (Qwen2.5-Coder via llama-server)
      → Vector store (Chroma/HNSW)                  ⇄ read-only tools: git blame, git log, open_file,
    → Keyword index (BM25, tantivy)                   search_again (at most max_verifier_rounds)
                                                  → Citation checker → verified (F) or flagged (G) answer
```

One indexing code path: **a full build is an incremental run from an empty index**. Before answering each question, the online pipeline calls the single public `ensure_current` entry point, which compares repo HEAD against the last indexed commit and re-indexes only the files that changed.

Module boundaries are strict: only `codecompass.offline`'s `ensure_current` (write-capable), `status`, `open_index`, and `check_consistency` (read-only) are visible to the online pipeline.

---

## Requirements

- Python 3.11 to 3.14 and Git, on macOS, Linux, or Windows. To install them:
  - macOS: `brew install python@3.14 git` ([Homebrew](https://brew.sh)), then use `python3.14`.
  - Ubuntu/Debian: `sudo apt install python3 python3-venv git` (check `python3 --version` is 3.11 to 3.14; `python3-venv` is needed to create the venv).
  - Windows: Python 3.14 from [python.org](https://www.python.org/downloads/) (tick "Add python.exe to PATH") and [Git for Windows](https://git-scm.com/download/win); then use `py -3.14`. Python 3.15 does not work yet: the pinned `torch` has no 3.15 build. If `python3 --version` shows 3.15, run the quickstart with `python3.14` (or 3.11 to 3.13).
- The pinned `torch` 2.14.1 has builds for Linux (x86_64 and ARM), Windows (x64) and **Apple Silicon Macs on macOS 14 or later** only. Intel Macs and macOS 13 or older cannot install it.
- **For indexing and the test suite:** nothing else. No GPU, paid service, or network access once installed.
- **For asking questions:** llama.cpp's `llama-server` and one Qwen2.5-Coder GGUF file (4.7 GB for the 7B, 9 GB for the 14B). Pick the profile by memory:

  | Profile | Model | Context | Fits |
  |---|---|---|---|
  | `dev` (default) | 14B Q4_K_M | 32768 | about 24 GB RAM or more |
  | `dev-lowmem` | 14B Q4_K_M | 8192 | 16 GB machines |
  | `dev-7b` | 7B Q4_K_M | 16384 | smaller machines, development only |
  | `dev-7b-gpu` | 7B Q4_K_M | 8192 | an 8 GB NVIDIA GPU, development only (see [Running fast on a GPU](#running-fast-on-a-gpu)) |

  Reported evaluation results use a 14B profile only (constitution Article VIII.5).
- **Network, once:** to install the pinned packages, and to download the embedder (during the first index), the re-ranker (on the first question) and the GGUF.
- **Disk space:** about 8 GB with the 7B or 13 GB with the 14B. Measured: `.venv` 1.4 GB, embedder 0.3 GB and re-ranker 2.1 GB (in `~/.cache/huggingface`), GGUF 4.7 GB (7B) or 9 GB (14B), plus the index (tens of MB for a typical repo).

---

## Getting started on a new machine

Run these from a terminal. `<repo>` is any git repository you want to ask about (not this one).

**1. Clone CodeCompass and run the quickstart.**

```bash
git clone https://github.com/rodneywangjl/CodeCompass-project.git
cd CodeCompass-project
python3 quickstart.py /path/to/repo --profile dev-lowmem     # Windows: py -3.14 quickstart.py ...
```

This sets up everything on the CodeCompass side: the virtual environment, the `codecompass` command, your personal config, the index for `<repo>`, and a test run. [What `quickstart.py` does](#what-quickstartpy-does) below explains each step, the options and the personal config file.

**2. Install `llama-server`** (llama.cpp, release b11960 is the tested build):

Download the file for your machine from the [b11960 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11960), extract it, and run `llama-server --version` from the extracted folder (put the folder on your `PATH`, or use the full path):

| Machine | File |
|---|---|
| Apple Silicon Mac | `llama-b11960-bin-macos-arm64.tar.gz` (Metal GPU included) |
| Linux x86_64, CPU only | `llama-b11960-bin-ubuntu-x64.tar.gz` |
| Linux ARM, CPU only | `llama-b11960-bin-ubuntu-arm64.tar.gz` |
| Linux + NVIDIA | `llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz` plus its `cudart-…` file (steps under [Running fast on a GPU](#running-fast-on-a-gpu)) |
| Windows x64, CPU only | `llama-b11960-bin-win-cpu-x64.zip` |
| Windows + NVIDIA | `llama-b11960-bin-win-cuda-13.4-x64.zip` plus `cudart-llama-bin-win-cuda-13.4-x64.zip` |
| Any GPU (AMD, Intel) | the `vulkan` build for your OS |

On macOS, `brew install llama.cpp` also works, but installs whatever version is current rather than the pinned b11960 (Article VIII.2 asks for the release to be recorded). On macOS the downloaded binary may be blocked by Gatekeeper the first time: `xattr -dr com.apple.quarantine <folder>` clears it. Linux and Windows builds are listed with checksums under [Running fast on a GPU](#running-fast-on-a-gpu).

**3. Download the GGUF for your profile** and check its SHA-256 against `gguf_checksum` in your personal config:

```bash
mkdir -p ~/.cache/codecompass/models
# 14B (dev, dev-lowmem)
.venv/bin/huggingface-cli download Qwen/Qwen2.5-Coder-14B-Instruct-GGUF \
  qwen2.5-coder-14b-instruct-q4_k_m.gguf --local-dir ~/.cache/codecompass/models
# 7B (dev-7b, dev-7b-gpu)
.venv/bin/huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct-GGUF \
  qwen2.5-coder-7b-instruct-q4_k_m.gguf --local-dir ~/.cache/codecompass/models
shasum -a 256 ~/.cache/codecompass/models/*.gguf      # Linux: sha256sum
```

On Windows (PowerShell), the same for the 14B:

```powershell
$m = "$env:USERPROFILE\.cache\codecompass\models"; New-Item -ItemType Directory -Force $m | Out-Null
.venv\Scripts\huggingface-cli download Qwen/Qwen2.5-Coder-14B-Instruct-GGUF `
  qwen2.5-coder-14b-instruct-q4_k_m.gguf --local-dir $m
Get-FileHash "$m\*.gguf" -Algorithm SHA256
```

**4. Start the server** in its own terminal and leave it running. The context (`-c`) must match the profile; `codecompass` prints this exact command when the server is not running. For `dev-lowmem`:

```bash
llama-server -m ~/.cache/codecompass/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 8080 -c 8192
```

On Windows, run `llama-server.exe` from the folder you extracted, with the same arguments and the model path `$env:USERPROFILE\.cache\codecompass\models\...`.

**5. Ask questions.**

```bash
source .venv/bin/activate       # Windows: .venv\Scripts\activate
cd /path/to/repo
codecompass
```

The first question downloads the re-ranker (2.1 GB) and loads the models, so it is slow; later questions in the same session are not. The index is brought up to date before every question, so after new commits just ask again. See [Interactive mode](#7-interactive-mode-codecompass) for the commands inside a session and [Ask a question](#6-ask-a-question) for the one-shot `ask` command and how to read the verified/flagged answer.

### What `quickstart.py` does

`quickstart.py` (in the project root) takes a machine that has never run CodeCompass to the point where `codecompass` can answer questions about one repository. It uses only the Python standard library, so you run it with a plain system Python before anything is installed. It contains no indexing logic of its own: it calls the same commands described in this README.

**How to run it.** From the CodeCompass folder:

```bash
python3 quickstart.py /path/to/repo                          # defaults: profile dev, real embedder, runs tests
python3 quickstart.py /path/to/repo --profile dev-lowmem     # 16 GB machine
python3 quickstart.py ../my-project --skip-tests             # a relative path works from any folder
py -3.14 quickstart.py C:\code\my-project --profile dev-7b   # Windows
```

| Option | Effect |
|---|---|
| `<repo>` (required) | The git repository to index. Only committed code at HEAD is indexed. |
| `--profile NAME` | `default_profile` for a **new** personal config: `dev` (default), `dev-lowmem`, `dev-7b` or `dev-7b-gpu` (see the table under [Requirements](#requirements)). Ignored, with a message, if the file already exists. |
| `--skip-install` | Skip both `pip install` steps (the `.venv` must already be set up). |
| `--skip-tests` | Skip the test suite (saves about 6 minutes). |
| `--embedder stub` | Model-free smoke test of the install. `codecompass` cannot query a stub-built index; run again without it. |

**What it does, in order.** It stops at the first step that fails, with `quickstart: <step> failed: <reason>` and exit code 1.

1. **Checks Python.** It must be 3.11 to 3.14 (the pinned `torch` has no build for other versions). If `.venv` already exists, it checks the venv's Python too.
2. **Creates `.venv`** in the project folder, if it does not exist.
3. **Installs** the pinned `requirements.txt`, then the project itself (`pip install -e .`), which adds the `codecompass` command to `.venv`.
4. **Sets up your personal config** (see below).
5. **Indexes the repository** with the real embedder (downloaded about 300 MB the first time), then prints `status` (should be `current`) and `check` (should be `consistent: True`). The index goes in your OS application-data folder, never inside the repo.
6. **Runs the required test suite**, `pytest -m "not model"`, to show the install works on this machine.
7. **Prints the next steps**: download the GGUF, start `llama-server`, run `codecompass`.

Running it again is safe and quick: installed packages are skipped, the personal config is kept, and only files changed since the last run are re-indexed. Run it once per repository you want to use (or just run `codecompass` in a new repository: it builds the index on the first question).

**The personal config file.** `codecompass` reads settings from the repo's own `codecompass.toml` and from a personal file that applies in every repo:

| OS | Path |
|---|---|
| macOS, Linux | `~/.config/codecompass/codecompass.toml` (or `$XDG_CONFIG_HOME/codecompass/codecompass.toml` if set) |
| Windows | `%APPDATA%\codecompass\codecompass.toml` |

The built-in profiles name the model but no GGUF file or checksum, so without this file `codecompass` cannot run the generator in a repo that has no `codecompass.toml` of its own. quickstart handles it like this:

- **If the file does not exist**, it creates it with your `--profile` as `default_profile` and a copy of every pinned profile from this project's `codecompass.toml` (model, GGUF file name, SHA-256, context window, generation settings). It checks the new file with the same loader `codecompass` uses before saving it, so a broken file is never left behind, and prints `Wrote personal config: <path>` and the chosen profile.
- **If the file exists**, it is never changed. quickstart only checks that it loads and that its `default_profile` is defined, and prints `Personal config exists, left unchanged`. If the check fails, it stops and prints why.

The start of a new file looks like this:

```toml
# Personal CodeCompass settings, written by quickstart.py.
...
[generator]
default_profile = "dev-lowmem"

[generator.profiles."dev"]
model_id = "Qwen2.5-Coder-14B-Instruct"
gguf_file = "qwen2.5-coder-14b-instruct-q4_k_m.gguf"
gguf_checksum = "c1e659736d89ac1065fb495330fb824d94001974a4bfa78e7270e43476a8d940"
context_window = 32768
...
```

To change profile later, edit `default_profile` in the file, or override it per session with `codecompass --profile NAME` or the `GENERATOR_PROFILE` environment variable. To start over, delete the file and run quickstart again. A repo's own `codecompass.toml` is layered on top and wins where it sets a value. GPU settings (`[reranker]` and `[embedder]` `device`/`dtype`) are not written; add them by hand as described under [Running fast on a GPU](#running-fast-on-a-gpu).

**What it does not do.** It does not install `llama-server`, download the GGUF or start the server (steps 2 to 4 above), because those depend on your hardware. It never changes the repository you index, this project's `codecompass.toml`, or an existing personal config.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `codecompass: No such file or directory`, `bad interpreter`, or `No module named 'codecompass'` | The CodeCompass folder was moved or renamed after installing; a venv cannot be moved. Delete `.venv` and run `python3 quickstart.py <repo> --skip-tests` again. |
| `warning: llama-server is not reachable` | The server is not running, or not on port 8080. Start it with the command in the warning. |
| The server or `codecompass` runs out of memory | The profile is too big for the machine. Use `codecompass --profile dev-lowmem` (or `dev-7b`), or change `default_profile` in your personal config, and restart `llama-server` with the matching `-c`. |
| `embedder ... does not match` when asking | The index was built with `--embedder stub`. Run `python -m codecompass.offline.cli index <repo> --full`. |
| `quickstart: Python 3.11 to 3.14 is required` or `.venv uses Python 3.15` | Run the quickstart with a supported Python, e.g. `python3.14 quickstart.py ...`; delete `.venv` first if it was created with the wrong one. |
| `quickstart: checking ... failed` | Your personal config has an error (the reason is printed). Fix the file, or delete it and run the quickstart again to recreate it. |

### Indexing by hand

`quickstart.py` only calls the offline command line, which you can also use directly:

```bash
.venv/bin/python -m codecompass.offline.cli index /path/to/repo    # first run: full; later: changed files only
.venv/bin/python -m codecompass.offline.cli status /path/to/repo   # current / stale / empty, and the indexed commit
.venv/bin/python -m codecompass.offline.cli check /path/to/repo    # both indexes hold the same chunk ids
```

All dependencies are pinned in [`requirements.txt`](requirements.txt), and the embedder revision in `codecompass/offline/config.py`. Do not add `mlx-lm` or MLX: generator inference uses llama.cpp only.

---

## User guide

The indexing commands (sections 1 to 3) share the form:

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
# Memory cap per embedding batch: texts * (longest text in tokens)^2. Long chunks
# go in smaller batches, so indexing a big repo on the CPU cannot run out of memory.
max_batch_cost = 8388608

[lock]
timeout_seconds = 120
```

Notes:

- Unknown sections or keys are rejected. `target_tokens > hard_max_tokens` is rejected.
- Relative `index.dir` resolves against the config file's directory.
- Changing exclusion rules takes effect on the next run; newly excluded paths have their chunks removed from both indexes. Changing chunking settings triggers re-chunking (vectors reused where chunk text is unchanged).
- The embedder identity (model, revision, dimension) is recorded in index metadata; opening or writing with a different one fails with a clear error. The schema version is gated the same way.

**Online (question answering) settings.** The same file takes these sections, shown with their built-in defaults:

```toml
[retrieval]
vector_k = 50                     # vector (ANN) candidates
keyword_k = 50                    # BM25 candidates
rrf_constant = 60                 # Reciprocal Rank Fusion constant (Article IV.2)
rerank_k = 50                     # RRF shortlist the re-ranker sees
final_k = 8                       # chunks given to the generator (also capped by the context window)
min_top_score = 0.02              # evidence gate: below this best re-rank score, decline before generating
closest_files = 3                 # files suggested when the gate declines
docs_fallback = false             # also search indexed docs when code evidence is weak
doc_languages = ["md", "rst"]
docs_margin = 0.2

[reranker]
model = "BAAI/bge-reranker-v2-m3"
revision = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
device = "cpu"                    # "cuda" (NVIDIA) or "mps" (Apple) if available
dtype = "float32"                 # "float16" needs a GPU device

[generator]
default_profile = "dev"           # overridden by GENERATOR_PROFILE or --profile
server_url = "http://127.0.0.1:8080"
timeout_seconds = 120             # per generator call
connect_timeout_seconds = 5       # first contact with llama-server
generation_reserve_tokens = 1024  # context kept free for the answer
# [generator.profiles.NAME] tables: see codecompass.toml for the pinned ones

[tools]
max_verifier_rounds = 3           # tool runs per question; 0 = no tools (Article V.1)
allowed_tools = ["git_blame", "git_log", "open_file", "search_again"]  # can only remove, never add
git_log_limit = 20
git_blame_timeout = 30
git_log_timeout = 30
max_tool_output_tokens = 768

[pipeline]
mode = "rag_tools"                # "rag" (no tools) or "no_retrieval": the evaluation configurations

[logging]
query_log_dir = ""                # default: <index dir>/queries/

[prompt]
vague_question_hint = false
format_example = false            # add one example answer to the system prompt
```

- Config files are layered: built-in defaults, then your personal config, then the repo's `codecompass.toml` (see [Interactive mode](#7-interactive-mode-codecompass)).
- Startup fails loudly on an unknown key inside these sections, an unknown profile, pipeline mode or tool name, and a `max_verifier_rounds` that leaves no room for retrieved chunks. A misspelled *section* name is not caught, so its settings are silently ignored.
- The retrieval sizes, re-ranker, prompt options and profile affect results: change them only with an evaluation run (Article VII.5). Each query's audit log records the values in force.

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
- **Options:** `--profile NAME` (else `GENERATOR_PROFILE`, else the config default), `--config PATH`, `--index-dir DIR`, `--no-draft`, `--theme auto|dark|light`, `--no-color`, `--plain`.
- **Output:** only the answer goes to stdout, exactly as `ask()` returns it, so a flagged answer always shows its banner and `[UNVERIFIED]` marks. The prompt, a "Thinking…" line, the startup banner, warnings and errors go to stderr, and only on a terminal. Piped input works: `codecompass < questions.txt > answers.txt`.
- **Keys:** `/exit`, `/quit` or Ctrl-D to leave. Ctrl-C at the prompt prints a hint; Ctrl-C during a question abandons it and returns to the prompt. A failed question prints `error: ...` and the session carries on.
- **Tools used:** after each answer on a terminal, one line says how many tool calls the answer used (`▸ 3 tools called — type /tools to see them`, or `▸ No tools called`). Type `/tools` to list them for the last answered question: the round, the tool, its arguments, whether the result came from the cache, and the first line of the result. `/tools` is a command, not a question: it is never sent to the model. Only calls that ran are counted; a malformed request, or one refused after the round limit, gets a line in `/tools` but is not counted. (There is no mouse support: a click would need a full-screen interface, which means a new dependency or code that does not work on Windows.)
- **Colour:** on a colour terminal the prompt, the status line, the tool line, `/tools`, `error:` and `warning:` and the flagged parts of an answer (the banner, `[UNVERIFIED]`, `(not cited)`, the `[N]` markers, the `Sources` heading) are coloured, in a Rosé Pine theme: `dark` is Rosé Pine Moon, `light` is Rosé Pine Dawn with a darker error colour. Colour is only ever added around text: with the colour removed, the output is word for word what it was, and a flagged answer is never made to look verified. `--theme auto` (the default) uses the light theme when the terminal sets `COLORFGBG` to a light background and the dark theme otherwise; some terminals do not set it, so use `--theme light` (or the `CODECOMPASS_THEME` environment variable) there. Colour is used only on a real terminal, for stdout and stderr separately, so piped output never has any. `--no-color`, or any non-empty `NO_COLOR` environment variable ([no-color.org](https://no-color.org)), turns it off. Terminals without truecolor get the nearest of 256 colours, and others none. Inside a session, `/theme none` turns colour off and `/theme rose-pine` turns it back on (Moon or Dawn as above); `/theme` alone shows the current choice. `/theme rose-pine` overrides `NO_COLOR` and `--no-color` because it is an explicit choice, but not a terminal that cannot show colour. The choice lasts for the session; nothing is saved.
- **Live interface:** on a real terminal the session looks and behaves more like Claude Code. The prompt is a rounded box with a status line under it (`<repo> · <profile> · <model>`); while a question runs, the status line is a spinner with the elapsed time (`✻ Thinking… (12s · ctrl-c to cancel)`); each tool call is shown as soon as it finishes (`● git_log(path=src/auth.py, n=5)` and `⎿` with the first line of its result); and the answer's markdown is styled with its punctuation removed (headings, **bold**, *italic*, `code`, code blocks, bullets). Nothing the citation checker produced (the banner, notes, `[UNVERIFIED]`, `(not cited)`, the `[N]` markers, the `Sources` section) is changed by it. It uses only the standard library. Limits: there is no pop-up menu when you type `/`, no multi-line editing inside the box and no mouse, and a very long question overwrites the right edge of the box. Pipes, files and `--plain` get the plain interface; use `--plain` on a terminal that handles cursor movement badly.
- **Generator:** the command never starts `llama-server`. If it is not running, or does not match the profile, you get a warning with the start command and the session still opens.
- **Models:** the generator, re-ranker and embedder are created once per session and reused. Each question is independent (there is no conversation memory).
- **Warm-up:** on a terminal, as soon as the session opens, a background thread brings the index current and loads the models while you type. A question asked before it finishes shows `Preparing index and models…` and waits; one asked afterwards starts at once. Piped input does not warm up, and `/exit` never waits for it.
- **Watching the model write (unchecked draft):** on a terminal, the model's text appears on stderr as it is written, under `⚠ DRAFT — NOT CHECKED. The model is still writing. Do not rely on this text.`, every line starting with `draft │ ` and dimmed. When the answer is ready you see `Draft finished after N s.` and `── Checked answer (replaces the draft above) ──`, and only then does the **checked** answer go to stdout. The draft is never on stdout, has not been through the citation check, and may contain citations that the check will flag. Turn it off with `--no-draft`; it is also off when stderr is not a terminal. Control characters in the draft are removed.

#### Running fast on a GPU

> **On the SCIS GPU cluster?** Follow [`GPU-CLUSTER.md`](GPU-CLUSTER.md): getting a 3090 node with Slurm, building `llama-server`, running the `dev` (14B) profile, and fixes for the errors we hit.

The project runs on Linux, Windows and macOS, with the GPU API chosen per machine and CPU-only always possible (constitution Article VIII.2). What has actually been **tested** is narrower:

| Platform | `llama-server` build (release b11960) | Embedder / re-ranker device | Status |
|---|---|---|---|
| Linux + NVIDIA | `llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz` + `cudart-llama-b11960-bin-ubuntu-cuda-13.4-x64.tar.gz` | `cuda` | **Tested** (numbers below, RTX 3070 Ti 8 GB) |
| Windows + NVIDIA | `llama-b11960-bin-win-cuda-13.4-x64.zip` + `cudart-llama-bin-win-cuda-13.4-x64.zip` | `cuda` | Not tested on a real machine; see "Windows" below |
| macOS (Apple Silicon or Intel) | `llama-b11960-bin-macos-arm64.tar.gz` / `-x64.tar.gz` (Metal), or `brew install llama.cpp` | `mps` | Not tested on a real machine; see "macOS" below |
| AMD / Intel GPU | the `vulkan` builds (Linux and Windows) | `cpu` (the pinned PyTorch has no ROCm or XPU build) | Not tested |
| CPU only, any OS | any build, or `win-cpu-x64` | `cpu` | Works everywhere, slow: re-ranking one shortlist took 52 s here |
| SCIS GPU cluster (RTX 3090, Slurm) | b11960 built from source with CUDA 12.6 (the cluster's glibc is too old for the prebuilt binaries) | `cuda` | Used with the `dev` 14B profile, median 5.1 s per answer (RAG only) and 8.2 s with tools; step-by-step guide in [`GPU-CLUSTER.md`](GPU-CLUSTER.md) |

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
quickstart.py        new-machine setup: venv, install, personal config, index, tests
codecompass.toml     project config: pinned generator profiles (dev, dev-lowmem, dev-7b, dev-7b-gpu)
codecompass/online/
  __init__.py        public API: ask(), warm_up()
  config.py          online config, profiles, layered config files
  retrieval/         query embedding, vector + BM25 search, RRF merge, cross-encoder re-ranker
  generator/         the one llama-server client: HTTP, profiles, launch command
  agent/             tool-call parser, read-only tools, tool cache, bounded harness loop
  citation/          Sources parser, deterministic checker, verified/flagged formatting
  context.py         context budgeting for the active profile
  logging.py         per-query JSON audit log
  cli.py             one-shot `ask` command
  tui.py, tui_*.py   `codecompass` interactive mode (prompt loop, repo root, layered config, draft, warm-up)
codecompass/eval/    evaluation runs, grading and reports (Spec 003)
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
  support/           fixture-repo builder, StubEmbedder, StubGenerator, StubReranker, fakes
  offline/, online/  unit + integration tests mirroring the modules
eval/                question set, eval config, versioned results
```

Specs, plans and tasks are in [`docs/specs/`](docs/specs/): [001 offline indexing](docs/specs/001-offline-indexing/spec.md), [002 online retrieval](docs/specs/002-online-retrieval/spec.md), [003 evaluation](docs/specs/003-evaluation/spec.md), [004 interactive mode](docs/specs/004-tui/spec.md), [005 GPU inference](docs/specs/005-gpu-inference/spec.md). Sprint records: [`docs/summary/`](docs/summary/).

---

## Testing

```bash
# Required suite: deterministic, network-blocked, CPU-only, stub embedder
.venv/bin/python -m pytest -m "not model"

# Real-model tests (local only; downloads the pinned model once)
.venv/bin/python -m pytest -m model
```

Latest run (9 Nov 2026, `main` at `0518a82`, WSL): **1502 passed** in the required suite, 10 model tests deselected, none skipped or xfail ([`docs/final/test-results.md`](docs/final/test-results.md)). Sprint 1 verification: 134 passed in the required suite, 5 passed in the model suite.

---

## Evaluation

The evaluation compares three configurations on the same questions (constitution Article VII): **(a)** no retrieval, **(b)** RAG only and **(c)** RAG with the verifier tools. The method is in [`docs/specs/003-evaluation/`](docs/specs/003-evaluation/), and the full figures, each with its n, are in [`eval/results/report-eval-v1/report.md`](eval/results/report-eval-v1/report.md).

**Setup.** CodeCompass at tag `eval-v1` (`c6fa1b7`) on Flask at `85c5d93`. Qwen2.5-Coder-14B-Instruct (Q4_K_M, `dev` profile, 32k context, temperature 0.1, seed 42) through llama.cpp b11960 on one RTX 3090. Settings are in [`eval/codecompass.eval.toml`](eval/codecompass.eval.toml). Every results file records the commits, the config hash, the model ids and the hardware.

**Questions.** 88 frozen questions: 40 written by the team (8 in each of five categories, including 8 unanswerable controls) and 48 taken from SWE-QA. Every answerable question has a reference answer and ground-truth lines, checked by hand. A subset of 20, picked by a fixed rule before any run, was graded by two people independently with the configuration hidden. No answer was graded by an AI.

### Results

| | (b) RAG only | (c) RAG + tools |
|---|---|---|
| Hallucination rate, graded subset (n = 20) | 55% | 20% |
| Strict rate, format slips counted (n = 20) | 75% | 50% |
| Mean answer quality, 0 to 2 (n = 20) | 0.80 | 0.95 |
| Citation accuracy, all questions (n = 88) | 35% | 15% |
| Median time per answer (n = 88) | 5.1 s | 8.2 s |

- **The tools reduce hallucination:** Verification Gain +0.35 (+0.25 strict). Part of the gain comes from the tools declining more often, not from better answers.
- **Hybrid retrieval beats either retriever alone.** With a ground-truth file in the top 5 chunks: vector 85%, BM25 89%, RRF 94% (n = 80 answerable questions). The re-ranker's effect was mixed.
- **Citation accuracy is low mostly because of format slips:** the model lists `Sources` but leaves out the `[N]` markers in the text, so correct sources are flagged. Invented citations were rare (H1: 0 in (b), 2 in (c)).
- **Without retrieval** the model refused 74 of 88 questions, and the checker caught all 14 citations it produced. The contamination check was therefore inconclusive.
- **Graders' agreement before settling:** score 75% (κ 0.55), hallucination judgement 68% (κ 0.24).

Example answers for each outcome (verified, format slip, unverified citation, abstention) are in [`docs/final/sample-runs.md`](docs/final/sample-runs.md).

**Exploratory runs** (not graded, not part of the comparison, no default changed). Adding one example answer to the prompt (`format_example = true`) halved the format slips (56 → 28 of 88) and raised citation accuracy from 15% to 45%, but H1 rose from 2 to 4; this run was on `main` (`01bbc6e`), because the flag was added after the freeze. Indexing documentation (28%) and 1024-token chunks (18%) helped less. Details: [`eval/results/experiments/README.md`](eval/results/experiments/README.md).

### Limitations

- Small samples: 20 graded questions per configuration and one run each. No significance tests.
- Judging whether a claim is supported is hard even for people (κ 0.24 before settling).
- "Verified" means the cited file or commit was in the model's context, not that the claim is true.
- One model (14B), one GPU and one repository. The 32B production model and the held-out FastAPI set were not run.
- The tools can only explain *why* if the commit history says why (Article X.5).
- The evidence gate refuses questions that name no file or function before the model runs.

---

## Development process

This repo is built **spec-driven and test-first** (see [`AGENTS.md`](AGENTS.md)):

1. Read the constitution, then the task in `docs/specs/<NNN-feature>/tasks.md` plus the spec/plan sections it references.
2. Do one task at a time. Write the listed tests first, run them, confirm they fail for the expected reason — then stop and wait for approval.
3. After approval, write the minimum code to pass; iterate on the code until green; refactor with tests green.
4. Run `pytest -m "not model"` before finishing. Commit tests first, then implementation, as separate commits.

Hard rules: never edit, weaken, skip, or xfail an approved test to pass; stay inside the task's `Touches`; no new/unpinned dependencies without asking; if the spec is ambiguous, mark `[NEEDS CLARIFICATION]` and ask.

---

## Known limitations

- The verifier is only as useful as the repository's commit history; uninformative messages are reported as-is, never invented.
- Only the branch/HEAD passed in is indexed; there is no branch selection.
- Submodules are skipped and reported. Symlinks are flagged, never followed.
- No performance target has been set. Measured on one RTX 3090 with the 14B model: median 5.1 s per answer with RAG only and 8.2 s with tools (n = 88; see [Evaluation](#evaluation)). Run reports and query audit logs record timings per stage.
- Answers describe the code committed at HEAD. Uncommitted changes in the working tree are not indexed.
- A 14B model on a 16 GB laptop takes about a minute per generator call (`MODEL-SETUP.md` §5).
- The first question in a repository with no index builds the index first. With the real embedder on CPU that took about 6 minutes for this repository (3 minutes of it indexing, 1 minute re-ranking, 1.5 minutes generating). On a terminal the warm-up does this while you type; the GPU settings above shrink the embedding and re-ranking parts. Run `python -m codecompass.offline.cli index <repo>` ahead of time to pay it separately.
- Interactive mode has no conversation memory and no arrow-key history. The text streamed while the model writes is an unchecked draft, not an answer (see section 7).
- A daemon warm-up thread that is still loading a model when you exit is abandoned, not waited for.
- On an 8 GB GPU the 7B server, the re-ranker and the embedder do not all fit; see [Running fast on a GPU](#running-fast-on-a-gpu) for the tested split.

---

## Roadmap

- [x] Sprint 1: offline indexing pipeline
- [x] Sprint 2: online pipeline: hybrid retriever (RRF-50/50→50), cross-encoder re-ranker (top 8), generator (Qwen2.5-Coder-Instruct via llama-server), verifier tool loop (`git blame`, `git log`, `open_file`, `search_again`; configurable rounds, default 3), deterministic citation checker, evaluation modes
- [x] Interactive mode: the `codecompass` command (Spec 004)
- [x] 7B generator and fp16 re-ranker on one 8 GB GPU (Spec 005, development only)
- [ ] Pin the `prod` (32B) GGUF and check it on the target machine (Article VIII.2, VIII.5)
- [x] Evaluation question set with reference answers/citations; three-way comparison (no-retrieval vs RAG vs RAG+verification): done at `eval-v1`, see [Evaluation](#evaluation)
- [ ] Generalisation run on the held-out FastAPI question set
- [ ] Performance target from measured run-report timings

---

## Reference

- `docs/constitution.md` — non-negotiable principles (grounding, two pipelines, index correctness, hybrid retrieval, bounded agent loop, citation integrity, evaluation-first, models/environment, TDD, responsible AI, scope)
- `docs/specs/001-offline-indexing/spec.md` — what the pipeline must do (user stories, acceptance criteria)
- `docs/specs/001-offline-indexing/plan.md` — how it is built (interfaces, design decisions D1–D10, optimisations O1–O9)
- `docs/specs/001-offline-indexing/tasks.md` — ordered task list with per-task tests
- `docs/specs/002-online-retrieval/` — spec, plan and tasks for the online pipeline
- `docs/summary/SPRINT1-SUMMARY.md` — what was built, verification results, and design deviations
- `docs/specs/003-evaluation/` — evaluation spec, plan, tasks and the complexity tagging rule
- `docs/specs/004-tui/` — spec, plan and tasks for the minimal terminal UI (`codecompass`)
- `docs/specs/005-gpu-inference/` — spec, plan and tasks for running the 7B generator and the re-ranker on one 8 GB GPU
- `eval/questions/README.md` — how the 88 evaluation questions are built, tagged and checked
- `eval/results/report-eval-v1/` — the eval-v1 report (`report.md`) and failure candidates; exploratory runs in `eval/results/experiments/README.md`
- `MODEL-SETUP.md` — record of the development model setup (`llama-server`, pinned GGUF files, profiles)
- `GPU-CLUSTER.md` — running CodeCompass with the `dev` 14B profile on the SCIS GPU cluster
- `AGENTS.md` — rules for AI coding agents working in this repo
- `ai-log/` — each member's AI use log
- `docs/final/` — final submission documents: AI use declaration, member reflections, sample runs and test results
