# Tasks 004: Minimal Terminal UI

**Implements:** Plan 004 / Spec 004 | **Constitution:** v1.4.0

Same rules as Tasks 002: one task at a time, in order; tests first, show them failing, **stop for approval**, then implement; tests commit before implementation; never edit an approved test; stay inside "Touches".
Paths are under `codecompass/online/` and `tests/online/` unless stated.

---

**T0.1 Reuse default models across questions** *(Q1 option (a), approved)*
- Tests first: two `ask()` calls with default (non-injected) reranker and embedder construct each one once (use a counting factory); injected stubs are used instead of the cache; a different config builds a new instance; Article II.4 identity check still rejects a mismatched embedder.
- ACs: AC-1.4. | Touches: `online/__init__.py`, `offline/` embedder construction. | Depends on: none.

**T1.1 Session loop**
- Tests first: a fake `answer` is called once per non-blank line and its text is the only stdout; blank lines are skipped; `/exit`, `/quit` and EOF return 0; Ctrl-C at the prompt prints the hint and continues; Ctrl-C during a question returns to the prompt; an exception prints `error: ...` to stderr and continues; non-TTY mode prints no prompt or status; the status line appears and is cleared only on a TTY.
- ACs: AC-1.2, AC-1.5, AC-1.6, AC-1.7, AC-1.8, AC-1.11. | Touches: `tui.py`, `tests/online/test_tui_session_t11.py`. | Depends on: none.

**T1.2 Startup and wiring**
- Tests first: run from a subdirectory of the fixture repo (and with the repo as an explicit argument), the session uses the repo root and prints it; `main([repo])` on the fixture repo with the stubs answers a piped question through the real `ask()`; a flagged answer's banner and `[UNVERIFIED]` mark reach stdout unchanged; stale-index warning reaches stdout; startup prints profile and model id to stderr; not-a-git-repo, unknown profile and invalid config return 1 with a clear message; a failed health check warns with the start command and still runs; generator, reranker and embedder are each built once across three questions; importing `tui.py` imports no model library.
- Config lookup (AC-1.13): `--config` wins over the repo-root file, which wins over the user-level file, which wins over built-in defaults; a missing `--config` path is an error; the banner names the file used.
- ACs: AC-1.1, AC-1.3, AC-1.4, AC-1.9, AC-1.10, AC-1.13. | Touches: `tui.py`, `tests/online/test_tui_main_t12.py`. | Depends on: T1.1 (and T0.1 for the reuse test).

**T1.3 `codecompass` command**
- Tests first: `pyproject.toml` declares `codecompass = "codecompass.online.tui:main"` and the target resolves to a callable; `main(["--help"])` exits 0 and mentions `REPO`, `--profile`, `--config`, `--index-dir`.
- ACs: AC-1.12. | Touches: `pyproject.toml`, `tests/online/test_tui_entry_t13.py`. | Depends on: T1.2. Q2 approved.

**T1.4 Docs and AI log**
- Add a short "Interactive mode" section to `README.md` and the AI-log entry (with "How I checked it" left as `TODO (member)`).
- Touches: `README.md`, `ai-log/<member>.md`. | Depends on: T1.3.

---

## Phase 2 (draft, pending approval of Q5 and Q6)

**T2.1 Layered config**
- Tests first: a repo file overrides a user-level key and inherits the rest; a profile table replaces the whole profile of that name; `--config` ignores both; relative paths resolve against the file that set them; the banner lists every file; an unknown section in either file is rejected as before.
- ACs: AC-3.1. | Touches: `online/config.py`, `tui.py`, `tests/online/test_tui_layers_t21.py`. | Depends on: T1.4.

