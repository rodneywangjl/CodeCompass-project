# Spec 004: Minimal Terminal UI

**Project:** CodeCompass (SE201 G1-T1) | **Status:** Implemented (T0.1 to T2.5); README in T2.6; US4 and US5 (T3.1 to T3.4) drafted 2026-11-02, pending approval
**Constitution version:** 1.4.0 | **Constitution articles touched:** I, VI, VIII, IX, X, XI

> This spec says **what** the terminal UI must do and how we will know it works. Module layout and design choices belong in the plan.

---

## 1. Purpose

A developer types `codecompass` in a terminal inside (or pointing at) a git repository, types a question at a prompt, and reads the model's cited answer. Nothing else. It is a thin interactive layer over the existing `ask()` API (Spec 002 US9). It adds no pipeline behaviour.

## 2. Scope

**In scope**
- A `codecompass` command that starts an interactive session: prompt, question in, answer out, repeat.
- The answer is exactly `QueryResult.answer`, so the flagged banner, per-source marks, `(not cited)` notes and stale-index warning (Articles VI.3, X.3) appear unchanged.
- Models and clients are created once per session and reused for every question.
- A single progress line while a question is running.
- *(US2, draft)* A live, clearly labelled unchecked draft of the model's text on stderr while it generates.
- *(US3, draft)* Background warm-up: the index and the models are prepared while the user types the first question.
- Clean exit (`/exit`, `/quit`, Ctrl-D), and survival of per-question errors and Ctrl-C.
- Piped (non-interactive) input works, one question per line.
- *(US4)* After an answer, a line saying how many tool calls it used, and a `/tools` command that lists them.
- *(US5)* A calmer, more modern look: a fixed dark palette as foreground colours, on terminals that support it, with no change to any word the user reads.

**Out of scope**
- Streaming the *answer* to stdout (only an unchecked draft on stderr, US2), interrupting the server's generation, panes, mouse (so no clicking: US4 uses a command), markdown or syntax rendering, persistent history, slash commands other than `/exit`, `/quit` and `/tools`. Colour is in scope only as US5 describes it (foreground colours, no layout engine).
- Conversation memory: every question is independent (`ask()` has no history).
- Starting or stopping `llama-server`. Server lifecycle is manual (Spec 002 C9).
- Any change to retrieval, prompts, models, thresholds or the citation checker (Article VII.5).
- A full-screen or richer UI (a possible later spec).

## 3. User story and acceptance criteria

### US1 (P1): Ask questions interactively

*As a new developer, I want to type a question and read a cited answer without composing a long command each time.*

- **AC-1.1** `codecompass [REPO]` starts a session for the repository containing `REPO` (default: the current directory). The repository root is found with `git rev-parse --show-toplevel`, so running it from the repo root or from any subdirectory uses the same root. The root is printed in the startup banner and every index, retrieval and tool call uses it, never the working directory. Options `--profile`, `--config` and `--index-dir` behave as in the `ask` CLI (Spec 002 AC-8.1).
- **AC-1.2** At the prompt, each non-blank line is one question. The answer is written to stdout exactly as `QueryResult.answer` (no reformatting, nothing added to stdout around it), then the prompt returns. Blank lines are ignored.
- **AC-1.3** A flagged answer is never shown as verified: the TUI prints the banner and marks produced by the formatter and never strips, reorders or restyles them (Article VI.3).
- **AC-1.4** The reranker, embedder and generator client are created once per session and reused for all questions. Model weights load on first use, not at startup, so the prompt appears immediately.
- **AC-1.5** While a question runs, one status line is shown on stderr and erased when the answer arrives. It is shown only when stderr is a terminal.
- **AC-1.6** `/exit`, `/quit` and Ctrl-D end the session with exit code 0. At the prompt, Ctrl-C does not exit; it prints a hint to use `/exit` or Ctrl-D.
- **AC-1.7** Ctrl-C while a question is running abandons that question and returns to the prompt. The session stays usable.
- **AC-1.8** An error during one question (generator unreachable, no index, timeout) is printed to stderr as `error: <message>` and the prompt returns. The session does not crash and no traceback is shown.
- **AC-1.9** Startup fails loudly (message on stderr, exit code 1) for: a path that is not a git repository, an unknown profile, or an invalid config (Article VIII.4).
- **AC-1.10** At startup the session prints the active profile and resolved model id once to stderr (Article VIII.4). If the generator's health check fails, it prints a one-line warning with the `llama-server` start command for that profile, and still starts.
- **AC-1.11** When stdin is not a terminal, no prompt, banner or status line is printed; each input line is answered in turn and output is just the answers. EOF ends the session.
- **AC-1.13** *(amended by AC-3.1 below: the files are layered, not "first wins")* The config file is the first that exists of: `--config PATH`, `<repo root>/codecompass.toml`, `~/.config/codecompass/codecompass.toml` (or `$XDG_CONFIG_HOME/codecompass/codecompass.toml`). If none exists, built-in defaults apply. The file used (or "built-in defaults") is named in the startup banner. A `--config` path that does not exist is a startup error, not a fallback.
- **AC-1.12** Typing `codecompass` works after `pip install -e .` in the virtual environment, with no new runtime dependency.

