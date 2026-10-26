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
  │     │     ├─ tool call? → validate args → execute at indexed commit → cap output → cache → log → append to messages → round++ → loop if round < 3
  │     │     └─ answer? → break
  │     └─ round == 3 and still a tool request? → one final generate call with tools disabled (D15)
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
| Query embedder | Same `jinaai/jina-embeddings-v2-base-code` as indexing | Bound to the index handles: `open_index(..., embedder=)` then `handles.embed_query` (Article II.2, II.4; §3) |
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
    embedder.py      query embedding via handles.embed_query (no offline internals)
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

**Boundary rule (Article II.2):** the online package imports from `codecompass.offline` only through its public API (`__all__`: `ensure_current`, `status`, `open_index`, `check_consistency`). It never imports scanner, chunker, embedder-writing, or store-writing code. Result types (`EnsureResult`, `IndexHandles`, `IndexStatus`) are used as the return values of those functions, not imported.

**Resolved: query embedder access** (PR `fix/query-embedder`). D1 originally reused `CodeEmbedder` from `codecompass.offline.embedding`, which is not part of the public API. Resolution, as proposed here: the handles returned by `open_index` gain an `embed_query(text) -> list[float]` method backed by an embedder whose identity `open_index` has already checked against the index metadata. Query embedding then goes through the public API, and Article II.4 (same embedder) holds by construction rather than by convention. Implemented as `open_index(repo, *, config, index_dir=None, embedder=None)`: with no embedder it builds the pinned `CodeEmbedder` from config (the model loads on first `embed_query`); tests pass a `StubEmbedder`. It raises `EmbedderMismatchError` unless the config's embedder **and** the embedder instance both match the index metadata (strict rule, chosen so the config can never name one model while another is used). Tests: `tests/offline/test_query_embedder.py`. The change to Sprint 1 code is reviewed in that PR.

## 4. Interfaces (the contracts tests are written against)

```python
# --- Generator ---
class Generator(Protocol):
    def generate(self, messages: list[dict]) -> str:
        """Send chat messages, return the model's text response."""
        ...
    def count_tokens(self, text: str) -> int:
        """Token count in the generator's own tokenizer (context budgeting, D4)."""
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

**D1. Query embedding uses the index's own embedder.** The query is embedded by the same embedder model and revision as the index (Article II.4), obtained through the offline public API: `open_index(..., embedder=)` returns handles whose `embed_query(question)` uses an embedder already checked against the index (§3). Tests inject `StubEmbedder`. The same instance is passed to `ensure_current(embedder=)` (O2). The embedder is loaded once per process and reused across questions.

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
--- src/auth/client.py, lines 42-58 (indexed at a1b2c3d) | python ---
def authenticate(user, password):
    ...
```

The header text before ` | ` is exactly the code-citation form required in `Sources` (Article VI.4), so the model cites a chunk by copying its header and never has to recompute line numbers. Citing a whole chunk is always valid under D9.

The generator receives these blocks as the `user` message content, preceded by a system message. No raw vectors, no chunk ids in the prompt (Article IV.4).

**D4. Context budgeting.** The budget covers the whole conversation, including the tool rounds that come after the chunks, not only the first prompt:

```
budget = context_window - max_tokens - tokens(system prompt + question)
chunk_budget = budget - MAX_VERIFIER_ROUNDS * max_tool_output_tokens
```

1. Chunks are added in re-ranker-score order while they fit in `chunk_budget`; the rest are dropped. `final_k` is therefore capped by the budget (AC-2.6).
2. Each tool result is truncated to `max_tool_output_tokens` before it is appended, ending with a visible `[output truncated: N more lines]` line so the model knows it is partial. Together with step 1, the conversation can never exceed the context window, whatever the tools return.
3. The reserve for the answer is the profile's `max_tokens`. A separate, smaller `generation_reserve_tokens` would let a long answer overflow the window, so that key is retired (it is not covered by an approved test).
4. Token counts come from the generator interface (`Generator.count_tokens`), because the budget is measured in the generator's tokens, which differ from the embedder's. `LlamaServerGenerator` calls llama-server's `/tokenize` endpoint; `StubGenerator` counts whitespace-separated tokens so tests stay model-free.

Example for an 8192-token profile (window 8192, `max_tokens` 2048, three tool results of 768): about 3,500 tokens remain for chunks, so 6-7 chunks of the 512-token target fit.

**D5. Tool-call format.** The system prompt instructs the model to use:

```
<tool>git_blame(path="src/auth/client.py", lines="42-58")</tool>
<tool>git_log(path="src/auth/client.py", n=10)</tool>
```

The harness uses a regex to extract tool calls. If no `<tool>...</tool>` block is found, the response is treated as a final answer. If the format is malformed, it is also treated as a final answer (no crash). The harness never relies on server-side tool-call features (Article VIII.2).

