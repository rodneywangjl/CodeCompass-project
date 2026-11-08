"""CodeCompass online query pipeline (Spec 002).

Public API: ask(). One call runs the whole pipeline (Plan §1): ensure the
index is current, retrieve and re-rank, run the bounded agent loop, check
every citation, and return the rendered answer with its audit log.
"""

from __future__ import annotations

import contextlib
import dataclasses
import posixpath
import re
import time
from pathlib import Path

from codecompass.offline import ensure_current, open_index, status
from codecompass.online.agent.harness import (
    make_tool_runner, run_agent, system_prompt, user_message)
from codecompass.online.citation import checker, formatter
from codecompass.online.config import OnlineConfig, check_mode
from codecompass.online.context import (
    RetrievedChunk, check_round_reserve, chunk_budget, fit_chunks)
from codecompass.online.generator.profiles import resolve_profile
from codecompass.online.logging import TimedGenerator, new_log, timed, write_log
from codecompass.online.models import QueryResult
from codecompass.online.retrieval.hybrid import retrieve
from codecompass.online.retrieval.reranker import rerank_chunks

__version__ = "0.1.0"
__all__ = ["ask", "warm_up", "asks_about_docs"]

STALE_WARNING = ("⚠ WARNING: The index may be out of date. The answer below is based "
                 "on an older version of the codebase.")
NO_EVIDENCE = "I could not find enough evidence in the indexed code to answer this question."
CLOSEST_HEADER = ("Closest matches found (these are not evidence for an answer; "
                  "check them yourself):")
EMPTY_QUESTION = ("The question has no words in it. Each question is answered on its own, so "
                  "type a full question, for example \"Explain what require_role does "
                  "in simpler words\".")
NO_INDEX = ("No index is available for this repository yet, so this question cannot "
            "be answered.")
DOC_WORDS = frozenset({"readme", "docs", "doc", "documentation", "documented",
                       "changelog", "guide", "tutorial"})
