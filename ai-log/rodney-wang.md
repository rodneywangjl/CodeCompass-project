# AI Use Log: Rodney Wang

## 2026-10-26 · Query embedder on the index handles
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/__init__.py, tests/offline/test_query_embedder.py
- **Outcome:** Changed
### What I asked for
The online pipeline needs to embed questions with the same embedder as the index, but Plan 002 D1 imports the internal `CodeEmbedder`, which breaks Article II.2. Separately, `open_index` only checked the config, not the embedder actually used. I asked for both to be fixed tests-first.
### How I checked it
TODO (member)
### What I kept or changed
Chose to bind the embedder to the handles: `open_index(..., embedder=None)` attaches it, and `handles.embed_query(text)` uses it. With no embedder passed, the pinned one is built from config and loads lazily. I chose the strict rule: the config and the embedder must both match the index, otherwise it is refused. No new public export.
