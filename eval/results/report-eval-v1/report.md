# Evaluation report (Spec 003)

Every figure states its n. No significance tests (AC-9.5).

## Hallucination rate (AC-9.1)

Hallucinated = H1 or H2 or H3. Abstentions count in n; errors are left out.

| Group | rag | rag_tools | strict (slips as H1): rag | rag_tools |
|---|---|---|---|---|
| overall | 55% (11/20), n = 20 | 20% (4/20), n = 20 | 75% (15/20), n = 20 | 50% (10/20), n = 20 |
| category: architectural | 75% (3/4), n = 4 | 50% (2/4), n = 4 | 75% (3/4), n = 4 | 75% (3/4), n = 4 |
| category: design-rationale | 75% (3/4), n = 4 | 0% (0/4), n = 4 | 75% (3/4), n = 4 | 0% (0/4), n = 4 |
| category: localisation | 50% (2/4), n = 4 | 25% (1/4), n = 4 | 50% (2/4), n = 4 | 25% (1/4), n = 4 |
| category: runtime-behaviour | 50% (2/4), n = 4 | 25% (1/4), n = 4 | 100% (4/4), n = 4 | 100% (4/4), n = 4 |
| category: unanswerable | 25% (1/4), n = 4 | 0% (0/4), n = 4 | 75% (3/4), n = 4 | 50% (2/4), n = 4 |
| complexity: code-tracing | 62% (5/8), n = 8 | 50% (4/8), n = 8 | 75% (6/8), n = 8 | 62% (5/8), n = 8 |
| complexity: simple | 50% (6/12), n = 12 | 0% (0/12), n = 12 | 75% (9/12), n = 12 | 42% (5/12), n = 12 |
| set: core | 33% (4/12), n = 12 | 17% (2/12), n = 12 | 58% (7/12), n = 12 | 50% (6/12), n = 12 |
| set: swe-qa | 88% (7/8), n = 8 | 25% (2/8), n = 8 | 100% (8/8), n = 8 | 50% (4/8), n = 8 |

## Verification Gain (AC-9.2)

rate(rag) − rate(rag_tools); positive means the tools help.

| Group | Verification Gain |
|---|---|
| overall | 0.35 |
| category: architectural | 0.25 |
| category: design-rationale | 0.75 |
| category: localisation | 0.25 |
| category: runtime-behaviour | 0.25 |
| category: unanswerable | 0.25 |
| complexity: code-tracing | 0.12 |
| complexity: simple | 0.50 |
| set: core | 0.17 |
| set: swe-qa | 0.62 |

## Quality (AC-9.3)

| Group | rag mean (0/1/2) | rag_tools mean (0/1/2) |
|---|---|---|
| overall | 0.80 (11/2/7), n = 20 | 0.95 (9/3/8), n = 20 |
| category: architectural | 0.25 (3/1/0), n = 4 | 0.75 (2/1/1), n = 4 |
| category: design-rationale | 0.50 (3/0/1), n = 4 | 0.00 (4/0/0), n = 4 |
| category: localisation | 1.00 (2/0/2), n = 4 | 0.75 (2/1/1), n = 4 |
| category: runtime-behaviour | 0.75 (2/1/1), n = 4 | 1.25 (1/1/2), n = 4 |
| category: unanswerable | 1.50 (1/0/3), n = 4 | 2.00 (0/0/4), n = 4 |
| complexity: code-tracing | 0.62 (5/1/2), n = 8 | 0.25 (6/2/0), n = 8 |
| complexity: simple | 0.92 (6/1/5), n = 12 | 1.42 (3/1/8), n = 12 |
| set: core | 1.25 (4/1/7), n = 12 | 1.17 (4/2/6), n = 12 |
| set: swe-qa | 0.12 (7/1/0), n = 8 | 0.62 (5/1/2), n = 8 |

## Paired comparison, rag_tools vs rag (AC-9.4)

| Group | n | better | same | worse | hallucination fixed | new |
|---|---|---|---|---|---|---|
| overall | n = 20 | 5 | 12 | 3 | 9 | 2 |
| code-tracing | n = 8 | 2 | 3 | 3 | 3 | 2 |
| simple | n = 12 | 3 | 9 | 0 | 6 | 0 |

## Contamination check, no_retrieval (AC-10.2)

- core: mean 0.00, n = 8
- swe-qa: mean 0.00, n = 8
- difference (swe-qa − core): 0.00; flagged at ≥ 0.5 (fixed before the results): **no**
- The two sets differ in style and difficulty, so a gap suggests memorisation but does not prove it.

## Citation accuracy and automatic labels, all questions (AC-7.1, AC-10.3)

| Configuration | n | errors | accuracy (verified/entries) | F share | abstentions | format slips | uncited | H1 | strict H1 |
|---|---|---|---|---|---|---|---|---|---|
| no_retrieval | n = 88 | 0 | 0% (0/14) | 0% | 74 | 0 | 0 | 14 | 14 |
| rag | n = 88 | 0 | 35% (81/230) | 47% | 4 | 43 | 0 | 0 | 43 |
| rag_tools | n = 88 | 0 | 15% (39/266) | 20% | 9 | 56 | 3 | 2 | 58 |

## Latency (AC-11.1)

| Configuration | n | median total (s) | max total (s) | median per stage (s) |
|---|---|---|---|---|
| no_retrieval | n = 88 | 0.64 | 0.96 | citation_check 0.00, ensure_current 0.01, generation 0.63, reranking 0.00, retrieval 0.00, tool_execution 0.00 |
| rag | n = 88 | 5.07 | 21.35 | citation_check 0.00, ensure_current 0.01, generation 4.48, reranking 0.42, retrieval 0.03, tool_execution 0.00 |
| rag_tools | n = 88 | 8.22 | 21.72 | citation_check 0.00, ensure_current 0.01, generation 7.38, reranking 0.42, retrieval 0.03, tool_execution 0.35 |

## Hit rate@k (AC-4.x)

See `report.json` → `hit_rates` (copied from the retrieval results file, with n).