**T2.2 Streaming in the generator**
- Tests first (mocked HTTP): with a callback, the request has `stream: true` and each delta reaches the callback in order; the returned text equals the concatenation; without a callback the request and result are unchanged; a stream that cannot be opened falls back to one normal call; a dropped stream raises a clear error.
- ACs: AC-2.5. | Touches: `online/generator/llama.py`, `online/generator/server.py` if needed, `tests/support/fake_http.py`, `tests/online/test_stream_generator_t22.py`. | Depends on: none.

**T2.3 Draft through the harness and `ask()`**
- Tests first: with `on_draft`, an answer round streams and a `<tool>` round does not; the callback never sees tool-call text; with `on_draft=None` the audit log and result are byte-identical to today's; the citation outcome is the same either way; `ask()` still prints nothing.
- ACs: AC-2.3, AC-2.5, AC-2.6. | Touches: `online/__init__.py`, `online/agent/harness.py`, `online/logging.py`, `tests/support/stub_generator.py`, `tests/online/test_draft_t23.py`. | Depends on: T2.2.

**T2.4 Draft in the terminal**
- Tests first: on a terminal the draft goes to stderr under the `⚠ DRAFT — NOT CHECKED` header with every line prefixed `draft │ ` and dimmed, and only the checked answer reaches stdout; a draft line split across two chunks is still prefixed once; `Draft finished after N s.` and `── Checked answer (replaces the draft above) ──` follow the draft; control characters in the draft are removed; a failure or Ctrl-C after some draft prints `(draft discarded)`; no chrome when no draft text arrived; `--no-draft` and non-terminals stream nothing; Ctrl-C mid-draft returns to the prompt with the status cleared; a flagged answer still shows the banner on stdout.
- ACs: AC-2.1, AC-2.2, AC-2.4. | Touches: `tui.py`, `tests/online/test_tui_draft_t24.py`. | Depends on: T2.3.

**T2.5 Warm-up**
- Tests first: on a terminal a warm-up runs once at start-up and the first question reuses it (models and index built once); a question asked during warm-up waits and shows `Preparing index and models…`; a warm-up error appears only at the question; piped input starts no thread; `/exit` during warm-up returns at once.
- ACs: AC-3.2, AC-3.3, AC-3.4. | Touches: `online/__init__.py`, `tui.py`, `tests/online/test_warmup_t25.py`. | Depends on: T2.1.

**T2.6 Docs**
- README: draft display and `--no-draft`, warm-up, layered config, GPU settings with the measurements and the VRAM trade-off, and the CPU-only `llama-server` finding. AI log entries.
- ACs: AC-3.5. | Touches: `README.md`, `ai-log/`. | Depends on: T2.5.

---

## Phase 3 (draft, pending approval): tools view and look

**T3.1 Tool count and `/tools`**
- Tests first: `summary_line` gives "No tools called", "1 tool called" and "N tools called" (AC-4.1 wording); `tool_calls` counts only entries with a `tool` name, so a malformed request, a `final_call` entry and an `ignored_calls` entry are not counted; `format_tools` lists each executed call in order with round, tool, arguments, `cache hit` or `cache miss`, the first line of the result and `failed` on error, adds one line for each malformed or refused request, removes control characters from arguments and results and cuts values over 100 characters with `…`; in `run_session` (fake `answer`, fake `tool_rounds`): on terminals the count line follows the answer on stderr and stdout holds only the answer; with piped input there is no count line; `/tools` prints the last answered question's list to stderr and is never sent to `answer`; `/tools` before any question says no question has been answered; a question that raises, or is interrupted, leaves the previous list in place; `/tools now` is a question; without a `tool_rounds` callable nothing extra is printed; through `main` (stubs, a generator that requests `git_log`), the real audit log feeds the count line and `/tools`, and a result without an audit log counts as no tool calls.
- **Existing approved tests:** approved tests that run `main` on fake terminals may assert the whole of stderr. The count line adds one line there. Run the full suite after the change; if an approved test fails for that reason, stop and ask (Article IX.3).
- ACs: AC-4.1 to 4.5. | Touches: `online/tui_view.py` (new), `tui.py`, `tests/online/test_tui_tools_t31.py`. | Depends on: T2.5.

