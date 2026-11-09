# Sample runs (eval-v1, RAG + tools)

Five answers from the official `rag_tools` run, one for each outcome a developer can see. Each answer is copied verbatim from the committed results file by a script; nothing was edited.

| | |
|---|---|
| **Source** | [`eval/results/llm-rag_tools-20261109T011140Z.json`](../../eval/results/llm-rag_tools-20261109T011140Z.json) |
| **System** | CodeCompass `eval-v1` (`c6fa1b7`), Flask at `85c5d93` |
| **Model** | Qwen2.5-Coder-14B-Instruct Q4_K_M, `dev` profile (32k context), llama.cpp b11960, RTX 3090 |
| **Settings** | `eval/codecompass.eval.toml`: 50 + 50 retrieved, RRF, 50 re-ranked, 8 sent, up to 3 tool rounds, documentation fallback off |
| **Grades** | Final values from [`sheet-merged.csv`](../../eval/results/grading-20261109T012724Z/sheet-merged.csv), settled by two graders |

Each results record holds what the per-query audit log holds (retrieved chunks with scores, every tool call with round, arguments and cache hit, per-stage timings) plus the full messages the model saw. The audit log files themselves stayed on the cluster; the `log_file` path is recorded in each record.

| # | Question | Outcome | Graded row |
|---|---|---|---|
| 1 | `core-localisation-02` | F: every citation verified | R18 |
| 2 | `core-runtime-behaviour-07` | G: format slip (nothing fabricated) | R52 |
| 3 | `swe-qa-flask-06` | G: H1, a citation that matches nothing in context | R35 |
| 4 | `swe-qa-flask-03` | Abstention: stopped by the evidence gate | not in the graded subset |
| 5 | `core-unanswerable-08` | Abstention on an unanswerable control, round limit reached | R07 |

---

## 1. F: every citation verified

**Question** (`core-localisation-02`, localisation, simple): Where is the default session interface, `SecureCookieSessionInterface`, defined?

**Checker outcome:** F. Unverified entries: none. Not referenced in the text: none. Round limit reached: no.

**Human grade (R18):** H2 no, H3 n/a, score 2 of 2, reason none.

**What happened:** The model opened the file with `open_file`, cited the lines it read, and the checker matched the entry to code in its context. Shown with no warning.

**Answer as shown to the developer:**

````text
The default session interface, `SecureCookieSessionInterface`, is defined in the `src/flask/sessions.py` file, lines 298-316 [1].

Sources
[1] src/flask/sessions.py, lines 298-316 (indexed at 85c5d93)
````

**Tool calls:**

| Round | Tool | Arguments | Cache | Result (first line) |
|---|---|---|---|---|
| 0 | `open_file` | path=`src/flask/sessions.py`, lines=`298-316` | miss | --- src/flask/sessions.py, lines 298-316 (indexed at 85c5d93) \| python --- |

**Timings:** ensure_current 0.01 s, retrieval 0.03 s, reranking 0.38 s, generation 2.66 s, tool_execution 0.03 s, citation_check 0.00 s, total 3.14 s.

**Retrieved:** 50 chunks shortlisted, 8 sent to the model.

---

## 2. G: format slip (nothing fabricated)

**Question** (`core-runtime-behaviour-07`, runtime-behaviour, code-tracing): What happens when a view calls `abort(404)`, and how does it reach the registered error handler?

**Checker outcome:** G. Unverified entries: [1]. Not referenced in the text: [1]. Round limit reached: no.

**Human grade (R52):** H2 no, H3 n/a, score 1 of 2, reason none.

**What happened:** The only `Sources` entry matches a retrieved chunk, but the model never wrote `[1]` in the text, so the entry is marked `[NOT REFERENCED IN ANSWER]`, every statement is marked `(not cited)`, and a warning banner is shown. Counted as a format slip, not H1. This is the most common failure (56 of 88 answers in this configuration).

