"""T5.5 LLM runner tests (tests-first).

Contract under test (Spec AC-5.2, AC-5.3, AC-5.5, AC-6.1-6.4; Plan 003 §3.5):
  - codecompass.eval.llm_run.run_llm(question_files, repo_path, *, config_path, mode,
        subset_path, profile="dev", index_dir=None, generator=None, reranker=None,
        embedder=None, reported=False, project_dir=None, out_dir=Path("eval/results"),
        resume=None) -> Path
    loads the config from config_path itself (what is recorded is what ran), sets
    pipeline.mode from `mode`, and calls the module's `ask` once per question with a fresh
    RecordingGenerator around the same inner generator, and the same reranker and embedder
  - checks before any question: question files pass check_question_set; repo HEAD and
    the index commit equal every question's repo_commit; with reported=True a clean
    git checkout (project_dir). Any failure raises ValueError and writes no file.
  - one results file <out>/llm-<mode>-<UTC time>.json, rewritten after every question:
    {"meta": run_meta(...) + run fields, "questions": [...]}
  - a failing ask() is retried once, then recorded with its error; the run continues
  - resume=FILE continues that file and skips ids with a result or a final error
  - main(argv) -> int: FILE... --repo --config --mode [--subset] [--index-dir] [--profile]
    [--reported] [--out] [--resume]; prints the results path (0) or "error: ..." (1)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import codecompass.offline as offline
from codecompass.eval import llm_run
from codecompass.eval.recording import RecordingGenerator
from codecompass.online.config import load_online_config
from tests.online.ask_support import CitingGenerator
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import TOOL_CALL_LOG, StubGenerator
from tests.support.stub_reranker import StubReranker

QUESTION_FIELDS = {
    "id", "set", "category", "complexity", "in_subset", "mode", "answer", "raw_text",
    "citation_outcome", "sources", "unverified", "unreferenced", "retrieved",
    "tool_calls", "round_limit_hit", "timings", "log_file", "messages", "error", "attempts",
}
RUN_FIELDS = {"mode", "docs_fallback", "label", "question_files", "subset",
              "started_at", "ended_at"}
RUN_META_GROUPS = {"codecompass", "repo", "index", "config", "embedder", "reranker",
                   "generator", "server", "host"}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def _row(commit, qid, *, category="architectural", question="Why does authenticate retry?"):
    gt = [] if category == "unanswerable" else [{"path": "src/auth.py", "start_line": 1,
                                                 "end_line": 2}]
    return {
        "id": qid, "set": "core", "category": category, "complexity": "simple",
        "question": question, "reference_answer": "In src/auth.py.",
        "reference_citations": [{"path": g["path"], "lines": "1-2"} for g in gt],
        "ground_truth_files": gt, "source": "hand-written", "ai_assisted": False,
        "repo_commit": commit, "original_id": None,
    }


def _write_jsonl(path: Path, rows) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def s(tmp_path):
    """History repo indexed with the stub embedder, 3 questions, a subset file, a config."""
    repo = build_history_repo(tmp_path / "repo").path
    commit = _git(repo, "rev-parse", "HEAD")
    cfg_path = tmp_path / "eval.toml"
    cfg_path.write_text(
        '[embedder]\nmodel = "stub"\nrevision = "stub-1"\ndimension = 8\n\n'
        "[retrieval]\nmin_top_score = 0\n\n"
        f'[logging]\nquery_log_dir = "{(tmp_path / "queries").as_posix()}"\n')
    idx = tmp_path / "idx"
    embedder = StubEmbedder()
    offline.ensure_current(repo, config=load_online_config(cfg_path).offline, index_dir=idx,
                           embedder=embedder)
    qfile = _write_jsonl(tmp_path / "q.jsonl", [
        _row(commit, "core-architectural-01"),
        _row(commit, "core-architectural-02", question="What does authenticate return?"),
        _row(commit, "core-unanswerable-01", category="unanswerable",
             question="Which OAuth providers does auth support?"),
    ])
    subset = tmp_path / "subset.json"
    subset.write_text(json.dumps({"rule": "test", "question_files": [],
                                  "ids": ["core-architectural-02"]}))
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q")
    (project / "README.md").write_text("p\n")
    _git(project, "add", "-A")
    _git(project, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    return {"repo": repo, "commit": commit, "cfg": cfg_path, "idx": idx, "q": qfile,
            "subset": subset, "project": project, "out": tmp_path / "results",
            "embedder": embedder, "reranker": StubReranker(), "tmp": tmp_path}


def _run(s, mode="rag_tools", generator=None, **kw):
    kw.setdefault("project_dir", s["project"])
    return llm_run.run_llm(
        [s["q"]], s["repo"], config_path=s["cfg"], mode=mode, subset_path=s["subset"],
        index_dir=s["idx"], generator=generator or CitingGenerator(),
        reranker=s["reranker"], embedder=s["embedder"], out_dir=s["out"], **kw)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class _Spy:
    """Wraps the real ask(); records the keyword arguments of every call."""

    def __init__(self, real, fail=None):
        self.real, self.fail, self.calls = real, fail or {}, []

    def __call__(self, repo, question, **kw):
        self.calls.append({"question": question, **kw})
        remaining = self.fail.get(question, 0)
        if remaining:
            self.fail[question] = remaining - 1
            raise TimeoutError("llama-server went silent")
        return self.real(repo, question, **kw)


# -- results file (AC-6.1, AC-6.3) ----------------------------------------------------


def test_writes_one_results_file_with_every_question_field(s):
    path = _run(s)
    assert path.parent == s["out"]
    assert path.name.startswith("llm-rag_tools-") and path.suffix == ".json"
    data = _load(path)
    assert [q["id"] for q in data["questions"]] == [
        "core-architectural-01", "core-architectural-02", "core-unanswerable-01"]
    for q in data["questions"]:
        assert set(q) == QUESTION_FIELDS, q["id"]
        assert q["error"] is None and q["attempts"] == 1


def test_answers_outcomes_and_context_are_recorded(s):
    q = _load(_run(s))["questions"][0]
    assert q["answer"].startswith("Login retries on timeout [1].")
    assert q["raw_text"].startswith("Login retries on timeout [1].")
    assert q["citation_outcome"] == "F"
    assert [src["verified"] for src in q["sources"]] == [True]
    assert q["unverified"] == [] and q["unreferenced"] == []
    assert q["retrieved"] and q["messages"]
    assert q["messages"][-1]["output"] == q["raw_text"]
    assert Path(q["log_file"]).is_file()
    assert q["timings"]["generation"] >= 0


def test_in_subset_comes_from_the_subset_file(s):
    flags = {q["id"]: q["in_subset"] for q in _load(_run(s))["questions"]}
    assert flags == {"core-architectural-01": False, "core-architectural-02": True,
                     "core-unanswerable-01": False}


# -- run details (AC-5.3, AC-6.2, AC-6.4) ---------------------------------------------


def test_meta_has_run_meta_and_the_run_fields(s):
    meta = _load(_run(s))["meta"]
    assert RUN_META_GROUPS | RUN_FIELDS <= set(meta)
    assert meta["mode"] == "rag_tools"
    assert meta["label"] == "dev"
    assert meta["docs_fallback"] is False
    assert meta["generator"]["profile"] == "dev"
    assert meta["repo"]["head_commit"] == s["commit"]
    assert meta["index"]["indexed_commit"] == s["commit"]
    assert meta["config"]["path"] == str(s["cfg"])
    assert meta["codecompass"]["dirty"] is False
    assert [f["path"] for f in meta["question_files"]] == [str(s["q"])]
    assert len(meta["question_files"][0]["sha256"]) == 64
    assert meta["subset"]["path"] == str(s["subset"]) and len(meta["subset"]["sha256"]) == 64


# -- the three configurations (AC-5.2) ------------------------------------------------


# Approved test change (2026-11-08): CitingGenerator copies a retrieved chunk's header, so
# it cannot answer in no_retrieval; these use a stub that needs no chunks. In rag, an
# ignored tool request is logged, never executed.
@pytest.mark.parametrize("mode", ["no_retrieval", "rag", "rag_tools"])
def test_mode_is_set_on_every_question(s, mode):
    data = _load(_run(s, mode=mode, generator=StubGenerator(["An answer from the model."])))
    assert data["meta"]["mode"] == mode
    assert {q["mode"] for q in data["questions"]} == {mode}
    assert all(q["error"] is None for q in data["questions"])


def test_no_retrieval_sends_no_chunks(s):
    data = _load(_run(s, mode="no_retrieval",
                      generator=StubGenerator(["An answer from the model."])))
    for q in data["questions"]:
        assert q["error"] is None
        assert q["retrieved"] == []


def test_tools_run_in_rag_tools_only(s):
    with_tools = _load(_run(s, mode="rag_tools",
                            generator=CitingGenerator(before=[TOOL_CALL_LOG])))
    assert len(with_tools["questions"][0]["tool_calls"]) == 1
    without = _load(_run(s, mode="rag", generator=CitingGenerator(before=[TOOL_CALL_LOG])))
    for q in without["questions"]:
        assert not [c for c in q["tool_calls"] if c.get("tool")]
    assert without["questions"][0]["tool_calls"] == [
        {"round": 0, "ignored_calls": 1, "reason": "tools disabled"}]


# -- models loaded once (plan §3.5) ---------------------------------------------------


def test_same_models_are_passed_to_every_ask_with_a_fresh_recorder(s, monkeypatch):
    spy = _Spy(llm_run.ask)
    monkeypatch.setattr(llm_run, "ask", spy)
    inner = CitingGenerator()
    _run(s, generator=inner)
    assert len(spy.calls) == 3
    assert all(c["reranker"] is s["reranker"] for c in spy.calls)
    assert all(c["embedder"] is s["embedder"] for c in spy.calls)
    gens = [c["generator"] for c in spy.calls]
    assert all(isinstance(g, RecordingGenerator) and g.inner is inner for g in gens)
    assert len({id(g) for g in gens}) == 3
    assert all(c["config"].pipeline.mode == "rag_tools" for c in spy.calls)
    assert all(c["profile"] == "dev" for c in spy.calls)


# -- retries and the rewrite after each question (AC-5.5) ----------------------------


def test_a_failing_question_is_retried_once_then_recorded_and_the_run_continues(s, monkeypatch):
    spy = _Spy(llm_run.ask, fail={"Why does authenticate retry?": 2,
                                  "What does authenticate return?": 1})
    monkeypatch.setattr(llm_run, "ask", spy)
    qs = {q["id"]: q for q in _load(_run(s))["questions"]}
    failed = qs["core-architectural-01"]
    assert failed["attempts"] == 2
    assert failed["error"] == {"type": "TimeoutError", "message": "llama-server went silent"}
    assert failed["answer"] is None
    recovered = qs["core-architectural-02"]
    assert recovered["attempts"] == 2 and recovered["error"] is None
    assert recovered["citation_outcome"] == "F"
    assert qs["core-unanswerable-01"]["attempts"] == 1
    assert len(spy.calls) == 5


def test_the_file_is_rewritten_after_each_question(s, monkeypatch):
    seen = []

    def watching(repo, question, **kw):
        files = sorted(s["out"].glob("llm-*.json"))
        seen.append(len(_load(files[0])["questions"]) if files else 0)
        return real(repo, question, **kw)

    real = llm_run.ask
    monkeypatch.setattr(llm_run, "ask", watching)
    _run(s)
    assert seen == [0, 1, 2]


# -- resume (AC-5.5) ------------------------------------------------------------------


def test_resume_skips_ids_with_a_result_or_a_final_error(s, monkeypatch):
    path = _run(s)
    data = _load(path)
    data["questions"] = data["questions"][:2]
    data["questions"][1]["answer"], data["questions"][1]["error"] = None, {
        "type": "TimeoutError", "message": "x"}
    path.write_text(json.dumps(data), encoding="utf-8")
    spy = _Spy(llm_run.ask)
    monkeypatch.setattr(llm_run, "ask", spy)
    again = _run(s, resume=path)
    assert again == path
    assert [c["question"] for c in spy.calls] == ["Which OAuth providers does auth support?"]
    assert [q["id"] for q in _load(path)["questions"]] == [
        "core-architectural-01", "core-architectural-02", "core-unanswerable-01"]


def test_resume_refuses_a_file_from_another_mode(s):
    path = _run(s, mode="rag")
    with pytest.raises(ValueError, match="rag"):
        _run(s, mode="rag_tools", resume=path)


# -- checks before any question (AC-1.2, AC-6.4) --------------------------------------


def _no_ask(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("ask() must not be called")
    monkeypatch.setattr(llm_run, "ask", forbidden)


def test_repo_head_different_from_repo_commit_stops_before_any_question(s, monkeypatch):
    (s["repo"] / "NEW.txt").write_text("x\n")
    _git(s["repo"], "add", "-A")
    _git(s["repo"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "n")
    _no_ask(monkeypatch)
    with pytest.raises(ValueError, match="HEAD"):
        _run(s)
    assert not s["out"].exists() or not list(s["out"].iterdir())


def test_index_commit_different_from_repo_commit_stops_before_any_question(s, monkeypatch):
    (s["repo"] / "NEW.txt").write_text("x\n")
    _git(s["repo"], "add", "-A")
    _git(s["repo"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "n")
    head = _git(s["repo"], "rev-parse", "HEAD")
    _write_jsonl(s["q"], [_row(head, "core-architectural-01")])
    _no_ask(monkeypatch)
    with pytest.raises(ValueError, match="index"):
        _run(s)


def test_a_question_set_with_problems_stops_before_any_question(s, monkeypatch):
    bad = _row(s["commit"], "core-architectural-01")
    bad["ground_truth_files"] = [{"path": "src/missing.py", "start_line": 1, "end_line": 2}]
    _write_jsonl(s["q"], [bad])
    _no_ask(monkeypatch)
    with pytest.raises(ValueError, match="src/missing.py"):
        _run(s)


def test_a_missing_config_file_stops_the_run(s, monkeypatch):
    _no_ask(monkeypatch)
    with pytest.raises((ValueError, FileNotFoundError)):
        llm_run.run_llm([s["q"]], s["repo"], config_path=s["tmp"] / "nope.toml",
                        mode="rag", subset_path=s["subset"], index_dir=s["idx"],
                        generator=CitingGenerator(), reranker=s["reranker"],
                        embedder=s["embedder"], out_dir=s["out"], project_dir=s["project"])


def test_reported_refuses_a_dirty_tree(s, monkeypatch):
    (s["project"] / "README.md").write_text("changed\n")
    _no_ask(monkeypatch)
    with pytest.raises(ValueError, match="uncommitted"):
        _run(s, reported=True)


def test_reported_on_a_clean_tree_is_labelled_reported(s):
    assert _load(_run(s, reported=True))["meta"]["label"] == "reported"


def test_an_unknown_mode_is_refused(s, monkeypatch):
    _no_ask(monkeypatch)
    with pytest.raises(ValueError):
        _run(s, mode="rag_plus")


# -- command line ---------------------------------------------------------------------


def test_main_passes_its_arguments_and_prints_the_path(s, monkeypatch, capsys):
    got = {}

    def fake(question_files, repo_path, **kw):
        got.update(question_files=question_files, repo_path=repo_path, **kw)
        return s["out"] / "llm-rag-x.json"

    monkeypatch.setattr(llm_run, "run_llm", fake)
    code = llm_run.main([str(s["q"]), "--repo", str(s["repo"]), "--config", str(s["cfg"]),
                         "--mode", "rag", "--subset", str(s["subset"]), "--index-dir",
                         str(s["idx"]), "--profile", "dev", "--reported", "--out",
                         str(s["out"])])
    assert code == 0
    assert capsys.readouterr().out.strip() == str(s["out"] / "llm-rag-x.json")
    assert [Path(p) for p in got["question_files"]] == [s["q"]]
    assert Path(got["repo_path"]) == s["repo"] and Path(got["config_path"]) == s["cfg"]
    assert got["mode"] == "rag" and got["profile"] == "dev" and got["reported"] is True
    assert Path(got["subset_path"]) == s["subset"] and Path(got["index_dir"]) == s["idx"]
    assert got["resume"] is None


def test_main_prints_an_error_and_returns_1(s, monkeypatch, capsys):
    def fake(*a, **kw):
        raise ValueError("repo HEAD is not repo_commit")

    monkeypatch.setattr(llm_run, "run_llm", fake)
    code = llm_run.main([str(s["q"]), "--repo", str(s["repo"]), "--config", str(s["cfg"]),
                         "--mode", "rag"])
    assert code == 1
    assert capsys.readouterr().out.startswith("error: repo HEAD is not repo_commit")