**D6. Tool argument validation.** Before execution:
1. `path` is normalised (`posixpath.normpath`) and must be repo-relative: not absolute, not starting with `-`, and with no `..` component.
2. The path must exist as a file in the git tree at the indexed commit. This one check also rejects anything outside the repository, so no character blacklist is needed: commands run with `shell=False` and pass `--` before the path, so shell metacharacters are inert. Real file names such as `app/(auth)/page.tsx` or `Outer$Inner.java` must stay valid.
3. `lines` (if present) must be `N` or `N-M` with `1 ≤ N ≤ M ≤` the file's line count at the indexed commit.
4. `n` (git_log) must be an integer from 1 to `git_log_limit`.
5. Rejected arguments produce a tool-error message appended to context (the model sees the rejection and can try differently). A rejected call still uses up its round, so a model that keeps sending bad calls still terminates (Article V.1).

**D7. Tool execution.** Both tools run via `subprocess.run` with `capture_output=True`, `shell=False`, `cwd=repo_path`, and a timeout. The harness builds the argument list; the model never controls the command line.

- `git blame`: `git blame --porcelain -L <start>,<end> <indexed_commit> -- <path>` (or without `-L` for the whole file). Porcelain output carries each commit's full hash, author, author time and summary, so D10 can copy commit metadata from blame results, not only from log results.
- `git log`: `git log --format=%H%x1f%an%x1f%ad%x1f%s --date=short -n <n> <indexed_commit> -- <path>`. Fields are separated by the unit-separator byte (0x1F), which cannot occur in names or subjects, so parsing is exact even though author names contain spaces.

Both tools run against the **indexed commit**, not HEAD, so blame line numbers always match the retrieved chunks, including when the index is stale (D12).

The executor parses each result into commit records (full hash, author, date, subject) kept on the `ToolResult`, and renders a compact text form for the context: one line per commit (`<7-char hash> <date> <author> "<subject>"`), plus the blamed line ranges for blame. The parsed records are what D9 and D10 match against; the rendered text is what the model sees and what D4 caps.

**D8. Tool-result caching.** A per-`ask`-call dictionary keyed by `(tool_name, frozen_args)`. On cache hit, the result is reused and the log records `cache_hit=True`. The cache is discarded after the `ask` call returns.

**D9. Citation checker algorithm.**
1. Parse the `Sources` section from the answer text using regex.
2. For each source entry:
   - **Code source** `[N] path, lines X-Y (indexed at hash)`: verify that every line from X to Y is covered by retrieved chunks with the same `file_path` (the union of their line ranges contains `[X, Y]`), and that the 7-char hash equals the indexed commit's prefix. Overlap is not enough: a citation of lines 1-500 that overlaps a chunk at 42-58 would point the reader at code the model never saw (Articles I.1, VI.1).
   - **Commit source** `[N] Commit hash, "subject", author, date`: verify that the 7-char hash is a prefix of a commit record parsed from a tool result (D7), not merely a substring of some tool output.
3. Markers and entries must match both ways: every inline marker `[N]` has a `Sources` entry, and every entry is referenced by a marker.
4. If all pass → outcome F. If any fail → outcome G, with per-source verification status.

**D10. Harness-copied commit metadata (Article VI.4).** When the answer contains a commit source, the harness replaces the model's subject/author/date with the values from the matching commit record parsed from a `git log` or `git blame --porcelain` tool result (D7). This prevents the model from fabricating commit details. If the commit hash is not found in any tool result, the source is marked unverified.

**D11. Flagged-answer rendering (Article VI.3).**
- **Banner:** `⚠ WARNING: Some citations in this answer could not be verified against the retrieved evidence. Verify the marked sources manually.`
- **Per-source mark:** unverified entries are prefixed with `[UNVERIFIED]`.
- Flagged answers are never rendered identically to cited answers (the banner is always present for G outcomes).

**D12. Stale-index fallback.** If `ensure_current` returns `ok=False`, whatever the status (`failed` or `locked`); the code checks `ok`, never a specific status string:
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
7. Sends the profile's `seed` with every request, so runs are reproducible where the server supports it (Article VII.6).
8. `health_check()` also reads `/props` and fails loudly when the server cannot serve the active profile: the per-slot context (`default_generation_settings.n_ctx`) must be at least the profile's `context_window`, and when `gguf_file` is set the loaded model path must end with it. The server is started by hand (spec C9), so this is the only point where the pinned profile is checked against what is actually running.
9. `count_tokens(text)` calls `/tokenize` (used by D4).

**D14. System prompt.** A minimal, functional prompt (prompt engineering deferred per Article VII.1):

