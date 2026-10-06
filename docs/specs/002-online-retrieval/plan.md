# Plan 002: Online Query Pipeline

**Implements:** Spec 002 (Online Query Pipeline) | **Constitution:** v1.2.0 | **Status:** Draft for review

> The spec says what the pipeline must do. This plan says how we will build it, in the leanest way that satisfies every acceptance criterion (AC) without adding components the constitution doesn't allow (Article XI).

---

## 1. Design in one page

One function, one flow. `ask(repo, question)` runs the entire pipeline and returns a structured result. No mutable state between calls.

```
ask(repo, question, *, config, profile)
  ├─ ensure_current(repo, config)                        # offline API (write path)
  │     └─ failed? → set stale_flag, continue with existing index
  ├─ open_index(repo, config)                            # offline API (read-only handles)
  │     └─ empty? → return "no evidence" answer
  ├─ embed query (same embedder as index)
  ├─ vector_search(query_vector, k=50)
  ├─ keyword_search(question, k=50)
  ├─ rrf_merge(vector_hits, keyword_hits, constant=60, k=50)
  ├─ fetch chunk records for merged ids
  ├─ rerank(question, chunks, k=8)                       # cross-encoder
  ├─ cap to context budget (profile-driven)
  ├─ assemble context (plain text + metadata)
  ├─ agent loop (round = 0):
  │     ├─ build messages: system + context + conversation
  │     ├─ generate(messages)                             # llama-server HTTP
  │     ├─ parse response:
  │     │     ├─ tool call? → validate args → execute → cache → log → append to messages → round++ → loop if round < 3
  │     │     └─ answer? → break
  │     └─ round == 3? → force answer from last response
  ├─ citation_check(answer, context)                     # deterministic F/G
  ├─ if commit sources → harness copies metadata from tool results
  ├─ build QueryResult (answer, sources, outcome, stale_flag, audit_log)
  └─ return QueryResult
```

## 2. Technology choices (fixed by the constitution unless noted)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | Same as offline side |
| Generator | Qwen2.5-Coder-Instruct 14B (dev) / 32B (prod) | Via llama.cpp `llama-server` (Article VIII.2) |
| Generator client | `httpx` or `urllib3` (standard HTTP) | No `llama-cpp-python` (Article VIII.2) |
| Cross-encoder | `BAAI/bge-reranker-v2-m3` | Via `sentence-transformers` `CrossEncoder` or `FlagEmbedding`. *Plan decision.* |
| Query embedder | Same `jinaai/jina-embeddings-v2-base-code` as indexing | Reuses `CodeEmbedder` from offline (Article II.4) |
| Vector search | Chroma collection `.query()` | Via read-only handles from `open_index` |
| Keyword search | tantivy `.search()` | Via read-only handles from `open_index` |
| Git tools | `subprocess` calling `git blame`, `git log` | Validated args, no shell (Article V.2) |
| Tests | pytest | Article IX.7 |

All versions pinned in `requirements.txt`. No mlx-lm.

## 3. Package layout

```
codecompass/online/
  __init__.py        public API: ask
  config.py          online-specific config: retrieval params, profile loading, tool settings
  models.py          QueryResult, SourceEntry, ToolCall, ToolResult, AuditLog, CitationOutcome
  retrieval/
    embedder.py      query embedding (reuses offline CodeEmbedder, same model)
    vector.py        vector ANN search wrapper (uses read-only VectorStore)
    keyword.py       BM25 search wrapper (uses read-only KeywordIndex)
    rrf.py           Reciprocal Rank Fusion merge
    reranker.py      cross-encoder re-ranker (RerankerProtocol + BgeReranker)
  context.py         context assembly: format chunks as plain text with metadata, budget capping
  generator/
    protocol.py      Generator protocol (generate method)
    llama.py         LlamaServerGenerator: HTTP client to llama-server, chat template, stop tokens
    profiles.py      model profile loader (dev, prod), validation
    server.py        health check, connection management (lifecycle docs)
  agent/
    harness.py       agent loop: round counting, tool-call dispatch, message building
    tool_parser.py   parse tool calls from model text output
    tools.py         git_blame, git_log executors with arg validation
    cache.py         per-query tool-result cache
  citation/
    checker.py       deterministic citation checker (F/G)
    parser.py        parse Sources section, extract SourceEntry objects
    formatter.py     format flagged/cited answers with banners and marks
  logging.py         per-query structured audit log builder
  cli.py             `ask` CLI entry point
tests/
  support/           StubGenerator, StubReranker, canned responses
  online/            unit + integration tests mirroring the modules
```

