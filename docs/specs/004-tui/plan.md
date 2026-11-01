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
- The TUI writes to stderr only when stderr is a terminal and `--no-draft` is absent: the `⚠ DRAFT — NOT CHECKED…` header once, then each delta with every line prefixed `draft │ ` and dimmed (a line splitter holds a partial line until its newline, so the prefix is never split), control characters removed, then `Draft finished after N s.`, `── Checked answer (replaces the draft above) ──` and the answer on stdout. `run_session` gets a `draft` flag; only when it is set and stderr is a terminal does it call `answer(question, on_draft=...)`, so answer functions that take only a question keep working. Cursor movement is avoided on purpose: the draft stays in the scrollback.
- `tests/support/stub_generator.py` gains the same `on_text` keyword and streams its canned text in pieces.

## 7. Warm-up and layered config (US3)

- `online/config.py`: split `load_online_config(path)` into reading TOML and `online_config_from_dict(raw, anchor)`, so layers can be merged as dicts. Merge rule: section by section, keys of the upper layer win; `generator.profiles.<name>` replaces the whole profile.
- `tui.py`: `_find_config` returns the list of files (user-level first, then repo); the banner prints each. `--config` returns just that file.
- `online/__init__.py`: `warm_up(repo_path, *, config, index_dir=None)` calls `ensure_current`, then `open_index(...).embed_query("warm up")` to load the embedder, then the shared re-ranker once; it prints nothing and returns nothing.
- `tui.py` runs `warm_up` in a daemon thread when stdin and stderr are terminals. Before the first `ask()` it joins the thread (status text `Preparing index and models…`). Errors are swallowed in the thread; the real `ask()` raises them again.
- No GPU code is added: devices come from `[embedder] device` and `[reranker] device`, which already exist.

## 8. Tools view and look (US4, US5)

One new module, `codecompass/online/tui_view.py`: pure functions, no I/O, standard library only, so every rule below is unit-tested without a terminal.

```
tool_calls(rounds) -> list[dict]       executed entries (a `tool` name), in order        AC-4.1
summary_line(rounds) -> str            "▸ 3 tools called — type /tools to see them" etc.  AC-4.1
format_tools(rounds) -> str            the /tools text                                    AC-4.2, 4.3
color_level(stream, environ, no_color) -> "truecolor" | "256" | "none"                    AC-5.2
Style(level).paint(text, name) / .answer(text)                                            AC-5.1, 5.3, 5.4
strip_escapes(text) -> str             removes every SGR sequence (used by the tests)
```

- **Rounds, not recomputed (AC-4.4).** `main` keeps the last answered question's `result.audit_log["tool_calls"]` (`getattr(result, "audit_log", None) or {}`) and passes `run_session` a zero-argument `tool_rounds` callable. `run_session` stays backward compatible: with no `tool_rounds`, nothing changes, so the approved session tests are untouched. A failed or interrupted question never calls it, so the previous list stays.
- **Counting.** An entry counts as a tool call when `entry.get("tool")` is not None. The other record kinds in the harness (`malformed`, `final_call`, `ignored_calls` with `reason`) are listed by `/tools` as one explanatory line each and are not counted.
- **The `/tools` text (AC-4.2).** A header line `Tools called for the last question:` and then, per round in order, two lines (the second indented by nine spaces):

  ```
  round 0  git_log  path=src/auth.py n=5
           cache miss · f00dbab 2024-03-14 Alice "fix"
  round 1  open_file  path=src/auth.py lines=1-20
           cache hit · --- src/auth.py, lines 1-20 | python ---
  round 2  open_file  path=../x
           cache miss · failed · error: path outside the repository
  round 0  malformed request, no tool ran
  round 3  request refused: the round limit was reached
  round 0  request ignored: tools are off in this mode
  ```

  Arguments are `key=value` pairs in the order the call gave them; the result line is the record's `result_summary` (omitted when empty). With nothing to list: `No tools were called for the last question.` (or `No question has been answered yet.` before the first answer).
