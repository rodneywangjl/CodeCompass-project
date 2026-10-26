# AI Use Log: Rodney Wang

## 2026-10-26 · Online config merge without a TOML round trip
- **Tool (model):** Claude Code (claude-opus-5-5)
- **Files:** codecompass/offline/config.py, codecompass/online/config.py, tests/online/test_config_merge.py
- **Outcome:** Changed
### What I asked for
T0.1's `load_online_config` wrote the offline sections back out as TOML text in a temp file. That crashed on, or silently corrupted, values with backslashes or quotes (e.g. Windows paths) and wrote booleans as `True`. I asked for a tests-first fix.
### How I checked it
TODO (member)
### What I kept or changed
Split the offline `load_config` so its validation runs on a parsed dict (`config_from_dict(raw, anchor=)`). The online loader passes its offline sections straight in and the TOML writer is deleted. The tests also found that relative `index.dir` resolved against the temp folder; the anchor is now the real config file's folder. The boolean bug has no test because no offline setting is boolean yet; the code that caused it is removed.
