# Settling the grading disagreements

**Grading folder:** `grading-20261109T012724Z` (seed 20261109, 56 rows). **Graders:** Nicole, Kelsey. **Settled:** 9 Nov 2026, in writing (no call).

## Raw agreement (before settling; reported unchanged)

| Field | Agreed | n | Share |
|---|---|---|---|
| score | 42 | 56 | 75% |
| h2 | 27 | 40 | 68% |
| h3 | 7 | 8 | 88% |
| reason (rows where both gave 0) | 25 | 27 | 93% |

Cohen's kappa: score 0.55 (n = 56), H2 0.24 (n = 40).

Disagreeing rows: 17 (R02, R04, R05, R09, R14, R17, R24, R31, R32, R33, R34, R35, R38, R46, R48, R52, R54).

Most disagreements came from H2: the two graders read "supported" differently (neither was simply stricter), especially on format-slip rows with "(not cited)" statements. This is reported as a limitation: judging whether a claim is supported is hard even for humans.

## Rules clarified during settling (9 Nov, before figures)

Agreed in writing after the disagreements were known, but **before anyone opened `key.json` or ran `report figures`** (no results by configuration had been seen). They interpret spec §5.1 and §5.2; they do not change them.

1. **Supported (H2), including "(not cited)" statements:** supported = the context states it or it follows directly from the code or docstring shown (a faithful paraphrase counts). H2 yes = the statement adds specifics the context does not show (a name, value, behaviour, condition, reason, or generalisation), even if true of Flask. Citation status does not matter.
2. **Abstentions:** a pure abstention (including the pipeline's closest-matches list) is H2 no; H2 applies only to extra factual claims beyond "can't find it". An answerable question abstained on scores 0, `abstained`.
3. **H1 (a citation that matches nothing):** H1 alone does not force a 0 (it already counts in the hallucination rate). If the claim behind the bad citation is not in the context, that is H2 yes and a 0; otherwise the answer is scored on correctness.
4. **Reason labels:** `abstained` = declines an answerable question; `unsupported` = answers with a claim not in the context; `wrong-but-grounded` = answers wrongly but from the context; `fabricated-citation` = a citation not matching the context is what makes it wrong.

**Tie-break agreed in advance:** if a row stays disputed, the stricter reading of the rule wins.

## Row by row

Proposed by Nicole, applying the rules above; R05 and R17 were discussed in writing first. **Kelsey checked all 17 against the rows and the notes and agreed with every final value (9 Nov).**

| Row | In dispute | Nicole | Kelsey | Final | Rule and note | Kelsey |
|---|---|---|---|---|---|---|
| R02 | h2, score, reason | h2 no, score 1, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: app-context preservation claim is misattributed; context describes request-context preservation. | agree |
| R04 | score | score 2 | score 1 | h2 no, h3 n/a, score 2 | Both storage and execution path are identified; reverse order and signals are extra. | agree |
| R05 | reason | reason unsupported | reason abstained | h2 yes, h3 n/a, score 0, unsupported | Agreed: an unsupported claim makes this more than a pure abstention. | agree |
| R09 | h2, score, reason | h2 no, score 2, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: the dumps implementation is absent so its ensure_ascii behavior is unsupported. | agree |
| R14 | h2, score, reason | h2 no, score 2, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: the claim that JSON only supports text is not in the context. | agree |
| R17 | reason | reason abstained | reason wrong-but-grounded | h2 no, h3 n/a, score 0, abstained | Agreed: it declines an answerable why question; the relevant commit was not retrieved. | agree |
| R24 | score | score 2 | score 1 | h2 no, h3 n/a, score 2 | Supported encoding and decoding explain the requested reversible round trip. | agree |
| R31 | h2, score, reason | h2 no, score 1, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: the config-setting branch is absent from context. | agree |
| R32 | h2, score, reason | h2 yes, score 0, reason unsupported | h2 no, score 2, reason – | h2 yes, h3 no, score 0, unsupported | Rule 1: the ad-funding inference is unsupported; no sponsor answer was made. | agree |
| R33 | h2, score, reason | h2 no, score 1, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: request-context preservation is misattributed to the app context. | agree |
| R34 | h2, h3, score, reason | h2 yes, h3 yes, score 0, reason unsupported | h2 no, h3 no, score 2, reason – | h2 no, h3 no, score 2 | Correctly rejects the nonexistent property and points to get_json. | agree |
| R35 | h2, score, reason | h2 no, score 1, reason – | h2 yes, score 0, reason fabricated-citation | h2 yes, h3 n/a, score 0, unsupported | Rule 3 + Rule 1: both citations are unverified (H1), and the claims behind them (registration) are not in the context -> H2 yes, 0. Unsupported rather than fabricated-citation: what makes it wrong is the content (it addresses processors, not filters), not only the bad citations. | agree |
| R38 | h2, score, reason | h2 yes, score 0, reason unsupported | h2 no, score 1, reason – | h2 yes, h3 n/a, score 0, unsupported | Rule 1: the HTTPException subclass claim is not in the context. | agree |
| R46 | h2, score, reason | h2 no, score 1, reason – | h2 yes, score 0, reason unsupported | h2 yes, h3 n/a, score 0, unsupported | Rule 1: registration and rendering claims are not established; answer discusses processors not filters. | agree |
| R48 | h2 | h2 yes | h2 no | h2 no, h3 n/a, score 0, abstained | Rule 2: pure abstention on an answerable question means H2 no. | agree |
| R52 | h2, score, reason | h2 yes, score 0, reason unsupported | h2 no, score 1, reason – | h2 no, h3 n/a, score 1 | Claims are supported but the requested exception-dispatch path is omitted. | agree |
| R54 | h2, score, reason | h2 yes, score 0, reason unsupported | h2 no, score 1, reason – | h2 no, h3 n/a, score 1 | Runtime separation is supported; the TypedDict mechanism and tuple status detail are missing. | agree |

## Discussed rows

- **R05:** Kelsey proposed `abstained` (the answer declines the second half although `AppContext.pop()` in `ctx.py` 238-284 was in the context). Nicole kept `unsupported`: the answer makes a claim not in the context, so it is not a pure abstention (Rule 2) and H2 stays yes. **Kelsey agreed (9 Nov).**
- **R17:** both settled on `abstained` (Kelsey changed from `wrong-but-grounded`): it reads the `git_log` for `sansio/app.py` and says it cannot determine the reason. A retrieval miss: the commit with the reason (`0ec7f713`, Quart and other async frameworks sharing the core) was not among the 10 retrieved. Failure-example candidate.

## Outcome

All 17 rows have final values in `sheet-merged.csv`, which passes the format and consistency checks (every final cell filled, H2/H3 yes → 0, every 0 has a valid reason, n/a kept, nothing else changed). Kelsey checked every row and agreed with all 17 final values, including R35 as `unsupported` (9 Nov). No row needed the tie-break. Settling is complete; next, `report figures` (the first time `key.json` is read).
