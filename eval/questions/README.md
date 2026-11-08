# Evaluation question sets

Spec: `docs/specs/003-evaluation/spec.md`. Check any file with `python3 -m codecompass.eval.questions FILE... --repo <flask clone at 85c5d93>`.

| File | Questions | Source |
|---|---|---|
| `flask-core-nicole.jsonl` | 20 | Written by Nicole (AI-assisted items marked `ai_assisted`) |
| `flask-core-kelsey.jsonl` | 20 | Written by Kelsey (AI-assisted items marked `ai_assisted`) |
| `flask-swe-qa.jsonl` | 48 | Imported from SWE-QA (below) |
| `tagging.md` | | Complexity tags: second-tagger agreement and final decisions |

All questions are pinned to Flask commit `85c5d93cbd049c4bd0679c36fd1ddcae8c37b642`.

## SWE-QA (imported set)

- **Dataset:** SWE-QA-Bench, <https://github.com/peng-weihan/SWE-QA-Bench>, file `Benchmark/flask.jsonl`.
- **Version:** commit `744a673b63bab77996096d278572da675defc0f9` (2026-04-07, "for camera-ready"), the last commit to change that file. Git blob `719b8b02f162012da3062351b8b8662fb188f7b5`, which matches the copy we converted (checked 2026-11-08).
- **Licence:** Apache-2.0 (the SWE-QA-Bench repository).
- **Citation:** Peng et al., "SWE-QA: Can Language Models Answer Repository-level Code Questions?", Findings of ACL 2026, pp. 8230-8245. arXiv:2509.14635. BibTeX key `peng2026swe` in the dataset README.
- **What we changed:** nothing in the question or reference-answer text (AC-2.1). We added the id, category, complexity tag, reference citations and ground-truth files (AC-2.2, AC-2.3). Known quirks in the source are kept as they are (AC-2.1a).
- **Reporting:** results on this set are reported separately from the core set, and combined only where stated (AC-2.4).
