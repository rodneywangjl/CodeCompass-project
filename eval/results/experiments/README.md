# Exploratory experiments (9 Nov 2026)

Not part of the three-way comparison. Run on eval-v1 (c6fa1b7) except C (see the table), same model, seed and settings, written to a separate folder. No defaults were changed because of them (Article VII.5). Automatic metrics only, no human grading. One run each, so differences of a few answers are not conclusive. All files carry `label: reported` because they ran from a clean tagged or main checkout; that does not make them part of the three-way comparison.

| File | Experiment | Config |
|---|---|---|
| retrieval-20261109T013603Z.json | A: 1024-token chunks, retrieval only | chunk1024.toml (index: idx1024-only.toml) |
| llm-rag_tools-20261109T020317Z.json | A+: 1024-token chunks, rag_tools | chunk1024.toml |
| llm-rag_tools-20261109T014917Z.json | B: docs fallback on (.md/.rst indexed), rag_tools | docs-on.toml (index: idxdocs-only.toml) |
| llm-rag_tools-20261109T080951Z.json | C: citation example in the prompt ([prompt] format_example = true, T19.6), rag_tools; run on main 01bbc6e, not eval-v1 (the flag was added after the freeze; with it off the prompt is byte-identical to eval-v1) | fmt-on.toml |

The *-only.toml files are indexing-only configs: `codecompass.offline.cli index --config` does not accept a full config (unknown section 'generator'), recorded as a limitation.

Summary vs official rag_tools (citation accuracy / F share / format slips / abstentions / median latency):
- official: 15% / 20% / 56 / 9 / 8.2 s
- B, docs on: 28% / 30% / 49 / 8 / 7.8 s (a doc chunk was sent in 18/88; 24 answers cited a doc, 6 verified)
- A+, 1024: 18% / 17% / 51 / 18 / 10.3 s
- C, citation example on: 45% / 47% / 28 / 12 / 7.6 s (H1 4 vs 2; no answer cited the invented example file or commit)
- A retrieval: hybrid file hit@1 79% vs 71% (512); @10 100% for both.

