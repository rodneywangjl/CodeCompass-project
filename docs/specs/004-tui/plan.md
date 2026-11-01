# Plan 004: Minimal Terminal UI

**Implements:** Spec 004 | **Constitution:** v1.4.0

## 1. Design

One new module, `codecompass/online/tui.py`, standard library only.

```
main(argv) -> int          parse args, load config, resolve profile, validate repo, build Session, run it
Session                    holds config, profile, repo, and the once-built generator, reranker and embedder
run_session(session, stdin, stdout, stderr) -> int     the loop; no model or config knowledge
```

- `run_session` takes an `answer(question) -> str` callable plus streams, so the loop is tested with a fake and never needs a model (Article IX.7).
- The callable is `ask(repo, q, config=..., profile=..., generator=g, reranker=r, embedder=e).answer`. `generator` is built once from the active profile. `reranker` and `embedder` are built once if Q1 option (a) is approved; otherwise `ask()` builds its defaults and AC-1.4 is not met for them.
- `print(result.answer)` is the only thing written to stdout per question (AC-1.2, AC-1.3). Banner, hints, status and errors go to stderr.
- Heavy imports (`codecompass.online`, torch via sentence-transformers) happen on the first question, not at import of `tui.py`, so the prompt appears at once (AC-1.4).
- Interactive means `sys.stdin.isatty()`. Not interactive: no prompt, banner or status line (AC-1.11).
- Status line: write `\rThinking…` to stderr before the call and clear it with `\r\033[K` after, only if stderr is a TTY (AC-1.5). No thread or spinner.
- `KeyboardInterrupt` is caught around the call (AC-1.7) and at the prompt (AC-1.6). Any other `Exception` is printed as `error: ...` (AC-1.8).
- Repo root: `git -C <REPO or cwd> rev-parse --show-toplevel`; failure is the AC-1.9 error. That root, not the working directory, is passed to `ask()` and printed in the banner (AC-1.1).
- Startup validation reuses the same config and profile resolution as `cli.py` (`load_online_config`, `resolve_profile`) and checks the repo with `git rev-parse` (AC-1.9). The generator health check uses `LlamaServerGenerator.health_check` (AC-1.10).
- Config lookup (AC-1.13): a small `_find_config(repo_root, explicit)` returns the first existing path from the order in the spec, using `$XDG_CONFIG_HOME` if set, else `~/.config`.
- `readline` is imported in a `try` so history and line editing work where available (Q3).

## 2. Packaging (AC-1.12, needs Q2)

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project.scripts]
codecompass = "codecompass.online.tui:main"

[tool.setuptools.packages.find]
include = ["codecompass*"]
```

Install with `pip install -e .` (add `--no-build-isolation` when offline; setuptools is already in the venv).

## 3. Model reuse (Q1, option a)

- `codecompass/online/__init__.py`: cache `_default_reranker(config)` per process, keyed on the reranker config.
- `codecompass/offline`: cache the default `CodeEmbedder` per process, keyed on the embedder config, so `open_index` and `ensure_current` reuse one instance (plan 002 O1, O2). `ensure_current`'s fast path still loads nothing.
- Behaviour with stubs is unchanged: injected objects always win over the cache.

## 4. Test layers

| Layer | Tests |
|---|---|
| Unit | `run_session` with a fake `answer`: output, blank lines, exits, Ctrl-C, errors, non-TTY mode, status line only on TTY |
| Integration | `main` on the fixture repo with `StubGenerator`, `StubReranker`, `StubEmbedder`: real `ask()`, real citation check, flagged banner reaches stdout |
| Packaging | `pyproject.toml` declares the script and it resolves to a callable |
| Model (`-m model`, local only) | one smoke run against the 7B profile; not required for merge |

## 5. Optimisations

| # | Optimisation | Saves |
|---|---|---|
| P1 | Models built once and reused (Q1) | Seconds of model load per question |
| P2 | Lazy imports | Instant prompt; `codecompass --help` stays fast |
| P3 | No thread, no polling, no extra dependency | Startup time, install size, test complexity |

## 6. Draft streaming (US2)

- `LlamaServerGenerator.generate(messages, *, on_text=None)`: with a callback, request `stream: true` on `/v1/chat/completions` and feed each text delta to `on_text`; return the full text so callers see no difference. If the stream cannot be opened, make the normal call and pass the whole text once.
- The harness passes `on_text` through to each generator call. A small filter holds back the first characters of a round until it is clear whether the text starts with `<tool>`; tool rounds are never forwarded (AC-2.3).
- `ask(..., on_draft=None)` hands the callback to the harness via the timed generator wrapper. The default `None` leaves every code path as it is today.
- The TUI writes deltas to stderr only when stderr is a terminal and `--no-draft` is absent, dimmed with an ANSI style, then a `Checked answer:` line, then the answer on stdout. Cursor movement is avoided on purpose: the draft stays in the scrollback.
- `tests/support/stub_generator.py` gains the same `on_text` keyword and streams its canned text in pieces.

## 7. Warm-up and layered config (US3)

- `online/config.py`: split `load_online_config(path)` into reading TOML and `online_config_from_dict(raw, anchor)`, so layers can be merged as dicts. Merge rule: section by section, keys of the upper layer win; `generator.profiles.<name>` replaces the whole profile.
- `tui.py`: `_find_config` returns the list of files (user-level first, then repo); the banner prints each. `--config` returns just that file.
- `online/__init__.py`: `warm_up(repo_path, *, config, index_dir=None)` calls `ensure_current`, then `open_index(...).embed_query("warm up")` to load the embedder, then the shared re-ranker once; it prints nothing and returns nothing.
- `tui.py` runs `warm_up` in a daemon thread when stdin and stderr are terminals. Before the first `ask()` it joins the thread (status text `Preparing index and models…`). Errors are swallowed in the thread; the real `ask()` raises them again.
- No GPU code is added: devices come from `[embedder] device` and `[reranker] device`, which already exist.