### US2 (P2): See the model write (unchecked draft)

*As a developer waiting on a slow local model, I want to see it working, without ever mistaking unchecked text for a verified answer.*

Measured on the dev machine with the 7B on a CPU-only `llama-server`: one generator call took 85-94 s. Without a draft the terminal shows only "Thinking…" for that whole time.

- **AC-2.1** On a terminal, the text the generator writes appears on stderr as it is produced, and it is unmistakably a draft:
  - a header before the first character: `⚠ DRAFT — NOT CHECKED. The model is still writing. Do not rely on this text.`;
  - **every** draft line starts with the marker `draft │ ` and is dimmed, so any line copied or left in the scrollback still says what it is;
  - no control characters from the model (escape sequences, carriage returns) reach the terminal, so a draft cannot restyle or overwrite what is on screen;
  - nothing is written to stdout until the citation check has run.
- **AC-2.2** When the answer is ready, stderr shows `Draft finished after N s.` and then `── Checked answer (replaces the draft above) ──`, and stdout receives exactly `QueryResult.answer` as in AC-1.2. The draft is never on stdout and is never described as verified (Articles VI.1, VI.3, VI.5). If the check flags the answer, the banner of AC-1.3 appears with it. If the question fails or is interrupted after some draft was shown, stderr shows `(draft discarded)` before the error or `Interrupted.` line. If no draft text arrived (for example only tool rounds), none of this chrome appears.
- **AC-2.3** A generator round that is a tool request (text starting with `<tool>`) is not shown as draft text; the status line names the tool instead (Article V.4 stays the audit record).
- **AC-2.4** With `--no-draft`, or when stderr is not a terminal, nothing is streamed and behaviour is exactly AC-1.2 to AC-1.5.
- **AC-2.5** `ask()` still prints nothing (AC-9.2). It takes an optional `on_draft(text)` callback; with none given, behaviour and the audit log are unchanged. Streaming lives only in the generator wrapper (Article VIII.2); if the server cannot stream, the generator falls back to one non-streamed call.
- **AC-2.6** The citation checker, the audit log and the per-query timings are identical with and without streaming.

### US3 (P2): No wait at the first question

*As a developer, I do not want the first question to pay for indexing and model loading on top of answering.*

Measured: the first question took 352 s (index 193 s, re-ranking 65 s, generation 94 s). On the GPU the re-ranker takes 2 s instead of 52 s per question and the embedder is 27x faster, with matching results.