**T3.2 Colour support**
- Tests first: `color_level` is `none` for a stream without a file descriptor, for `NO_COLOR`, for `--no-color`, for `TERM=dumb` and for a pipe; `truecolor` for `COLORTERM=truecolor` or `24bit` or `WT_SESSION`; `256` for a `TERM` containing `256color`; `paint` emits exact 24-bit sequences from the AC-5.1 palette of the chosen theme, the nearest 256-colour index otherwise, and the unchanged text with level `none`; `strip_escapes(paint(t)) == t`; `theme_name` gives `light` for `COLORFGBG=0;15` and `0;7` (and `15;0;7`), `dark` for `15;0`, an unset or malformed `COLORFGBG`, and `auto`; the flag beats `CODECOMPASS_THEME`, which beats `auto`; an unknown value raises an error naming the allowed values; every colour of both themes has a WCAG contrast of at least 3:1 against its two reference backgrounds, so a future palette edit cannot make text unreadable; the `danger` colour of each theme has at least 4.5:1 against the same backgrounds, and in `light` it is `#91344f`, distinct from `warn`.
- ACs: AC-5.1, AC-5.2, AC-5.6. | Touches: `online/tui_view.py`, `tests/online/test_tui_color_t32.py`. | Depends on: T3.1.

**T3.3 Coloured answer**
- Tests first: with colour on, each text of the Plan 004 section 8 table is wrapped in its role's colour (banner danger, the notes and the stale warning warn, the `[UNVERIFIED]` mark, `(not cited)`, `[N]` markers including multi-digit ones and those in `Sources` entries, the last `Sources` heading); lookalikes are untouched (a mark or banner or tag in the middle of a line, `arr[0]`, `[a]`, anything inside a fenced code block); over real `formatter.render` output (cited, failed, marker without entry, partly uncited, uncited, no evidence, stale) `strip_escapes(output) == answer` exactly, in both themes and at both colour levels; a sentinel colour put in the `ok` role never appears in any answer, so nothing is styled as verified; with colour off the output is byte-identical; `run_session(style=...)` writes `style.answer(text)` and without `style` is unchanged; through `main`, stdout on a stand-in terminal is coloured (banner in the danger colour of the theme chosen by `CODECOMPASS_THEME` or by `COLORFGBG`) and its stripped text equals the plain run's, `NO_COLOR` and a piped stdout give identical plain text, and an unknown `CODECOMPASS_THEME` is a startup error (`error: ...`, exit code 1) naming `auto, dark, light`.
- **Approved test changes:** none expected; AC-1.2 and AC-1.3 are amended in the spec only (colour around, text identical).
- ACs: AC-5.4. | Touches: `online/tui_view.py`, `tui.py`, `tests/online/test_tui_answer_color_t33.py`. | Depends on: T3.2.

**T3.4 Look, flag, docs**
- Tests first: on a colour terminal the startup banner, prompt, status line, `error:` and `warning:` prefixes, the count line, `/tools` and the draft header are coloured and their text is unchanged; draft lines stay dim and marked; `--no-color` and `NO_COLOR` give exactly today's output; `--theme light` and `--theme dark` change only the colour sequences (the text with escapes removed is identical); an unknown `--theme` or `CODECOMPASS_THEME` is a startup error with exit code 1; `main(["--help"])` mentions `--no-color` and `--theme`; piped output has no escape sequence. README: "Interactive mode" gains `/tools`, the colours, the two themes, `--theme`, `--no-color` and `NO_COLOR`; the AI-log entry (with "How I checked it" left as `TODO (member)`).
- ACs: AC-5.3, AC-5.5, AC-5.6. | Touches: `tui.py`, `README.md`, `ai-log/rodney-wang.md`, `tests/online/test_tui_look_t34.py`. | Depends on: T3.3.

