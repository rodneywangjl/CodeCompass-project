# Complexity tagging: second-tagger agreement (Spec 003 AC-3.1, AC-3.2)

**Status:** decisions agreed by Nicole and Kelsey, 2026-11-08. One runtime-behaviour question is being replaced (see AC-1.4 below).

Rule: `docs/specs/003-evaluation/tagging-rule.md`. Tags: `simple` or `code-tracing`.

## Who tagged what

| Questions | First tag | Second tag (blind) |
|---|---|---|
| Kelsey's 20 core questions | Kelsey | Nicole |
| Nicole's 20 core questions | Nicole (AI-suggested, checked by Nicole) | Kelsey, on a sample of 10 answerable questions |
| 48 SWE-QA questions | Nicole (AI-suggested, checked by Nicole) | Kelsey, on a sample of 10 |
| Nicole's 8 unanswerable questions | `simple` by rule | not sampled |

The two samples were chosen by fixed rules before any results: Nicole's answerable core questions except every 6th; SWE-QA every 5th starting at #3. All other questions have one tagger, which the report states as a limitation.

## Exposed questions (tagged, but not counted)

These were seen with a tag before second tagging (as examples in an earlier version of the rule, or in review comments), so they are left out of the agreement rate:

- Kelsey's sample: `core-architectural-01`, `core-architectural-08`, `core-design-rationale-06`, `core-design-rationale-07`
- Nicole's sample: `core-localisation-03`, `core-localisation-05`, `core-runtime-behaviour-02`, `core-runtime-behaviour-04`, `core-runtime-behaviour-07`, `core-design-rationale-04`
- The replacement `core-runtime-behaviour-02` (see AC-1.4 below): Nicole suggested its topic, so it is not tagged blind and not counted. Kelsey tagged it `code-tracing`.

## Agreement

| Second tagger | Agreed | Rate |
|---|---|---|
| Kelsey (on Nicole's and SWE-QA questions) | 7 / 16 | 44% |
| Nicole (on Kelsey's questions) | 9 / 14 | 64% |
| **Total** | **16 / 30** | **53%** |

Agreement is low. The disagreements cluster in two places: single-method questions that one tagger read as tracing, and questions about class relationships or several stages. The rule was clarified after discussion (see below), and every disagreement was settled against it.

## Disagreements

"Recommendation" applies the rule; **Final** is the decision Nicole and Kelsey agreed. Kelsey agreed with all 14 rule-based recommendations; the 3 undecided ones were settled with her reasons.

| Question | Nicole tagged | Kelsey tagged | Recommendation (by the rule) | Final |
|---|---|---|---|---|
| core-architectural-02 (app vs request context) | code-tracing | simple | code-tracing: pushing a request context creates and pushes an app context (a call to follow) | **code-tracing** |
| core-architectural-03 (URL rules and matching) | code-tracing | simple | code-tracing: rule added to the map, then bound and matched per request | **code-tracing** |
| core-architectural-04 (`Scaffold`) | simple | code-tracing | simple: a class relationship read from the definitions | **simple** |
| core-architectural-07 (test client) | simple | code-tracing | simple: subclass relationships read from the definitions | **simple** |
| swe-qa-flask-03 (static serving and caching) | code-tracing | simple | simple: two parallel lookups, one per class | **simple** |
| swe-qa-flask-08 (test parameters and `locate_app`) | code-tracing | simple | code-tracing: the test's values must be followed into `locate_app` | **code-tracing** |
| swe-qa-flask-13 (`_lazy_sha1`) | simple | code-tracing | simple: the function and its docstring explain it | **simple** |
| swe-qa-flask-23 (`TypedDict` return type) | code-tracing | simple | code-tracing: needs `make_response`, not just `typing.py` | **code-tracing** |
| swe-qa-flask-28 (`open_resource` read-only) | simple | code-tracing | simple: one method | **simple** |
| core-localisation-02 (`SecureCookieSessionInterface`) | code-tracing | simple | simple: one class | **simple** |
| core-runtime-behaviour-01 (`url_for` extra arguments) | code-tracing | simple | simple: one documented behaviour | **simple** |
| core-runtime-behaviour-08 (when the cookie is sent) | code-tracing | simple | simple: one method, `should_set_cookie` | **simple** |
| core-design-rationale-02 (`JSONProvider` reason) | code-tracing | simple | simple: one docstring | **simple** |
| core-design-rationale-03 (`download_name` rename) | code-tracing | simple | simple: one commit (history rule) | **simple** |
| core-architectural-01 (exposed) | code-tracing | simple | code-tracing: a call chain from the WSGI server to the view | **code-tracing** |
| core-runtime-behaviour-02 (exposed) | simple | code-tracing | simple: one function, `preprocess_request` | **simple** |
| core-runtime-behaviour-04 (exposed) | code-tracing | simple | simple: one method, `get_expiration_time` | **simple** |

## Effect on the minimum of 3 code-tracing per category (AC-1.4)

With the final tags, runtime-behaviour fell to 2 code-tracing questions (`core-runtime-behaviour-02`, "In what order does Flask run app-wide and blueprint `@before_request` functions?", became `simple`). Kelsey replaced it, keeping the id, with a code-tracing question she wrote: "If my view raises an exception that has no error handler, how does Flask turn it into a 500 response, and where is `got_request_exception` sent?" (`full_dispatch_request` → `handle_user_exception` → `wsgi_app` → `handle_exception`; ai_assisted: Claude found the line numbers). The original question is retired, not reported.

Code-tracing per answerable category after the swap: architectural 4, design-rationale 4, localisation 5, runtime-behaviour 3. All meet the minimum.

## Notes

- SWE-QA reference answers `swe-qa-flask-19`, `-38` and `-47` end with a stray `</start_of_answer>`, and `-33` starts with "Yes,". They are kept unchanged (AC-2.1a); graders ignore them.