- **AC-3.1** *(amends AC-1.13, pending approval)* The user-level file is a base layer and the repo file overrides it section by section, so personal settings (profile, devices) apply in repositories that have their own `codecompass.toml`. A `[generator.profiles.X]` table replaces the whole profile of that name. `--config` replaces both. The banner lists every file used.
- **AC-3.2** On a terminal, at start-up a background thread brings the index current and loads the embedder and re-ranker, so the work overlaps with the user typing. Nothing is printed unless a question is asked before it finishes, in which case the status line says `Preparing index and models…` and the question waits for it.
- **AC-3.3** A warm-up failure is not shown at start-up; the same error appears when the question is asked, exactly as without warm-up (AC-1.8). No second index run starts if the warm-up is still running.
- **AC-3.4** Piped input does not warm up (the questions are already available). `/exit` during a warm-up ends the session at once.
- **AC-3.5** The README documents putting `device = "cuda"` under `[embedder]` and `[reranker]` in the user-level file, with the measured gain and the GPU memory use (re-ranker peak 3.2 GiB), and the memory trade-off with a GPU `llama-server`.

### US4 (P2): See which tools the answer used

*As a developer, I want to know whether an answer relied on tool calls (git history, file reads, extra searches) and which ones, so I can judge how it was put together.*

- **AC-4.1** After each answered question, when stdin and stderr are terminals, one line on stderr gives the number of tool calls that ran: `▸ 3 tools called — type /tools to see them`, `▸ 1 tool called — type /tools to see them`, or `▸ No tools called`. A tool call is an executed entry of the query's audit log `tool_calls` (an entry with a `tool` name). A malformed request that ran nothing, a request refused after the round limit, and calls ignored because tools are off are not counted. Nothing is added to stdout (AC-1.2).
- **AC-4.2** The exact line `/tools` is a command, not a question: it is never sent to the model and does not use a round. It prints, to stderr, the tool calls of the last answered question in the order they ran, one block each: the round number, the tool name, its arguments, `cache hit` or `cache miss`, the first line of its result, and `failed` when it returned an error. Malformed requests and requests refused after the round limit each get a line saying so, so every round is accounted for. With no tool calls it prints `No tools were called for the last question.`; before any question has been answered, `No question has been answered yet.`
- **AC-4.3** Everything the model wrote that `/tools` prints (arguments, result line) has its control characters removed and is cut with `…` when long, so tool text cannot restyle or overwrite the terminal (the rule of AC-2.1).
- **AC-4.4** The count and the list come from the query's audit log (Article V.4); they are not recomputed and `ask()` is unchanged. A question that fails or is interrupted does not replace the list of the last answered question. A result without an audit log counts as no tool calls.
- **AC-4.5** `/tools` also works with piped input (it prints to stderr; stdout stays answers only, AC-1.11), but the count line of AC-4.1 is for terminals only. Any other line, including `/tools now`, is a question.

### US5 (P3): A more modern look

*As a developer, I want the terminal to look clear and pleasant, without giving up anything that makes an answer safe to read.*

