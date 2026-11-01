"""Minimal terminal UI (Spec 004): `codecompass` prompt loop over ask()."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from codecompass.online import tui_live, tui_view

PROMPT = "> "
STATUS = "Thinking…"
CLEAR_LINE = "\r\x1b[K"
DRAFT_HEADER = "⚠ DRAFT — NOT CHECKED. The model is still writing. Do not rely on this text."
DRAFT_MARK = "draft │ "
CHECKED_MARK = "── Checked answer (replaces the draft above) ──"
DIM, RESET = "\x1b[2m", "\x1b[0m"
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # all but \n and \t
EXIT_COMMANDS = ("/exit", "/quit")
TOOLS_COMMAND = "/tools"
THEME_COMMAND = "/theme"
CONFIG_NAME = "codecompass.toml"
DEFAULT_PORT = 8080  # llama-server port when the configured URL names none


def _say(stream, text: str) -> None:
    stream.write(text)
    stream.flush()


def _paint(style, text: str, role: str) -> str:
    """*text* in the colour of *role* when there is a style; else unchanged (Spec 004 US5)."""
    return style.paint(text, role) if style else text


class _DraftPrinter:
    """Show the model's unchecked text on stderr so it cannot be taken for the answer.

    A header first, every line marked and dimmed, control characters removed
    (Spec 004 AC-2.1, AC-2.2).
    """

    def __init__(self, stderr, status: bool, chrome=None) -> None:
        self._stderr, self._status, self._chrome = stderr, status, chrome
        self.started, self._at_line_start, self._t0 = False, True, 0.0

    def write(self, piece: str) -> None:
        piece = _CONTROL.sub("", piece)
        if not piece:
            return
        if not self.started:
            self.started, self._t0 = True, time.monotonic()
            _clear(self._stderr, self._status)
            _say(self._stderr, _paint(self._chrome, DRAFT_HEADER, "warn") + "\n")
        for part in re.split("(\n)", piece):
            if part == "\n":
                if self._at_line_start:  # a blank line is still a marked line
                    _say(self._stderr, f"{DIM}{DRAFT_MARK}{RESET}")
                _say(self._stderr, "\n")
                self._at_line_start = True
            elif part:
                prefix = DRAFT_MARK if self._at_line_start else ""
                _say(self._stderr, f"{DIM}{prefix}{part}{RESET}")
                self._at_line_start = False

    def _end_line(self) -> None:
        if not self._at_line_start:
            _say(self._stderr, "\n")
            self._at_line_start = True

    def finish(self) -> None:
        """The checked answer is ready: close the draft."""
        self._end_line()
        _say(self._stderr, f"Draft finished after {int(time.monotonic() - self._t0)} s.\n"
                           f"{CHECKED_MARK}\n")

    def discard(self) -> None:
        """The question failed or was interrupted after some draft was shown."""
        self._end_line()
        _say(self._stderr, "(draft discarded)\n")


def _end_question(printer, stderr, status: bool, *, failed: bool) -> None:
    """Close what the question showed on stderr: the status line, or the draft."""
    if printer is not None and printer.started:
        printer.discard() if failed else printer.finish()
    else:
        _clear(stderr, status)


def run_session(answer, *, stdin, stdout, stderr, draft: bool = False,
                tool_rounds=None, style=None, chrome=None, theme=None,
                live_tools: bool = False, spinner: bool = False,
                spinner_interval: float = 1.0, boxed: bool = False, box_width=None,
                status_info=None, markdown: bool = False) -> int:
    """Read questions from *stdin*, print ``answer(question)`` to *stdout* (Spec 004).

    Only answers go to stdout. The prompt, status line, hints and errors go to
    stderr, and only when both streams are terminals (AC-1.5, AC-1.11). With *draft*
    and a terminal on stderr, ``answer(question, on_draft=...)`` is used and the
    model's unchecked text is shown on stderr as it is written (AC-2.1). Returns 0
    on /exit, /quit or end of input; nothing a question does ends the session
    (AC-1.7, AC-1.8).

    *tool_rounds*, if given, is called after each answered question and returns that
    question's tool records (the audit log's ``tool_calls``). On a terminal a line on
    stderr then gives the count, and the line ``/tools`` lists the calls of the last
    answered question (AC-4.1, AC-4.2); a failed or interrupted question leaves the
    previous list in place (AC-4.4).

    *style*, if given, is a ``tui_view.Style``: each answer is written through
    ``style.answer``, which only adds colour (AC-5.4). *chrome* is the same kind of
    object for stderr: it colours the prompt, status, tool line, ``/tools``, ``error:``
    and the draft header, and never changes a word (AC-5.3). *theme*, a
    ``tui_view.ThemeSwitch``, makes ``/theme`` and ``/theme X`` commands that change
    the colour of what follows (AC-5.7); without one they are ordinary lines. With
    *live_tools* and a terminal on stderr, ``answer`` is also given ``on_tool`` and
    each tool call is shown as it finishes (AC-6.2). With *spinner* and a terminal on
    stderr the status line is a spinner with the elapsed time, redrawn by one thread;
    every stderr write during a question then goes through one lock (AC-6.3). With
    *boxed* the prompt is a rounded box with *status_info* (repo, profile, model)
    under it, *box_width* columns wide or the terminal's width (AC-6.4). With
    *markdown* the answer's markdown is styled (AC-6.5).
    """
    prompting = stdin.isatty() and stderr.isatty()
    status = stderr.isatty()
    answered, last_rounds = False, []
    in_box = boxed and prompting
    while True:
        if in_box:
            width = box_width or shutil.get_terminal_size((80, 24)).columns
            _say(stderr, tui_live.prompt_box(width, status_info or ("", "", ""), chrome))
        elif prompting:
            _say(stderr, _paint(chrome, PROMPT.rstrip(), "accent") + PROMPT[len(PROMPT.rstrip()):])
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            _say(stderr, (tui_live.LEAVE_BOX_UNREAD if in_box else "\n")
                 + "(type /exit or press Ctrl-D to quit)\n")
            continue
        if line == "":  # end of input
            if prompting:
                _say(stderr, tui_live.LEAVE_BOX_UNREAD if in_box else "\n")
            return 0
        if in_box:
            _say(stderr, tui_live.LEAVE_BOX)
        question = line.strip()
        if not question:
            continue
        if question in EXIT_COMMANDS:
            return 0
        if theme is not None and (question == THEME_COMMAND
                                  or question.startswith(THEME_COMMAND + " ")):
            reply = theme.command(question[len(THEME_COMMAND):].strip())
            _say(stderr, _paint(chrome, reply, "muted") + "\n")  # in the new colours
            continue
        if question == TOOLS_COMMAND:
            _say(stderr, (tui_view.format_tools(last_rounds, chrome) if answered
                          else _paint(chrome, "No question has been answered yet.", "muted")) + "\n")
            continue
        printer = _DraftPrinter(stderr, status, chrome) if draft and status else None
        spin = (tui_live.Spinner(lambda text: _say(stderr, text), style=chrome,
                                 interval=spinner_interval) if spinner and status else None)
        if spin:
            spin.start()
        elif status:
            _say(stderr, _paint(chrome, STATUS, "info"))
        options = {}
        if printer:
            def draft(piece, printer=printer, spin=spin):
                if spin:
                    spin.stop()  # the draft replaces the spinner; it does not come back
                printer.write(piece)
            options["on_draft"] = draft
        if live_tools and status:
            def show_tool(entry, spin=spin):
                block = CLEAR_LINE + "\n".join(tui_live.tool_lines(entry, chrome)) + "\n"
                if spin:
                    with spin.lock:  # the whole block, then the spinner again
                        spin.pause()
                        _say(stderr, block)
                        spin.resume()
                else:
                    _say(stderr, block + _paint(chrome, STATUS, "info"))
            options["on_tool"] = show_tool
        try:
            try:
                text = answer(question, **options)
            finally:
                if spin:
                    spin.stop()
        except KeyboardInterrupt:
            _end_question(printer, stderr, status, failed=True)
            _say(stderr, "Interrupted.\n")
            continue
        except Exception as exc:  # noqa: BLE001 (one failed question must not end the session)
            _end_question(printer, stderr, status, failed=True)
            _say(stderr, f"{_paint(chrome, 'error:', 'danger')} {str(exc) or type(exc).__name__}\n")
            continue
        _end_question(printer, stderr, status, failed=False)
        if style is None:
            shown = text
        else:
            shown = tui_view.render_markdown(text, style) if markdown else style.answer(text)
        _say(stdout, shown if text.endswith("\n") else shown + "\n")
        answered = True
        if tool_rounds is not None:
            last_rounds = list(tool_rounds() or [])
            if prompting:
                _say(stderr, tui_view.summary_line(last_rounds, chrome) + "\n")


def _clear(stderr, status: bool) -> None:
    if status:
        _say(stderr, CLEAR_LINE)


def _repo_root(path) -> Path:
    """The git repository root containing *path* (AC-1.1)."""
    p = Path(path).expanduser()
    if not p.exists():
        raise ValueError(f"path does not exist: {p}")
    if p.is_file():
        p = p.parent
    try:
        run = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
    except FileNotFoundError:
        raise ValueError("git is not installed or not on PATH") from None
    if run.returncode != 0:
        raise ValueError(f"{p} is not a git repository")
    return Path(run.stdout.strip())


def _is_windows() -> bool:
    return sys.platform == "win32"


def _user_config_dir() -> Path:
    """$XDG_CONFIG_HOME if set (an explicit choice, any platform), else %APPDATA% on
    Windows, else ~/.config (Spec 005 AC-4.5)."""
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"])
    if _is_windows() and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"])
    return Path.home() / ".config"


def _prepare_terminal(*streams) -> None:
    """Make the terminal safe for what we print (Spec 005 AC-4.3, AC-4.4).

    Windows consoles need ANSI escape handling switched on (running an empty command
    does it); on every platform, characters the terminal's encoding cannot show are
    replaced rather than raising.
    """
    if _is_windows():
        os.system("")
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):  # a closed or unusual stream: leave it
                pass


def _find_configs(root: Path, explicit: str | None) -> list[Path]:
    """The config files in force, highest priority first (AC-1.13, AC-3.1).

    --config alone, else the repo file over the user-level file; either may be absent.
    """
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError(f"config file not found: {path}")
        return [path]
    candidates = (root / CONFIG_NAME, _user_config_dir() / "codecompass" / CONFIG_NAME)
    return [path for path in candidates if path.is_file()]


def _start_warm_up(warm_up, root: Path, config, index_dir) -> threading.Thread:
    """Run *warm_up* in the background while the user types (Spec 004 AC-3.2).

    A daemon thread, so /exit never waits for it. Its errors are dropped here: the
    first real question hits the same problem and reports it (AC-3.3).
    """
    def run() -> None:
        try:
            warm_up(root, config=config, index_dir=index_dir)
        except Exception:  # noqa: BLE001
            pass

    thread = threading.Thread(target=run, name="codecompass-warm-up", daemon=True)
    thread.start()
    return thread


def _start_command(profile, server_url: str) -> str:
    from codecompass.online.generator.server import launch_command
    folder = "C:\\path\\to\\" if _is_windows() else "/path/to/"
    model = folder + (profile.gguf_file or "<model>.gguf")
    port = urlsplit(server_url).port or DEFAULT_PORT
    command = launch_command(profile, model, port=port)
    return subprocess.list2cmdline(command) if _is_windows() else shlex.join(command)


def _check_generator(generator, profile, server_url: str, stderr, chrome=None) -> None:
    """Warn (never fail) when the generator is down or does not match the profile (AC-1.10)."""
    try:
        if generator.health_check():
            return
        message = (f"llama-server is not reachable at {server_url}. Start it with:\n"
                   f"  {_start_command(profile, server_url)}")
    except Exception as exc:  # noqa: BLE001 (a mismatched server explains itself)
        message = str(exc) or type(exc).__name__
    _say(stderr, f"{_paint(chrome, 'warning:', 'warn')} {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codecompass",
        description="Ask questions about a git repository, answered with checked citations.")
    parser.add_argument("repo", nargs="?", default=".",
                        help="path inside the git repository (default: current directory)")
    parser.add_argument("--profile", help="generator profile (default: GENERATOR_PROFILE "
                                          "or the config default)")
    parser.add_argument("--config", help="codecompass.toml (default: <repo root>/"
                                         "codecompass.toml, then your user-level codecompass.toml)")
    parser.add_argument("--index-dir", help="override the index directory")
    parser.add_argument("--no-draft", action="store_true",
                        help="do not show the model's unchecked draft while it writes")
    parser.add_argument("--theme", help="colour theme: auto (the default: light when the terminal "
                                         "says its background is light), dark (Rose Pine Moon) or "
                                         "light (Rose Pine Dawn); the CODECOMPASS_THEME "
                                         "environment variable does the same")
    parser.add_argument("--plain", action="store_true",
                        help="no live interface (tool lines as they run, spinner, boxed prompt, "
                             "styled markdown); plain output")
    parser.add_argument("--no-color", action="store_true",
                        help="use no colour (the NO_COLOR environment variable does the same)")
    return parser


def main(argv=None, *, stdin=None, stdout=None, stderr=None) -> int:
    """`codecompass [REPO]`: start an interactive session (Spec 004)."""
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    _prepare_terminal(stdout, stderr)
    args = _parser().parse_args(argv)
    style = chrome = None  # colour for the answer (stdout) and for the interface (stderr)
    try:
        # each stream is coloured only if it is itself a terminal (AC-5.2, AC-5.6); the theme
        # comes first so that every later error can already be painted
        theme = tui_view.theme_name(args.theme, os.environ)
        out_level = tui_view.color_level(stdout, os.environ, no_color=args.no_color)
        err_level = tui_view.color_level(stderr, os.environ, no_color=args.no_color)
        # what each stream could show, ignoring NO_COLOR: /theme rose-pine may override it (AC-5.7)
        could = {name: value for name, value in os.environ.items() if name != "NO_COLOR"}
        out_could = tui_view.color_level(stdout, could)
        err_could = tui_view.color_level(stderr, could)
        style = (tui_view.Style(out_level, theme, capability=out_could)
                 if out_could != "none" else None)
        chrome = (tui_view.Style(err_level, theme, capability=err_could)
                  if err_could != "none" else None)
        root = _repo_root(args.repo)
        config_files = _find_configs(root, args.config)
        # heavy model libraries are not imported here: they load on the first question
        import codecompass.online as online
        from codecompass.online.config import load_online_config_layers
        from codecompass.online.generator.llama import LlamaServerGenerator
        from codecompass.online.generator.profiles import resolve_profile
        config = load_online_config_layers(reversed(config_files))
        name, profile = resolve_profile(config, args.profile)
        generator = LlamaServerGenerator(profile, server_url=config.generator.server_url,
                                         timeout_seconds=config.generator.timeout_seconds)
    except Exception as exc:  # noqa: BLE001 (startup problems are reported, not traced)
        _say(stderr, f"{_paint(chrome, 'error:', 'danger')} {exc}\n")
        return 1
    if stdin.isatty() and stderr.isatty():
        details = (f"repo: {root}", f"profile {name} ({profile.model_id})",
                   f"config: {', '.join(map(str, config_files)) or 'built-in defaults'}")
        _say(stderr, "".join(f"{_paint(chrome, 'codecompass:', 'accent')} "
                             f"{_paint(chrome, detail, 'muted')}\n" for detail in details)
                     + _paint(chrome, "Type a question. /exit or Ctrl-D to quit.", "muted") + "\n")
    _check_generator(generator, profile, config.generator.server_url, stderr, chrome)

    warm = (_start_warm_up(online.warm_up, root, config, args.index_dir)
            if stdin.isatty() and stderr.isatty() else None)

    last = {"rounds": []}  # the audit log's tool records of the last answered question

    live = (stdin.isatty() and tui_live.is_terminal(stderr, os.environ)
            and not args.plain)  # a real terminal, and not --plain (AC-6.1)

    def answer(question: str, on_draft=None, on_tool=None) -> str:
        if warm is not None and warm.is_alive():  # only the first question can find it so
            with tui_live.LOCK:  # shared with the spinner, so the two never interleave
                tui_live.pause_active()  # keep the message readable while we wait
                _say(stderr, f"{CLEAR_LINE}{_paint(chrome, 'Preparing index and models…', 'info')}")
            warm.join()
            with tui_live.LOCK:
                _say(stderr, f"{CLEAR_LINE}{_paint(chrome, STATUS, 'info')}")
                tui_live.resume_active()  # and the spinner is back at once
        extra = {"on_tool": on_tool} if on_tool is not None else {}
        result = online.ask(root, question, config=config, profile=name,
                            index_dir=args.index_dir, generator=generator,
                            on_draft=on_draft, **extra)
        last["rounds"] = (getattr(result, "audit_log", None) or {}).get("tool_calls", [])
        return result.answer

    return run_session(answer, stdin=stdin, stdout=stdout, stderr=stderr,
                       draft=not args.no_draft, tool_rounds=lambda: last["rounds"],
                       style=style, chrome=chrome,
                       theme=tui_view.ThemeSwitch(theme, [s for s in (style, chrome) if s]),
                       live_tools=live, spinner=live, boxed=live,
                       status_info=(root.name, name, profile.model_id), markdown=live)