**Answer as shown to the developer:**

````text
⚠ WARNING: Sources are listed, but the answer does not say which statement each one supports. Check them yourself before relying on the answer.

Note: Some statements in this answer are not supported by a citation. They are marked (not cited). Verify them against the source code before relying on them.

When a view calls `abort(404)`, Flask raises a `NotFound` exception. This exception is caught by the registered error handler for 404 errors. The error handler then returns a response with the status code 404 and the message "not found". (not cited)

In the provided code context, the error handler for 404 errors is defined as follows:

```python
@app.errorhandler(404)
def not_found(e):
    return "not found", 404
```

This handler is registered in the `test_error_handling` function within `tests/test_basic.py`. (not cited)

Sources
[NOT REFERENCED IN ANSWER] [1] tests/test_basic.py, lines 867-902 (indexed at 85c5d93)
````

**Tool calls:**

| Round | Tool | Arguments | Cache | Result (first line) |
|---|---|---|---|---|
| 0 | `search_again` | query=`flask abort 404 error handling` | miss | --- tests/test_basic.py, lines 937-948 (indexed at 85c5d93) \| python --- |

**Timings:** ensure_current 0.01 s, retrieval 0.03 s, reranking 0.41 s, generation 3.53 s, tool_execution 0.30 s, citation_check 0.00 s, total 4.31 s.

**Retrieved:** 50 chunks shortlisted, 8 sent to the model.

---

## 3. G: H1, a citation that matches nothing in context

**Question** (`swe-qa-flask-06`, architectural, code-tracing): What mechanisms ensure that template processing functions registered during modular component registration are accessible when templates are rendered using the shared template environment?

**Checker outcome:** G. Unverified entries: [1, 2]. Not referenced in the text: [2]. Round limit reached: no.

**Human grade (R35):** H2 yes, H3 n/a, score 0 of 2, reason unsupported.

**What happened:** Entry [1] cites `src/flask/sansio/app.py` lines 506-532, which were not in the model's context, so the checker marks it `[UNVERIFIED]`. One of the 2 H1 answers in this configuration. The graders also judged the content unsupported (H2); the settling notes record that it describes context processors, not the template filters the question is about.

**Answer as shown to the developer:**

````text
⚠ WARNING: Some citations in this answer could not be verified against the retrieved evidence. Verify the marked sources manually.

Note: Some statements in this answer are not supported by a citation. They are marked (not cited). Verify them against the source code before relying on them.

The mechanisms ensuring that template processing functions registered during modular component registration are accessible when templates are rendered using the shared template environment are as follows:

1. **Blueprint Context Processors**: When a blueprint is registered, any context processors defined within that blueprint are stored in the `self.template_context_processors` dictionary of the blueprint. This dictionary maps blueprint names to lists of context processor functions. (not cited)

2. **App Context Processors**: Similarly, context processors defined at the application level are stored in the `self.template_context_processors` dictionary of the Flask app object. These are associated with the key `None`, indicating they are global to the entire application. (not cited)

3. **Template Rendering**: When a template is rendered, the `update_template_context` method of the Flask app is called. This method iterates over the context processors registered for the current request's blueprint and the global context processors. (not cited)

4. **Context Update**: For each context processor, the method calls the processor function and updates the template context with the values returned by the function. This ensures that all registered context processors contribute their values to the template context. (not cited)

5. **Precedence Handling**: The original context values are preserved and re-applied after all context functions have been processed, ensuring that values passed directly to `render_template` take precedence over those provided by context processors. (not cited)

Sources
[UNVERIFIED] [1] src/flask/sansio/app.py, lines 506-532 (indexed at 85c5d93)
[NOT REFERENCED IN ANSWER] [2] tests/test_blueprints.py, lines 634-672 (indexed at 85c5d93)
````

**Tool calls:**