- **AC-5.1** Two themes from the Rosé Pine family, as foreground colours only; the terminal keeps its own background. `dark` is Rosé Pine Moon (the author's palette), `light` is Rosé Pine Dawn, its official light counterpart. Each colour has a role (Plan 004 section 8: accent for the title, prompt and `[N]` markers; info for the status line, the tools line and the `Sources` heading; warn for the stale-index warning, the note lines and the draft header; tag for ` (not cited)`; danger for errors, the flagged banner and `[UNVERIFIED]`; ok for `cache hit`; muted for details). Every colour used for text keeps a contrast ratio of at least 3:1 against its theme's own background and against pure black (`dark`) or pure white (`light`), the WCAG 2 minimum for large text and interface components; a test checks it. The `danger` colour (errors, the flagged banner, `[UNVERIFIED]`) keeps at least 4.5:1 (the WCAG 2 minimum for normal text). In `light`, `danger` is a custom darker shade of Dawn's love (`#91344f`, same hue, lower lightness) because Dawn's own colours are too pale for it. No role depends on colour alone: the words (`WARNING`, `Note:`, `[UNVERIFIED]`, `cache hit`) carry the meaning.
- **AC-5.2** Colour is used only when the stream is a real terminal (its file descriptor is a tty), `NO_COLOR` is unset or empty, `--no-color` is absent and `TERM` is not `dumb`. It is 24-bit when `COLORTERM` is `truecolor` or `24bit` or `WT_SESSION` is set, the nearest of the 256 colours when `TERM` contains `256color`, and off otherwise. A pipe or file never receives an escape sequence (AC-1.2, AC-1.11).
- **AC-5.3** What is coloured outside the answer: the startup banner (title, muted details), the prompt, the status line, the AC-4.1 line and `/tools`, the `error:` and `warning:` prefixes, and the draft header. The text of every one of these is unchanged. Draft lines stay dimmed and marked `draft │ ` (AC-2.1).
- **AC-5.4** *(amends AC-1.2 and AC-1.3)* On a terminal with colour on, the TUI may add colour *around* these parts of the answer and nothing else: the flagged banner and the note lines (whole lines), the `[UNVERIFIED] ` mark, the ` (not cited)` tags, inline `[N]` markers, the `Sources` heading, and the stale-index warning. With every escape sequence removed, stdout is exactly `QueryResult.answer`: no word is added, removed or reordered. A flagged answer keeps its banner and marks in the warning colours (love, gold). The unreferenced-sources banner and `[NOT REFERENCED IN ANSWER] ` mark of Spec 002 AC-4.10 (an open pull request when this was written) get the `warn` role in a small follow-up once they are in `main`; until then the TUI colours only what `main` produces. No colour is used to suggest an answer is verified, and "verified" is never styled as "true" (Article VI.3, VI.5).
- **AC-5.5** Nothing here adds a dependency, a thread or a full-screen mode (Article XI.1). `--no-color` and `NO_COLOR` give today's plain output exactly.
- **AC-5.6** `--theme auto|dark|light` (default `auto`), and the environment variable `CODECOMPASS_THEME` with the same values (the flag wins). `auto` picks `light` when `COLORFGBG` is set and its last field, the background colour index, is `7` or `15`, and `dark` otherwise (best effort: only some terminals set it; others use `--theme light`). Any other value is a startup error (`error: ...`, exit code 1), as an unknown profile is (AC-1.9). The theme changes colours only; it never changes a word.

## 4. Constitution check

| Article | How this spec respects it |
|---|---|
| I, VI | Prints `ask()`'s checked answer unmodified. The TUI has no citation logic. |
| VIII.2, VIII.4, IX.7 | Never talks to `llama-server` itself; profile and model id logged at start; required tests use the stubs and need no model. |
| X.3 | Stale-index warning and flagged states reach the user because the answer text is printed whole. |
| XI.1 | Standard library only; no new component or dependency. |
| VI.3, VI.5 *(US5)* | Colour is added around the banner and marks, never in place of them; with escapes removed the answer is byte-identical; no success colour is ever used for a citation. Amends AC-1.2 and AC-1.3, which said the TUI never restyles the banner (the intent was that it never hides or weakens it). |
| VI.1, VI.3 *(US2)* | The draft is on stderr, labelled unchecked, and the checked answer is the only thing on stdout. Whether showing unchecked text at all is allowed by VI.1 ("before any answer is shown") is for the reviewer to confirm; see Q5. |
| VIII.2 *(US2)* | Streaming is implemented only inside the generator wrapper; no other module talks to `llama-server`. |
| III.2, VII.5 *(US3)* | Warm-up uses only `ensure_current` and the existing models; it changes no pipeline behaviour, so no evaluation re-run is needed. Switching a model to `cuda` is a device change, not a model change, and does not alter the index identity. |

## 5. Decisions

Q1, Q2 and Q4 were approved by the team member on 2026-11-01 with the recommended options. Q3 is still open.

| # | Question | Notes |
|---|---|---|
| Q1 | **Models are reloaded on every question today.** `ask()` builds a new `BgeReranker` and the offline default `CodeEmbedder` on each call, and plan 002 O1 ("load models once per process") is not implemented for the defaults. AC-1.4 needs it. Online code may not import `CodeEmbedder` (Article II.2). Options: (a) cache the default reranker in `ask()` and the default embedder inside `codecompass.offline`, keyed by config; (b) have `ask()` accept and keep a session object; (c) accept a reload per question. | Recommended: (a). It is a small change to Spec 001 and 002 code, so it is task T0.1 here and needs your approval. |
| Q2 | **Packaging.** `pyproject.toml` has no `[build-system]` or `[project.scripts]`. `pip install -e .` needs a build backend (setuptools, a build-time dependency not listed in `requirements.txt`) and an explicit package list, since the repo root also holds `tests/` and `docs/`. | Adding a build backend is a dependency decision, so I will not do it unprompted. |
| Q4 | **Where does `codecompass.toml` come from when run in another repo?** The `ask` CLI reads `./codecompass.toml` from the working directory. For a repo that has none, the built-in defaults apply (profile `dev`, the 14B). Options: (a) `--config`, then `<repo root>/codecompass.toml`, then built-in defaults; (b) also a user-level file such as `~/.config/codecompass/codecompass.toml`. | Recommended: (b), so your `dev-7b` choice follows you into any repo. Needs a decision because it adds a config location. |
| Q5 | **RESOLVED (yes, 2026-11-01), with the requirement that the draft is obviously a draft (AC-2.1, AC-2.2).** *Question was:* does a stderr draft break Article VI.1? VI.1 says the checker must verify before "any answer is shown". The draft is labelled unchecked and goes to stderr, with the checked answer alone on stdout, so the plan treats it as a progress display. A stricter reading would need a constitution amendment first. | Approved by the team member; the PR reviewer still confirms. |
| Q6 | **RESOLVED (approved 2026-11-01).** User-level base layer (AC-3.1). It changes Q4 ("first file wins"), and was needed because this repo has its own `codecompass.toml`, which hid the user-level file. | Done in T2.1. |
| Q3 | Does the session accept an optional readline-style line editor? | Plan assumes the standard library `readline` when present (history and arrow keys in memory only), nothing otherwise. |
| Q7 | **RESOLVED (2026-11-02, author).** How does "click on the tools" work? | A command, `/tools` (AC-4.2). A real mouse click needs a full-screen mode: a new dependency (for example `prompt_toolkit`) or POSIX-only code, since the standard library `curses` is not on Windows. Both conflict with XI.1 and the cross-platform work of Spec 005. |
| Q8 | **RESOLVED (2026-11-02, author).** How far does "more modern" go? | Colour and a cleaner layout while staying a scrolling prompt (US5). A full-screen layout with your `#232136` background is a possible later spec. |
| Q9 | **RESOLVED (2026-11-02, author).** May colour be added to the flagged banner (it amends AC-1.3)? | Yes, with the words and position unchanged (AC-5.4). |
| Q10 | **RESOLVED (2026-11-02, author).** Does "what all the tools are" mean the tools the answer *called*, or also the tools *available*? | The tools the answer called (AC-4.2). No "available tools" line. |
| Q11 | **RESOLVED (2026-11-02, author).** The palette is built for dark backgrounds; what about light terminals? | A second theme, `light` = Rosé Pine Dawn (AC-5.1, AC-5.6), chosen automatically when the terminal says its background is light, or with `--theme light`. `NO_COLOR` and `--no-color` remain for plain output. |
| Q12 | **RESOLVED (2026-11-02, author).** Rosé Pine Dawn's own gold (2.1:1 on its background), rose (2.6:1) and muted (2.7:1) are too pale to read as text. What does `light` use for errors? | A custom darker colour: `#91344f`, Dawn's love at the same hue (343°) and lower lightness, 6.8:1 on `#faf4ed` and 7.5:1 on white (AC-5.1). `warn` keeps Dawn's love (3.8 / 4.2:1); Dawn's gold, rose and muted are not used. |