**Boundary rule (Article II.2):** the online package imports from `codecompass.offline` only: `ensure_current`, `open_index`, `status`, `EnsureResult`, `IndexHandles`, `IndexStatus`. It never imports scanner, chunker, embedder-writing, or store-writing code.

## 4. Interfaces (the contracts tests are written against)

```python
# --- Generator ---
class Generator(Protocol):
    def generate(self, messages: list[dict]) -> str:
        """Send chat messages, return the model's text response."""
        ...

# --- Re-ranker ---
class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score each text against the query. Higher = more relevant."""
        ...

# --- Tool executor ---
class ToolExecutor(Protocol):
    def execute(self, tool: str, args: dict) -> str:
        """Run a validated tool and return its text output."""
        ...

# --- Citation checker ---
@dataclass(frozen=True)
class CitationResult:
    outcome: str          # "F" (cited) or "G" (flagged)
    sources: list         # SourceEntry objects with verification status
    unverified: list      # indices of unverified sources
    answer_text: str      # original answer text
    banner: str | None    # warning banner text if G, else None

# --- Query result ---
@dataclass(frozen=True)
class QueryResult:
    answer: str
    sources: list              # SourceEntry objects
    citation_outcome: str      # "F" or "G"
    stale_index: bool
    stale_message: str
    audit_log: dict
```

Production code depends only on these protocols. Tests supply a `StubGenerator` (canned responses), a `StubReranker` (deterministic scoring), and the existing `StubEmbedder` from Sprint 1.

## 5. Key design decisions

**D1. Query embedding reuses the offline embedder.** The online pipeline instantiates the same `CodeEmbedder` (or `StubEmbedder` in tests) and calls `embed([question])`. This guarantees Article II.4 (same model and revision). The embedder identity is checked against the index metadata by `open_index` (already built in Sprint 1).

**D2. RRF merge is a pure function.** Input: two ranked lists of `(chunk_id, rank)`. Output: a single list of `(chunk_id, rrf_score)` sorted descending. A chunk appearing in both lists gets the sum of its two contributions. The RRF constant and k values are parameters, never hard-coded.

```python
def rrf_merge(vector_hits, keyword_hits, *, k=50, constant=60):
    scores = {}
    for rank, cid in enumerate(vector_hits):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (constant + rank)
    for rank, cid in enumerate(keyword_hits):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (constant + rank)
    return sorted(scores, key=scores.get, reverse=True)[:k]
```

**D3. Context assembly.** Each chunk is formatted as a block:

```
--- File: src/auth/client.py, lines 42-58 (language: python, indexed at a1b2c3d) ---
def authenticate(user, password):
    ...
```

The generator receives these blocks as the `user` message content, preceded by a system message. No raw vectors, no chunk ids in the prompt (Article IV.4).

**D4. Context budgeting.** The context budget (in tokens) is `context_window - system_prompt_tokens - generation_reserve`. Chunks are added in re-ranker-score order until the budget would be exceeded; remaining chunks are dropped. The token count uses the embedder's tokenizer (shared, already loaded). `generation_reserve` is a profile setting (default: 1024 tokens for the response).

**D5. Tool-call format.** The system prompt instructs the model to use:

```
<tool>git_blame(path="src/auth/client.py", lines="42-58")</tool>
<tool>git_log(path="src/auth/client.py", n=10)</tool>
```

The harness uses a regex to extract tool calls. If no `<tool>...</tool>` block is found, the response is treated as a final answer. If the format is malformed, it is also treated as a final answer (no crash). The harness never relies on server-side tool-call features (Article VIII.2).

**D6. Tool argument validation.** Before execution:
1. `path` must be repo-relative, must not contain `..`, must not start with `/`, must not contain shell metacharacters (`; | & $ \` \\ ( )`).
2. `lines` (if present) must be a valid range (`N` or `N-M` where N ≤ M).
3. The path must exist in the repository at the indexed commit.
4. Rejected arguments produce a tool-error message appended to context (the model sees the rejection and can try differently).

**D7. Tool execution.** Both tools run via `subprocess.run` with `capture_output=True`, `shell=False`, `cwd=repo_path`, and a timeout. The harness builds the argument list; the model never controls the command line.

- `git blame`: `git blame -L <start>,<end> <commit> -- <path>` (or without `-L` for the whole file).
- `git log`: `git log --format=format:"%H %an %ad %s" --date=short -n <limit> <commit> -- <path>`.

**D8. Tool-result caching.** A per-`ask`-call dictionary keyed by `(tool_name, frozen_args)`. On cache hit, the result is reused and the log records `cache_hit=True`. The cache is discarded after the `ask` call returns.

**D9. Citation checker algorithm.**
1. Parse the `Sources` section from the answer text using regex.
2. For each source entry:
   - **Code source** `[N] path, lines X-Y (indexed at hash)`: verify that a chunk with a matching `file_path` and overlapping `[start_line, end_line]` range exists in the retrieved context, and that the 7-char commit hash prefix matches the indexed commit.
   - **Commit source** `[N] Commit hash, "subject", author, date`: verify that a tool result contains output referencing this commit hash.
3. For each inline marker `[N]` in the answer body, verify that a corresponding `[N]` entry exists in `Sources`.
4. If all pass → outcome F. If any fail → outcome G, with per-source verification status.

**D10. Harness-copied commit metadata (Article VI.4).** When the answer contains a commit source, the harness replaces the model's subject/author/date with the values parsed from the `git log` tool result. This prevents the model from fabricating commit details. If the commit hash is not found in any tool result, the source is marked unverified.

**D11. Flagged-answer rendering (Article VI.3).**
- **Banner:** `⚠ WARNING: Some citations in this answer could not be verified against the retrieved evidence. Verify the marked sources manually.`
- **Per-source mark:** unverified entries are prefixed with `[UNVERIFIED]`.
- Flagged answers are never rendered identically to cited answers (the banner is always present for G outcomes).

**D12. Stale-index fallback.** If `ensure_current` returns `ok=False`:
- Set `stale_flag=True` on the `QueryResult`.
- If the index exists (`status != "empty"`), proceed with retrieval from the existing index.
- Prepend a stale warning to the output: `⚠ WARNING: The index may be out of date. The answer below is based on an older version of the codebase.`
- If the index is empty, return an answer saying no evidence is available.

**D13. llama-server integration.** The `LlamaServerGenerator` class:
1. Connects to `http://127.0.0.1:<port>/v1/chat/completions` (OpenAI-compatible endpoint).
2. Sends messages in the chat format the model expects (Qwen2.5 uses ChatML).
3. Sets `temperature`, `max_tokens`, `stop` tokens from the profile.
4. Parses the response JSON and returns the assistant message content.
5. A `health_check()` method pings `/health` before the first query.
6. Timeout on HTTP calls (configurable, default 120s for generation).

**D14. System prompt.** A minimal, functional prompt (prompt engineering deferred per Article VII.1):