DOC_SUBSTRINGS = (".md", ".rst")
_DOC_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(DOC_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def asks_about_docs(question: str) -> bool:
    """Case-insensitive whole-word and extension check for doc queries (T22.1)."""
    lower = question.lower()
    if any(sub in lower for sub in DOC_SUBSTRINGS):
        return True
    return bool(_DOC_WORD_RE.search(lower))


def _default_generator(config: OnlineConfig, profile):
    from codecompass.online.generator.llama import LlamaServerGenerator
    generator = LlamaServerGenerator(profile, server_url=config.generator.server_url,
                                     timeout_seconds=config.generator.timeout_seconds)
    generator.connect_timeout = config.generator.connect_timeout_seconds  # T19.3
    return generator


_RERANKERS: dict = {}
_RERANKERS_MAX = 4


def _default_reranker(config: OnlineConfig):
    """One re-ranker per configuration per process (plan 002 O1).

    Keyed by the class as looked up now, like the shared embedder.
    """
    from codecompass.online.retrieval.reranker import BgeReranker
    key = (BgeReranker, config.reranker)
    if key not in _RERANKERS:
        if len(_RERANKERS) >= _RERANKERS_MAX:
            _RERANKERS.pop(next(iter(_RERANKERS)))
        _RERANKERS[key] = BgeReranker(config.reranker)
    return _RERANKERS[key]


def _log_dir(config: OnlineConfig, index_dir) -> Path:
    if config.logging.query_log_dir:
        return Path(config.logging.query_log_dir)
    return Path(index_dir or config.offline.index.dir) / "queries"


def _log_retrieved(log, ranked, rrf, sent_ids) -> None:
    log["retrieved"] = [{"chunk_id": c.chunk_id, "path": c.path,
                         "lines": f"{c.start_line}-{c.end_line}",
                         "rrf_score": rrf[c.chunk_id], "rerank_score": score,
                         "sent": c.chunk_id in sent_ids} for c, score in ranked]


def _refusal(ranked, closest_files: int) -> str:
    """NO_EVIDENCE plus the closest files, best first, each once (AC-1.7, Plan D19).

    Plain text, not citations: no Sources section and no [N] markers.
    """
    lines, listed = [], set()
    for chunk, _ in ranked:
        if len(lines) >= closest_files:
            break
        if chunk.path not in listed:
            listed.add(chunk.path)
            lines.append(f"- {chunk.path}, lines {chunk.start_line}-{chunk.end_line}")
    if not lines:
        return NO_EVIDENCE
    return f"{NO_EVIDENCE}\n\n{CLOSEST_HEADER}\n" + "\n".join(lines)


def _retrieve_and_answer(handles, repo_path, question, *, config, profile, tools, tools_on,
                         generator, reranker, log, on_draft=None, on_tool=None):
    """Hybrid retrieval, re-rank, budget, then the agent loop (Plan §1)."""
    if handles.vector.count() == 0:
        return NO_EVIDENCE, [], []
    with timed(log, "retrieval"):
        shortlist = retrieve(handles, question, config=config.retrieval)
        records = handles.vector.records_for_ids([cid for cid, _ in shortlist])
        chunks = [RetrievedChunk.from_record(cid, records[cid])
                  for cid, _ in shortlist if cid in records]
    reranker = reranker or _default_reranker(config)
    with timed(log, "reranking"):
        ranked = rerank_chunks(reranker, question, chunks, len(chunks))
    rrf = dict(shortlist)

    if not config.retrieval.docs_fallback:
        if ranked:  # the evidence gate (AC-1.5, Plan D19): poor matches are not evidence
            top, minimum = max(score for _, score in ranked), config.retrieval.min_top_score
            log["evidence_gate"] = {"min_top_score": minimum, "top_score": top,
                                    "passed": top >= minimum}
            if top < minimum:
                _log_retrieved(log, ranked, rrf, set())
                return _refusal(ranked, config.retrieval.closest_files), [], []
        chosen = [c for c, _ in ranked[:config.retrieval.final_k]]
        docs_flag = False
        doc_langs = ()
    else:
        # Docs as context (T22.1): code is the source of truth, docs add context when needed
        doc_langs = set(config.retrieval.doc_languages)
        code_ranked = [(c, s) for c, s in ranked if c.language not in doc_langs]
        doc_ranked = [(c, s) for c, s in ranked if c.language in doc_langs]
        best_code = max((s for _, s in code_ranked), default=None)
        best_doc = max((s for _, s in doc_ranked), default=None)
        minimum = config.retrieval.min_top_score
        code_passed = best_code is not None and best_code >= minimum
        doc_passed = best_doc is not None and best_doc >= minimum

        log["evidence_gate"] = {"min_top_score": minimum, "top_score": best_code,
                                "passed": code_passed}

        reason: str | None = None
        if code_passed:
            margin = config.retrieval.docs_margin
            if doc_passed and asks_about_docs(question):
                reason = "asked"
                chosen_ranked = ranked
            elif best_doc is not None and best_doc >= best_code + margin:
                reason = "better"
                chosen_ranked = ranked
            else:
                reason = None
                chosen_ranked = code_ranked
        else:
            if doc_passed:
                reason = "code_failed"
                chosen_ranked = doc_ranked
            else:
                _log_retrieved(log, ranked, rrf, set())
                log["docs_fallback"] = {"used": False, "reason": None,
                                        "best_code": best_code, "best_doc": best_doc}
                return _refusal(ranked, config.retrieval.closest_files), [], []

        chosen = [c for c, _ in chosen_ranked[:config.retrieval.final_k]]
        docs_flag = any(c.language in doc_langs for c in chosen)

    hint = config.prompt.vague_question_hint
    prefix = (generator.count_tokens(system_prompt(tools_enabled=tools_on,
                                                   vague_question_hint=hint))
              + generator.count_tokens(user_message(question, [], tools_enabled=tools_on,
                                                    docs=docs_flag)))
    sent = fit_chunks(chosen, chunk_budget(profile, tools, prefix), generator.count_tokens)
    _log_retrieved(log, ranked, rrf, {c.chunk_id for c in sent})
    if config.retrieval.docs_fallback:
        used = any(c.language in doc_langs for c in sent)
        log["docs_fallback"] = {"used": used, "reason": reason if used else None,
                                "best_code": best_code, "best_doc": best_doc}
    else:
        used = False
    if not sent:
        return NO_EVIDENCE, [], []
    # tools run at the indexed commit, the version the chunks came from (Plan D7)
    runner = make_tool_runner(repo_path, handles.meta.indexed_commit, config.tools,
                              generator.count_tokens, handles=handles, reranker=reranker,
                              retrieval=config.retrieval,
                              seen={c.chunk_id for c in sent},
                              # the indexer's ignore list also binds open_file (III.6)
                              exclude_patterns=config.offline.files.exclude_patterns,
                              exclude_dirs=config.offline.files.exclude_dirs)
    return _agent(generator, question, sent, runner=runner, tools=tools,
                  tools_on=tools_on, log=log, docs=used, on_draft=on_draft, on_tool=on_tool,
                  vague_question_hint=config.prompt.vague_question_hint)


def _agent(generator, question, chunks, *, runner, tools, tools_on, log, docs: bool = False,
           on_draft=None,
           on_tool=None, vague_question_hint: bool = False):
    def run_tool(call):
        with timed(log, "tool_execution"):
            return runner(call)

    run = run_agent(generator, question, chunks, run_tool=run_tool,
                    max_rounds=tools.max_verifier_rounds, tools_enabled=tools_on, docs=docs,
                    on_draft=on_draft, on_tool=on_tool,
                    vague_question_hint=vague_question_hint)
    log.update(tool_calls=run.rounds, generator_calls=run.generator_calls,
               round_limit_hit=run.round_limit_hit)
    # the checker sees retrieved chunks plus code shown by tools (VI.1, VI.4)
    return run.answer, chunks + run.chunks, run.commits


def ask(repo_path, question: str, *, config: OnlineConfig, profile: str | None = None,
        index_dir=None, generator=None, reranker=None, embedder=None,
        on_draft=None, on_tool=None) -> QueryResult:
    """Answer *question* about the repository at *repo_path* (Spec US1, US9).

    generator, reranker and embedder default to the configured models; tests
    pass stubs. Nothing is printed; everything is in the returned result.
    *on_draft*, if given, receives the model's text as it is written; it is an
    unchecked draft, and only the returned answer has been through the citation check.
    *on_tool*, if given, receives a copy of the audit record of each tool call as it
    finishes; it only observes, and with None nothing changes (Spec 004 US6).
    A question with no letter or digit raises ValueError before any work is done.
    """
    if not any(ch.isalnum() for ch in question):  # "", "   ", "?", "..." (report problem 11)
        raise ValueError(EMPTY_QUESTION)
    started = time.perf_counter()
    mode = check_mode(config.pipeline.mode)
    profile_name, model = resolve_profile(config, profile)
    tools_on = mode == "rag_tools"
    tools = (config.tools if tools_on
             else dataclasses.replace(config.tools, max_verifier_rounds=0))
    log = new_log(question, profile_name=profile_name, profile=model, mode=mode,
                  tools=config.tools)
    log["reranker"] = dataclasses.asdict(config.reranker)  # model, revision, device, dtype
    log["prompt"] = dataclasses.asdict(config.prompt)  # the [prompt] flags (T19.5)
    hint = config.prompt.vague_question_hint
    gen = TimedGenerator(generator or _default_generator(config, model), log)
    try:
        # the first call to llama-server (/tokenize), so inside the try (T18.2)
        check_round_reserve(model, tools,
                            gen.count_tokens(system_prompt(tools_enabled=tools_on,
                                                           vague_question_hint=hint)))
        with timed(log, "ensure_current"):
            ensured = ensure_current(repo_path, config=config.offline, index_dir=index_dir,
                                     embedder=embedder)
        stale = not ensured.ok
        reason = (ensured.message or ensured.status) if stale else ""
        log["index"] = {"ensure_status": ensured.status, "stale": stale, "stale_message": reason}

        if stale and status(repo_path, config=config.offline,
                            index_dir=index_dir).state == "empty":
            answer, chunks, commits = f"{NO_INDEX} Indexing failed: {reason}", [], []
            stale = log["index"]["stale"] = False  # nothing was answered from an old index
        elif mode == "no_retrieval":
            answer, chunks, commits = _agent(gen, question, [], runner=None, tools=tools,
                                             tools_on=False, log=log, on_draft=on_draft,
                                             vague_question_hint=hint)
        else:
            handles = open_index(repo_path, config=config.offline, index_dir=index_dir,
                                 embedder=embedder)
            try:
                answer, chunks, commits = _retrieve_and_answer(
                    handles, repo_path, question, config=config, profile=model, tools=tools,
                    tools_on=tools_on, generator=gen, reranker=reranker, log=log,
                    on_draft=on_draft, on_tool=on_tool)
            finally:
                handles.close()

        with timed(log, "citation_check"):
            result = checker.check(answer, chunks, commits)
        rendered = formatter.render(result)
        if config.retrieval.docs_fallback:
            doc_paths = {c.path for c in chunks
                         if c.language in config.retrieval.doc_languages
                         or posixpath.splitext(c.path)[1].lstrip(".").lower()
                            in config.retrieval.doc_languages}
            rendered, doc_sources = formatter.mark_documentation(rendered, result, doc_paths)
        else:
            doc_sources = []
        if stale:
            rendered = f"{STALE_WARNING}\nReason: {reason}\n\n{rendered}"
        log["citation"] = {"outcome": result.outcome, "unverified": list(result.unverified)}
        # only when there are some: the record of an ordinary answer is pinned
        if result.unreferenced:
            log["citation"]["unreferenced"] = list(result.unreferenced)
        if doc_sources:
            log["citation"]["documentation_sources"] = doc_sources
    except BaseException as exc:  # also Ctrl-C: a failed question is still audited (T18.1)
        log["error"] = {"type": type(exc).__name__, "message": str(exc)}
        log["timings"]["total"] = time.perf_counter() - started
        with contextlib.suppress(Exception):  # the original error matters more
            write_log(log, _log_dir(config, index_dir))
        raise
    log["timings"]["total"] = time.perf_counter() - started
    path = write_log(log, _log_dir(config, index_dir))
    return QueryResult(answer=rendered, sources=list(result.sources),
                       citation_outcome=result.outcome, stale_index=stale,
                       stale_message=reason, audit_log={**log, "log_file": str(path)})


def warm_up(repo_path, *, config: OnlineConfig, index_dir=None, embedder=None,
            reranker=None) -> None:
    """Bring the index current and load the models, so the first question does not wait.

    Prints nothing and changes no pipeline behaviour: it makes the calls the first
    ask() would make, ahead of time, on the shared models (Spec 004 US3). Errors are
    raised for the caller to ignore or report; ask() raises them again on its own.
    """
    ensured = ensure_current(repo_path, config=config.offline, index_dir=index_dir,
                             embedder=embedder)
    if not ensured.ok:
        raise RuntimeError(ensured.message or ensured.status)
    handles = open_index(repo_path, config=config.offline, index_dir=index_dir,
                         embedder=embedder)
    try:
        if handles.vector.count() > 0:
            handles.embed_query("warm up")  # loads the embedder
    finally:
        handles.close()
    (reranker or _default_reranker(config)).rerank("warm up", ["warm up"])