```
You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository.

Rules:
1. Cite every claim with numbered markers [1], [2], etc.
2. End with a Sources section listing each citation. For code, copy the
   chunk's header line exactly (the part before " | ").
   - Code: [N] file/path.py, lines X-Y (indexed at <7-char hash>)
   - Commit: [N] Commit <7-char hash>, "<subject>", <author>, <date>
3. If you need commit history to explain WHY code exists, request a tool:
   <tool>git_blame(path="file/path.py", lines="X-Y")</tool>
   <tool>git_log(path="file/path.py", n=10)</tool>
4. If the evidence is insufficient, say what you could not determine.
   Do NOT guess or make up file names, line numbers, or commit hashes.
```

**D15. Round limit (Article V.1).** One tool call executes per round: the first `<tool>` block in a response; any later blocks are ignored and logged. Rounds count from 0 and the loop continues while `round < MAX_VERIFIER_ROUNDS`. If the response after the third tool result is still a tool request, the harness makes **one final** generate call, adding a message that no more tools are available and an answer is required. Any `<tool>` block in that final response is removed, and the remaining text goes to the citation checker. A question therefore makes at most 3 tool executions and at most 4 generator calls. The earlier design passed the last response to the checker as the answer, but that response is a tool request, not an answer.

## 6. Optimisations

| # | Optimisation | Saves | Must not break |
|---|---|---|---|
| O1 | **Load models once per process:** the embedder, re-ranker and generator client are created once and reused across questions; `ensure_current`'s fast path loads none of them | Model load time on every question after the first | AC-2.2 (same model) |
| O2 | **Single embedder instance:** reuse the same embedder for query embedding and (if `ensure_current` triggers indexing) the indexing run | Memory (no duplicate model) | Article II.4 |
| O3 | **Batch re-ranking:** send all shortlist chunks in one call to the cross-encoder | Round-trip overhead | AC-2.7 (shortlist only) |
| O4 | **Early budget check:** if the question alone exceeds the context budget, fail fast | Wasted retrieval and generation | AC-2.6 |
| O5 | **Compact tool output:** tools return parsed commit records rendered as one line per commit, not raw porcelain (D7) | Context tokens in every tool round | AC-3.5 (results still citable) |

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
llama_cpp_release = ""   # pinned llama.cpp release in use (Article VIII.2)

[generator.profiles.dev]
model_id = "Qwen2.5-Coder-14B-Instruct"
backend = "llama.cpp"    # the only allowed value (Article VIII.4)
gguf_file = ""           # set by the user
gguf_checksum = ""       # SHA-256
quantisation = "Q4_K_M"
context_window = 32768
server_args = []         # extra llama-server launch flags, e.g. ["-ngl", "99"]
temperature = 0.1
seed = 42
max_tokens = 2048
stop_tokens = ["<|im_end|>", "<|endoftext|>"]

[generator.profiles.prod]
model_id = "Qwen2.5-Coder-32B-Instruct"
backend = "llama.cpp"
gguf_file = ""
gguf_checksum = ""
quantisation = "Q4_K_M"
context_window = 32768
server_args = []
temperature = 0.1
seed = 42
max_tokens = 2048
stop_tokens = ["<|im_end|>", "<|endoftext|>"]

[tools]
git_log_limit = 20
git_blame_timeout = 30
git_log_timeout = 30
max_tool_output_tokens = 768

[logging]
query_log_dir = ""   # default: <index_dir>/queries/
```

`generator/server.py` builds the documented `llama-server` launch command from the active profile (`-m`, `-c context_window`, `--host 127.0.0.1`, the port from `server_url`, then `server_args`), so the context size the server runs with comes from the same config the pipeline budgets against (AC-5.10).

**[NEEDS CLARIFICATION] Round limit and tool list in config.** `config.py` currently lets `codecompass.toml` override `tools.max_verifier_rounds` and `tools.allowed_tools`. Article V.1 makes the round limit a named constant changed only by amendment, and V.2 fixes the tool list, so both should be module constants (`MAX_VERIFIER_ROUNDS`, `ALLOWED_TOOLS`) and the keys removed from `[tools]` as shown above. The approved T0.1 test `test_max_verifier_rounds_and_tools_config` reads them from config, so this change needs reviewer sign-off before the test is updated (Article IX.3).

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
| R4 | Citation checker false positives (valid citations rejected) | Exact matching on the fixed format, never loosened to "overlap": copying a chunk header (D3) is always valid, so strict containment does not penalise a well-behaved model; unit tests cover boundary lines and citations spanning two adjacent chunks |
| R5 | Context budget miscalculation (too many/few chunks) | Tokens counted by the generator's own tokenizer (`/tokenize`); tool output capped and pre-reserved (D4); unit tests with known token counts |
| R7 | The running `llama-server` does not match the profile (wrong `-c` or model file) | `health_check()` compares `/props` with the profile and fails loudly (D13); launch command generated from the profile |
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
| II | Online imports only the four public offline exports; the query embedder is bound to the handles, with config and instance identity checked by `open_index`; no scanner/chunker/writer imports |
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