```
You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository.

Rules:
1. Cite every claim with numbered markers [1], [2], etc.
2. End with a Sources section listing each citation.
   - Code: [N] file/path.py, lines X-Y (indexed at <7-char hash>)
   - Commit: [N] Commit <7-char hash>, "<subject>", <author>, <date>
3. If you need commit history to explain WHY code exists, request a tool:
   <tool>git_blame(path="file/path.py", lines="X-Y")</tool>
   <tool>git_log(path="file/path.py", n=10)</tool>
4. If the evidence is insufficient, say what you could not determine.
   Do NOT guess or make up file names, line numbers, or commit hashes.
```

## 6. Optimisations

| # | Optimisation | Saves | Must not break |
|---|---|---|---|
| O1 | **Lazy embedder loading:** the query embedder loads only when needed (not when `ensure_current` takes the fast path and the index is current) | Model load time on cache-hit questions | AC-2.2 (same model) |
| O2 | **Single embedder instance:** reuse the same embedder for query embedding and (if `ensure_current` triggers indexing) the indexing run | Memory (no duplicate model) | Article II.4 |
| O3 | **Batch re-ranking:** send all shortlist chunks in one call to the cross-encoder | Round-trip overhead | AC-2.7 (shortlist only) |
| O4 | **Early budget check:** if the question alone exceeds the context budget, fail fast | Wasted retrieval and generation | AC-2.6 |

## 7. Configuration

Online-specific additions to `codecompass.toml`:

```toml
[retrieval]
vector_k = 50
keyword_k = 50
rrf_constant = 60
rerank_k = 50
final_k = 8

[reranker]
model = "BAAI/bge-reranker-v2-m3"
device = "cpu"     # or "cuda", "mps"

[generator]
default_profile = "dev"
server_url = "http://127.0.0.1:8080"
timeout_seconds = 120
generation_reserve_tokens = 1024

[generator.profiles.dev]
model_id = "Qwen2.5-Coder-14B-Instruct"
gguf_file = ""           # set by the user
gguf_checksum = ""       # SHA-256
quantisation = "Q4_K_M"
context_window = 32768
temperature = 0.1
max_tokens = 2048
stop_tokens = ["<|im_end|>", "<|endoftext|>"]

[generator.profiles.prod]
model_id = "Qwen2.5-Coder-32B-Instruct"
gguf_file = ""
gguf_checksum = ""
quantisation = "Q4_K_M"
context_window = 32768
temperature = 0.1
max_tokens = 2048
stop_tokens = ["<|im_end|>", "<|endoftext|>"]

[tools]
max_verifier_rounds = 3
git_log_limit = 20
git_blame_timeout = 30
git_log_timeout = 30
allowed_tools = ["git_blame", "git_log"]

[logging]
query_log_dir = ""   # default: <index_dir>/queries/
```

## 8. Spec coverage map

| Spec items | Built in | Verified by |
|---|---|---|
| AC-1.x grounded answer | `agent/harness`, `citation/checker`, `context` | integration (stub generator with canned responses) |
| AC-2.x hybrid retrieval | `retrieval/*`, `rrf.py`, `reranker.py` | unit (RRF scoring, dedup), integration (real stores, stub embedder) |
| AC-3.x verifier tools | `agent/tools`, `agent/tool_parser`, `agent/cache`, `agent/harness` | unit (validation, parsing, caching), integration (round limit, allow list) |
| AC-4.x citation integrity | `citation/checker`, `citation/parser`, `citation/formatter` | unit (all F/G edge cases), integration |
| AC-5.x generator | `generator/llama`, `generator/profiles`, `generator/server` | unit (profile loading, HTTP mocking), `model`-marked (real server) |
| AC-6.x index freshness | `__init__.ask` (calls `ensure_current`) | integration (mock failure → stale flag) |
| AC-7.x audit logging | `logging.py` | unit and integration (log content assertions) |
| AC-8.x CLI | `cli.py` | CLI smoke test |
| AC-9.x API | `__init__.ask` | unit (return structure) |

