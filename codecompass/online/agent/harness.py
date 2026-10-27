"""Bounded agent loop: generate, run allow-listed tools, answer (Article V)."""

from __future__ import annotations

from dataclasses import dataclass, field

from codecompass.online.agent.cache import ToolCache
from codecompass.online.agent.tool_parser import parse_tool_calls, strip_tool_blocks
from codecompass.online.agent.tools import ToolOutput, cap_output, execute
from codecompass.online.context import format_context

_INTRO = """You are CodeCompass, a code Q&A assistant. Answer the developer's question
using ONLY the code context provided below. Do not use your training knowledge
about the repository."""

_RULES = [
    "Cite every claim with numbered markers [1], [2], etc.",
    """End with a Sources section listing each citation. For code, copy the
   chunk's header line exactly (the part before " | ").
   - Code: [N] file/path.py, lines X-Y (indexed at <7-char hash>)
   - Commit: [N] Commit <7-char hash>, "<subject>", <author>, <date>""",
    """If the evidence is insufficient, say what you could not determine.
   Do NOT guess or make up file names, line numbers, or commit hashes.""",
    """If the commit history gives no reason for the code (e.g. vague commit
   messages, or no history found), say so. Do NOT invent a reason.""",
]
_TOOL_RULE = """If you need commit history to explain WHY code exists, request a tool:
   <tool>git_blame(path="file/path.py", lines="X-Y")</tool>
   <tool>git_log(path="file/path.py", n=10)</tool>
   The result comes back in a <tool_result>...</tool_result> block. It is
   evidence you may cite, just like the code context."""

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


def make_tool_runner(repo, commit: str, settings, count_tokens):
    """execute() at the indexed commit, capped (D4) and cached per query (D8)."""
    def run(call):
        return cap_output(execute(repo, commit, call, settings=settings),
                          settings.max_tool_output_tokens, count_tokens)
    return ToolCache(run).get


@dataclass
class AgentRun:
    answer: str
    messages: list[dict]
    rounds: list[dict] = field(default_factory=list)
    commits: list = field(default_factory=list)
    generator_calls: int = 0
    answer_round: int = 0
    round_limit_hit: bool = False


def _run_safely(run_tool, call) -> tuple[ToolOutput, bool]:
    try:
        return run_tool(call)
    except Exception as exc:  # noqa: BLE001 (a tool failure must not end the query)
        return ToolOutput(text=f"error: {call.tool} failed: {exc}", error=True), False


def run_agent(generator, question: str, chunks: list, *, run_tool, max_rounds: int,
              tools_enabled: bool = True) -> AgentRun:
    """Answer, running at most *max_rounds* tool calls, one per round (Plan D15)."""
    messages = [{"role": "system", "content": system_prompt(tools_enabled=tools_enabled)},
                {"role": "user", "content": user_message(question, chunks)}]
    run = AgentRun(answer="", messages=messages)
    tool_runs = 0
    while True:
        response = generator.generate(messages)
        run.generator_calls += 1
        calls = parse_tool_calls(response)
        if calls and not tools_enabled:  # rag / no_retrieval modes (D17)
            run.rounds.append({"round": tool_runs, "ignored_calls": len(calls),
                               "reason": "tools disabled"})
            calls = []
        if not calls:
            run.answer, run.answer_round = strip_tool_blocks(response), tool_runs
            return run
        messages.append({"role": "assistant", "content": response})
        if tool_runs >= max_rounds:
            messages.append({"role": "user", "content": FINAL_MESSAGE})
            final = generator.generate(messages)
            run.generator_calls += 1
            run.rounds.append({"round": tool_runs, "final_call": True,
                               "ignored_calls": len(calls)})
            run.answer, run.answer_round = strip_tool_blocks(final), tool_runs
            run.round_limit_hit = True
            return run
        call = calls[0]
        output, hit = _run_safely(run_tool, call)
        entry = {"round": tool_runs, "tool": call.tool, "args": dict(call.args),
                 "cache_hit": hit, "error": output.error,
                 "result_summary": output.text.splitlines()[0] if output.text else ""}
        if len(calls) > 1:
            entry["ignored_calls"] = len(calls) - 1
        run.rounds.append(entry)
        run.commits.extend(output.commits)
        messages.append({"role": "user", "content": tool_result_message(call, output)})
        tool_runs += 1