- **Where it prints.** The AC-4.1 line and `/tools` go to stderr, so stdout stays "the answer, nothing else" (AC-1.2, AC-1.11). The line is printed after the answer, only when `prompting` is true.
- **Sanitising (AC-4.3).** Arguments and the result line pass through the same `_CONTROL` filter as the draft, and values over 100 characters are cut with `…`.
- **Colour (AC-5.2).** `color_level` requires `os.isatty(stream.fileno())`, so the fake terminals in the approved tests (which only define `isatty()`) never get colour, whatever the environment of the machine running the tests. 256-colour output maps each RGB value to the nearest entry of the xterm cube and grey ramp. No colour is used on `dumb` terminals.
- **Answer colouring (AC-5.4).** `Style.answer(text)` works line by line on text that is already final: it wraps whole lines equal to the known banner and note constants (`formatter.BANNER`, `UNREFERENCED_BANNER`, `UNCITED_NOTE`, `PARTIAL_NOTE`, the stale-index warning), the line-start marks, the trailing ` (not cited)` tag, `[N]` markers and the `Sources` heading. It never inserts, removes or reorders characters other than escape sequences; the tests assert `strip_escapes(Style.answer(t)) == t` over a property-style set of answers.
- **Themes (AC-5.1, AC-5.6).** `Style(level, theme)`; `theme_name(flag, environ)` resolves `--theme`, then `CODECOMPASS_THEME`, then `auto` (`COLORFGBG` last field `7` or `15` means `light`). The palettes, by role:

  | Role | Used for | `dark` (Rosé Pine Moon) | `light` (Rosé Pine Dawn) |
  |---|---|---|---|
  | accent | title, prompt, `[N]` markers | iris `#c4a7e7` | iris `#907aa9`, bold |
  | info | status line, tools line, `Sources` heading | foam `#9ccfd8` | pine `#286983` |
  | warn | stale warning, note lines, draft header, `[NOT REFERENCED IN ANSWER]` | gold `#f6c177` | love `#b4637a` |
  | tag | ` (not cited)` | rose `#ea9a97` | subtle `#797593` |
  | danger | `error:`, flagged banner, `[UNVERIFIED]` | love `#eb6f92`, bold | custom `#91344f`, bold |
  | ok | `cache hit` | pine `#3e8fb0` | pine `#286983` |
  | muted | startup details, `/tools` header | `#6272a4` | subtle `#797593` |

  Reference backgrounds for the contrast check: `dark` `#232136` and `#000000`; `light` `#faf4ed` and `#ffffff`. The `light` theme leaves out Dawn's gold, rose and muted, whose contrast is 2.1 to 2.7:1, and gives `danger` a custom colour (Q12): Dawn's love with the same hue (343°) and the lightness lowered from 0.55 to 0.39. Measured contrast of what it uses, on `#faf4ed` / white: iris 3.5 / 3.8, love 3.8 / 4.2, subtle 4.0 / 4.4, pine 5.6 / 6.1, custom danger 6.8 / 7.5. `dark` on `#232136` / black: iris 7.5 / 10.0, foam 9.2 / 12.3, gold 9.5 / 12.8, rose 7.1 / 9.6, love 5.4 / 7.2, pine 4.3 / 5.8, muted 3.3 / 4.5.
- **Prompt and banner text stay as they are** (`> `, `codecompass: repo: …`): the approved tests assert them, and the look comes from colour. Only the colour around them is new.
- **No thread, no spinner, no new dependency** (P3 holds).

| Test layer | Tests |
|---|---|
| Unit | `tool_calls`, `summary_line`, `format_tools` on hand-made rounds; `color_level` over environments; `paint` and `answer` round-trip with escapes stripped; 256-colour mapping |
| Session | `run_session` with a fake `answer` and a fake `tool_rounds`: the count line, `/tools`, failed and interrupted questions, piped mode |
| Integration | `main` on the fixture repo with the stubs and a generator that requests `git_log`: the real audit log reaches the count line and `/tools` |