## 9. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Qwen2.5 does not reliably produce the `<tool>...</tool>` format | Failing test first; fallback: treat any response without a tool tag as a final answer; prompt iteration after eval set exists |
| R2 | Cross-encoder model is too large for CI or dev machines | Use `StubReranker` in required tests; `model`-marked test for real reranker; document minimum RAM |
| R3 | llama-server API changes across releases | Pin the llama.cpp release; test against the pinned version |
| R4 | Citation checker false positives (valid citations rejected) | Generous matching: 7-char prefix for commits, overlapping line ranges for code; exhaustive unit tests |
| R5 | Context budget miscalculation (too many/few chunks) | Token counting uses the embedder's tokenizer (same as chunking); unit test with known token counts |
| R6 | Tool timeout on large repos (blame/log on big files) | Configurable timeout per tool; timeout produces an error message in context, not a crash |

## 10. Build order (each slice starts with failing tests, Article IX.3)

| Slice | Delivers | Main ACs |
|---|---|---|
| S0 | Online package skeleton, online config loader, `StubGenerator`, `StubReranker`, extended fixture repo (meaningful commit messages) | none (enables the rest) |
| S1 | RRF merge: pure function, scoring, deduplication, configurable k and constant | 2.3, 2.4, 2.5 |
| S2 | Query embedding (reuse offline embedder), vector search wrapper, keyword search wrapper | 2.1, 2.2 |
| S3 | Cross-encoder re-ranker: `RerankerProtocol`, `StubReranker`, `BgeReranker` | 2.7 |
| S4 | Context assembly: format chunks as plain text, context budgeting, final_k capping | 1.4, 2.6 |
| S5 | Tool argument validation, tool executors (`git_blame`, `git_log`), tool-result caching | 3.2, 3.3, 3.4, 3.5 |
| S6 | Tool-call parser (from model text output) | 3.8 |
| S7 | Generator: `LlamaServerGenerator`, model profiles, health check, HTTP client | 5.1–5.11 |
| S8 | Agent harness: round counting, message building, tool dispatch, round limit enforcement | 3.1, 3.6, 3.7 |
| S9 | Citation checker: source parser, F/G checker, formatter, harness-copied commit metadata | 4.1–4.7 |
| S10 | Index freshness: `ensure_current` integration, stale-index fallback | 6.1–6.3 |
| S11 | Audit logging: per-query structured log | 7.1–7.3 |
| S12 | Public `ask` API, CLI entry point | 8.1–8.4, 9.1, 9.2 |
| S13 | Real generator and real re-ranker `model`-marked tests | end-to-end smoke |

## 11. Constitution check

| Article | Compliance |
|---|---|
| I | Generator prompted to ground in context; "could not determine" when evidence is insufficient; citation checker enforces traceability |
| II | Online imports only the four public offline exports; embedder identity checked by `open_index`; no scanner/chunker/writer imports |
| III | `ensure_current` called before every `ask`; failure → stale flag, not hang; existing index stays usable |
| IV | Both search paths, RRF merge with rank-only scores, cross-encoder on shortlist, configurable k values |
| V | `MAX_VERIFIER_ROUNDS = 3`, allow-listed tools, validated args, cached results, per-query log |
| VI | Deterministic checker, F/G outcomes, fixed format, harness-copied commit metadata, non-bypassable in production |
| VIII | llama.cpp only, switchable profiles, pinned GGUF, localhost, no mlx-lm, all config; hardware-independent required tests |
| IX | Every slice starts with failing tests; required suite needs no GPU/network/model; stub generator and reranker |
| X | Citations as navigable references; stale warnings; "no rationale found" honesty; local-only default |
| XI | No new components beyond constitution requirements; one pipeline, one entry point |

No conflicts found.

## 12. Next

Turn section 10 into a **task list**: each task names its failing tests first, the ACs it satisfies, and its definition of done.
