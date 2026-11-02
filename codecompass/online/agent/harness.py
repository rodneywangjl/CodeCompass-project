"""Bounded agent loop: generate, run allow-listed tools, answer (Article V)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from codecompass.online.agent.cache import ToolCache
from codecompass.online.agent.tool_parser import (
    malformed_blocks, parse_tool_calls, strip_tool_blocks)
from codecompass.online.agent.tools import ToolContext, ToolOutput, cap_output, execute
from codecompass.online.context import format_context

_INTRO = """You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository."""

_RULES = [
    "Cite every claim with numbered markers [1], [2], etc.",
    """End with a Sources section listing each citation, one per line. Start
   each line with its marker, with no bullet or number before it. For code,
   copy the chunk's header line exactly (the part before " | "). Example:
   Sources
   [1] file/path.py, lines X-Y (indexed at <7-char hash>)
   [2] Commit <7-char hash>, "<subject>", <author>, <date>""",
    """If the evidence is insufficient, say what you could not determine.
   Do NOT guess or make up file names, line numbers, or commit hashes.""",
    """If the commit history gives no reason for the code (e.g. vague commit
   messages, or no history found), say so. Do NOT invent a reason.""",
]
_TOOL_RULE = """If the code context is not enough, request ONE tool per reply:
   <tool>search_again(query="names or words to search for")</tool> finds more code
   <tool>open_file(path="file/path.py", lines="X-Y")</tool> reads lines of a file
   <tool>open_file(path="file/path.py")</tool> lists a file's functions with lines
   <tool>git_blame(path="file/path.py", lines="X-Y")</tool> shows who changed lines
   <tool>git_log(path="file/path.py", n=10)</tool> lists recent commits of a file
   The result comes back in a <tool_result>...</tool_result> block. It is
   evidence you may cite, just like the code context."""

_FORMAT_HINT = """Write one tool call on its own, with keyword arguments, exactly like:
<tool>search_again(query="names or words to search for")</tool>
<tool>open_file(path="file/path.py", lines="X-Y")</tool>
<tool>git_blame(path="file/path.py", lines="X-Y")</tool>
<tool>git_log(path="file/path.py", n=10)</tool>"""

FINAL_MESSAGE = ("Tool limit reached: no more tools are available. Answer now, using "
                 "only the evidence above, and state what you could not determine.")


def system_prompt(*, tools_enabled: bool) -> str:
    """The D14 prompt; without tools, the tool rule (rule 3) is left out (D17)."""
    rules = _RULES[:2] + ([_TOOL_RULE] if tools_enabled else []) + _RULES[2:]
    numbered = "\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, 1))
    return f"{_INTRO}\n\nRules:\n{numbered}"


def user_message(question: str, chunks: list) -> str:
    """The question, then the retrieved chunks as plain text (Plan D3)."""
    context = format_context(chunks) if chunks else "(none retrieved)"
    return f"Question: {question}\n\nCode context:\n\n{context}"


def _attr(value) -> str:
    return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def tool_result_message(call, output: ToolOutput) -> str:
    """The D16 wrapper; an empty history is said plainly (Article V.5)."""
    attrs = "".join(f' {k}="{_attr(v)}"' for k, v in {"tool": call.tool, **call.args}.items())
    if output.error:
        attrs += f' error="{_attr(output.text)}"'
        body = output.text
    elif not output.commits:
        body = f"No commit history found for {call.args.get('path', '')}"
        if call.args.get("lines"):
            body += f" lines {call.args['lines']}"
    else:
        body = output.text
    return f"<tool_result{attrs}>\n{body}\n</tool_result>"


def malformed_result_message(block: str) -> str:
    """The D16 error wrapper for a <tool> block that could not be parsed (T8.6)."""
    snippet = " ".join(block.split())[:120] or "(empty)"
    return (f'<tool_result error="malformed tool call">\n'
            f"error: your tool call could not be read: {snippet!r}\n"
            f"{_FORMAT_HINT}\n</tool_result>")


def make_tool_runner(repo, commit: str, settings, count_tokens, *, handles=None,
                     reranker=None, retrieval=None, seen=None):
    """execute() at the indexed commit, capped (D4) and cached per query (D8).

    handles, reranker and retrieval let search_again search the index; seen holds
    the ids of chunks already in context (Plan D18).
    """
    context = ToolContext(count_tokens=count_tokens, handles=handles, reranker=reranker,
                          retrieval=retrieval, seen=set(seen or ()))

    def run(call):
        return cap_output(execute(repo, commit, call, settings=settings, context=context),
                          settings.max_tool_output_tokens, count_tokens)
    return ToolCache(run).get


@dataclass
class AgentRun:
    answer: str
    messages: list[dict]
    rounds: list[dict] = field(default_factory=list)
    commits: list = field(default_factory=list)
    chunks: list = field(default_factory=list)  # code shown by tools (VI.4)
    generator_calls: int = 0
    answer_round: int = 0
    round_limit_hit: bool = False


def _run_safely(run_tool, call) -> tuple[ToolOutput, bool]:
    try:
        return run_tool(call)
    except Exception as exc:  # noqa: BLE001 (a tool failure must not end the query)
        return ToolOutput(text=f"error: {call.tool} failed: {exc}", error=True), False


class _DraftFilter:
    """Forward the model's text to *emit*, but nothing from a ``<tool>`` tag onwards.

    A few characters that could be the start of a tag are held back until the next
    piece shows whether they are (Spec 004 AC-2.3).
    """

    TAG = "<tool>"

    def __init__(self, emit) -> None:
        self._emit, self._held, self._stopped = emit, "", False

    def feed(self, piece: str) -> None:
        if self._stopped:
            return
        text = self._held + piece
        at = text.find(self.TAG)
        if at >= 0:
            self._stopped, self._held = True, ""
            if at:
                self._emit(text[:at])
            return
        keep = next((n for n in range(min(len(self.TAG) - 1, len(text)), 0, -1)
                     if self.TAG.startswith(text[-n:])), 0)
        self._held = text[len(text) - keep:]
        if len(text) > keep:
            self._emit(text[:len(text) - keep])

    def finish(self) -> None:
        """The reply ended: a held tail that never became a tag is ordinary text."""
        if self._held and not self._stopped:
            self._emit(self._held)
        self._held = ""


def _generate(generator, messages: list[dict], on_draft) -> str:
    if on_draft is None:
        return generator.generate(messages)
    shown = _DraftFilter(on_draft)
    text = generator.generate(messages, on_text=shown.feed)
    shown.finish()
    return text


def run_agent(generator, question: str, chunks: list, *, run_tool, max_rounds: int,
              tools_enabled: bool = True, on_draft=None, on_tool=None) -> AgentRun:
    """Answer, running at most *max_rounds* tool calls, one per round (Plan D15).

    *on_draft*, if given, receives the model's text as it is written (Spec 004 US2).
    *on_tool*, if given, is called with a deep copy of the audit record of each tool call
    that ran, in order (Spec 004 US6); it only observes.
    """
    messages = [{"role": "system", "content": system_prompt(tools_enabled=tools_enabled)},
                {"role": "user", "content": user_message(question, chunks)}]
    run = AgentRun(answer="", messages=messages)
    tool_runs = 0
    while True:
        response = _generate(generator, messages, on_draft)
        run.generator_calls += 1
        calls = parse_tool_calls(response)
        bad = malformed_blocks(response) if tools_enabled and not calls else []
        if calls and not tools_enabled:  # rag / no_retrieval modes (D17)
            run.rounds.append({"round": tool_runs, "ignored_calls": len(calls),
                               "reason": "tools disabled"})
            calls = []
        if not calls and not bad:
            run.answer, run.answer_round = strip_tool_blocks(response), tool_runs
            return run
        messages.append({"role": "assistant", "content": response})
        if tool_runs >= max_rounds:
            messages.append({"role": "user", "content": FINAL_MESSAGE})
            final = _generate(generator, messages, on_draft)
            run.generator_calls += 1
            run.rounds.append({"round": tool_runs, "final_call": True,
                               "ignored_calls": len(calls) or len(bad)})
            run.answer, run.answer_round = strip_tool_blocks(final), tool_runs
            run.round_limit_hit = True
            return run
        if bad:  # a malformed call uses a round, so the loop stays bounded (T8.6)
            run.rounds.append({"round": tool_runs, "tool": None, "args": {},
                               "malformed": True, "cache_hit": False, "error": True,
                               "result_summary": "malformed tool call"})
            messages.append({"role": "user", "content": malformed_result_message(bad[0])})
            tool_runs += 1
            continue
        call = calls[0]
        output, hit = _run_safely(run_tool, call)
        entry = {"round": tool_runs, "tool": call.tool, "args": dict(call.args),
                 "cache_hit": hit, "error": output.error,
                 "result_summary": output.text.splitlines()[0] if output.text else ""}
        if len(calls) > 1:
            entry["ignored_calls"] = len(calls) - 1
        run.rounds.append(entry)
        if on_tool is not None:
            on_tool(copy.deepcopy(entry))
        run.commits.extend(output.commits)
        run.chunks.extend(output.chunks)
        messages.append({"role": "user", "content": tool_result_message(call, output)})
        tool_runs += 1
