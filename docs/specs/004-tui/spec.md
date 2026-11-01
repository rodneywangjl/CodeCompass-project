# Spec 004: Minimal Terminal UI

**Project:** CodeCompass (SE201 G1-T1) | **Status:** Implemented (T0.1 to T2.5); README in T2.6
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

**Out of scope**
- Streaming the *answer* to stdout (only an unchecked draft on stderr, US2), interrupting the server's generation, panes, colours, mouse, markdown or syntax rendering, persistent history, slash commands other than exit.
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

## 4. Constitution check

| Article | How this spec respects it |
|---|---|
| I, VI | Prints `ask()`'s checked answer unmodified. The TUI has no citation logic. |
| VIII.2, VIII.4, IX.7 | Never talks to `llama-server` itself; profile and model id logged at start; required tests use the stubs and need no model. |
| X.3 | Stale-index warning and flagged states reach the user because the answer text is printed whole. |
| XI.1 | Standard library only; no new component or dependency. |
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