| Round | Tool | Arguments | Cache | Result (first line) |
|---|---|---|---|---|
| 0 | `search_again` | query=`template processing functions registration, shared template environment` | miss | --- tests/test_blueprints.py, lines 634-672 (indexed at 85c5d93) \| python --- |

**Timings:** ensure_current 0.01 s, retrieval 0.03 s, reranking 0.38 s, generation 6.71 s, tool_execution 0.35 s, citation_check 0.00 s, total 7.52 s.

**Retrieved:** 50 chunks shortlisted, 8 sent to the model.

---

## 4. Abstention: stopped by the evidence gate

**Question** (`swe-qa-flask-03`, architectural, simple): What is the modular component registration architecture that separates static asset serving from the main application framework while preserving consistent caching behavior across both components?

**Checker outcome:** G. Unverified entries: none. Not referenced in the text: none. Round limit reached: no.

**What happened:** The top retrieval score was below the evidence gate (`min_top_score` 0.02), so the generator was never called (generation 0.0 s). The closest files are listed as leads, explicitly not as evidence. This question is answerable (it comes from SWE-QA and has a reference answer), so the refusal is honest but a missed answer: the gate tends to stop questions that name no file or function, like this one, which is a limitation of the system. The checker outcome is G only because an answer citing nothing is never F (Article VI.3); it is shown with the uncited note, not the warning banner.

**Answer as shown to the developer:**

````text
Note: This answer is not supported by any citation from the repository. Verify it against the source code before relying on it.

I could not find enough evidence in the indexed code to answer this question.

Closest matches found (these are not evidence for an answer; check them yourself):
- tests/test_blueprints.py, lines 176-220
- src/flask/testing.py, lines 204-247
- src/flask/sansio/blueprints.py, lines 119-163
````

**Tool calls:**

No tool calls.

**Timings:** ensure_current 0.01 s, retrieval 0.03 s, reranking 0.39 s, generation 0.00 s, tool_execution 0.00 s, citation_check 0.00 s, total 0.45 s.

**Retrieved:** 50 chunks shortlisted, 0 sent to the model.

---

## 5. Abstention on an unanswerable control, round limit reached

**Question** (`core-unanswerable-08`, unanswerable, simple): Which companies are paying to sponsor Flask's development?

**Checker outcome:** G. Unverified entries: none. Not referenced in the text: none. Round limit reached: yes.

**Human grade (R07):** H2 no, H3 no, score 2 of 2, reason none.

**What happened:** The model repeated the same `search_again` call; rounds 1 and 2 were served from the cache (`repeat_of: 0`). After 3 tool rounds the harness ignored the next tool request and made one final answer-only call (Article V.1). The model then said it could not determine the answer, which is correct for this control. As in example 4, G only means the answer cites nothing; it is not H1.

**Answer as shown to the developer:**

````text
Note: This answer is not supported by any citation from the repository. Verify it against the source code before relying on it.

Based on the provided code context, there is no information about which companies are sponsoring Flask's development. The code snippets are primarily related to Flask's configuration, documentation, and testing. The context does not include any details about funding or sponsorship.

I could not determine which companies are paying to sponsor Flask's development from the given code context.
````

**Tool calls:**

| Round | Tool | Arguments | Cache | Result (first line) |
|---|---|---|---|---|
| 0 | `search_again` | query=`Flask sponsors` | miss | --- tests/test_regression.py, lines 1-1 (indexed at 85c5d93) \| python --- |
| 1 | `search_again` | query=`Flask sponsors` | hit | already run in round 0 |
| 2 | `search_again` | query=`Flask sponsors` | hit | already run in round 0 |
| 3 | final answer-only call | 1 tool request ignored | | |

**Timings:** ensure_current 0.01 s, retrieval 0.03 s, reranking 0.73 s, generation 6.60 s, tool_execution 0.30 s, citation_check 0.00 s, total 7.70 s.

**Retrieved:** 50 chunks shortlisted, 8 sent to the model.
