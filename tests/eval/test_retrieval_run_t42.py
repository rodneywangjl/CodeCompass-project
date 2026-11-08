"""T4.2 retrieval runner tests (tests-first).

Contract under test (Spec 003 US4, US6; Plan 003 §2.2):
  - codecompass/eval/retrieval_run.py exposes:
      run_retrieval(question_files, repo_path, *, config, index_dir=None, embedder=None,
                    reranker=None, generator=None, sent=False, reported=False,
                    codecompass_dir=None, config_path=None, out_dir=Path("eval/results")) -> Path
      main(argv=None) -> int for:
      python -m codecompass.eval.retrieval_run FILE... --repo PATH [--config] [--index-dir]
      [--sent] [--reported] [--out]
  - For each answerable question, records ranked lists: "vector", "bm25", "rrf", "rrf+rerank",
    each chunk entry having path, start_line, end_line, score
  - Functions used are the pipeline's own retrieval components; unanswerable questions are
    excluded from n and listed in summary["excluded"]
  - whole_file is true when ground-truth ranges span line 1 to the file's last line at repo_commit
  - Refuses to run if index commit != repo_commit or if question sets fail check_question_set
  - Results written to <out_dir>/retrieval-<UTC time>.json with meta, questions, and summary
  - meta contains all §2.2 fields including "index_dir", "codecompass_commit", "codecompass_clean",
    "score_note", and omits committed user/host names
  - summary equals hitrate.hit_rates over the recorded lists
  - Without sent=True, no generator is contacted and sent figure is recorded as null
  - With sent=True, sent chunks are recorded via fit_chunks(chunk_budget(...)) matching ask()
    (evidence gate and final_k cap; refuses docs_fallback=True)
  - --reported requires --config and a clean git checkout (via codecompass_dir)
  - main() returns 0 and prints results path on success, 1 with "error:" on failure
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from codecompass.eval import hitrate
from codecompass.eval.retrieval_run import main, run_retrieval
from codecompass.offline import ensure_current, open_index
from codecompass.offline.meta import index_path_for
from codecompass.online.retrieval.hybrid import retrieve
from tests.online.ask_support import config as make_online_config
from tests.support.fixture_repo import build_fixture_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker


class FailingGenerator:
    """Generator stub that fails the test if any method is called."""

    def generate(self, *args, **kwargs):
        raise AssertionError("Generator.generate() should not be called when sent=False")

    def count_tokens(self, *args, **kwargs):
        raise AssertionError("Generator.count_tokens() should not be called when sent=False")


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _make_row(commit: str, qid: str = "core-arch-01", *, category: str = "architectural",
              ground_truth: list[dict] | None = None, question: str = "How does hello work?"):
    gt = ([{"path": "src/main.py", "start_line": 1, "end_line": 3}]
          if ground_truth is None and category != "unanswerable" else (ground_truth or []))
    citations = [{"path": "src/main.py", "lines": f"{g['start_line']}-{g['end_line']}"}
                 for g in gt]
    return {
        "id": qid,
        "set": "core",
        "category": category,
        "complexity": "simple",
        "question": question,
        "reference_answer": "Defined in src/main.py.",
        "reference_citations": citations,
        "ground_truth_files": gt,
        "source": "hand-written",
        "ai_assisted": False,
        "repo_commit": commit,
        "original_id": None,
    }


@pytest.fixture
def test_setup(tmp_path):
    repo = build_fixture_repo(tmp_path / "repo")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo.path, text=True
    ).strip()
    idx_dir = tmp_path / "idx"
    out_dir = tmp_path / "results"
    cfg = make_online_config(tmp_path)
    embedder = StubEmbedder()
    reranker = StubReranker()
    ensure_current(repo.path, config=cfg.offline, index_dir=idx_dir, embedder=embedder)
    return {
        "repo": repo,
        "commit": commit,
        "idx_dir": idx_dir,
        "out_dir": out_dir,
        "cfg": cfg,
        "embedder": embedder,
        "reranker": reranker,
    }


# 1. For each answerable question, the results file has four ranked lists: "vector", "bm25",
#    "rrf", "rrf+rerank"; each entry has path, start_line, end_line, score
def test_answerable_question_has_four_ranked_lists_with_required_fields(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    assert res_path.exists()
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert len(data["questions"]) == 1
    ranked = data["questions"][0]["ranked"]
    assert set(ranked.keys()) == {"vector", "bm25", "rrf", "rrf+rerank"}
    for setup_name, chunk_list in ranked.items():
        assert len(chunk_list) > 0, f"{setup_name} should not be empty"
        for item in chunk_list:
            assert set(item.keys()) == {"path", "start_line", "end_line", "score"}
            assert isinstance(item["path"], str)
            assert isinstance(item["start_line"], int)
            assert isinstance(item["end_line"], int)
            assert isinstance(item["score"], (int, float))


# 2. The lists come from the pipeline's own functions: vector top 10, bm25 top 10, rrf = the
#    re-rank shortlist from retrieve(), rrf+rerank = rerank_chunks over that shortlist
def test_ranked_lists_come_from_pipeline_components(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    ranked = data["questions"][0]["ranked"]
    assert len(ranked["vector"]) <= 10
    assert len(ranked["bm25"]) <= 10
    rrf_chunks = [(c["path"], c["start_line"], c["end_line"]) for c in ranked["rrf"]]
    rerank_chunks = [(c["path"], c["start_line"], c["end_line"]) for c in ranked["rrf+rerank"]]
    assert set(rrf_chunks) == set(rerank_chunks)
    assert len(rrf_chunks) == len(rerank_chunks)
    scores = [c["score"] for c in ranked["rrf+rerank"]]
    assert scores == sorted(scores, reverse=True)

    # Assert rrf list matches retrieve(handles, question, config=cfg.retrieval) in order
    handles = open_index(s["repo"].path, config=s["cfg"].offline, index_dir=s["idx_dir"],
                         embedder=s["embedder"])
    try:
        shortlist = retrieve(handles, "How does hello work?", config=s["cfg"].retrieval)
        records = handles.vector.records_for_ids([cid for cid, _ in shortlist])
        expected = [(records[cid]["metadata"]["file_path"],
                     records[cid]["metadata"]["start_line"],
                     records[cid]["metadata"]["end_line"]) for cid, _ in shortlist]
    finally:
        handles.close()
    assert rrf_chunks == expected


# 3. Unanswerable questions (empty ground_truth_files) get no ranked lists and appear in
#    summary["excluded"]
def test_unanswerable_questions_get_no_ranked_lists_and_are_excluded(test_setup, tmp_path):
    s = test_setup
    rows = [
        _make_row(s["commit"], "core-arch-01", question="How does hello work?"),
        _make_row(s["commit"], "core-unans-01", category="unanswerable", ground_truth=[],
                  question="What is the flux capacitor?"),
    ]
    q_file = _write_jsonl(tmp_path / "q.jsonl", rows)
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert data["summary"]["excluded"] == ["core-unans-01"]
    unans_q = next(q for q in data["questions"] if q["id"] == "core-unans-01")
    assert unans_q["ranked"] == {}


# 4. whole_file is true when every ground-truth range is line 1 to the file's last line at
#    repo_commit, and false otherwise
def test_whole_file_flag_computed_from_line_counts_at_repo_commit(test_setup, tmp_path):
    s = test_setup
    line_count = len(subprocess.check_output(
        ["git", "show", f"{s['commit']}:src/main.py"], cwd=s["repo"].path, text=True
    ).splitlines())
    rows = [
        _make_row(s["commit"], "q-whole",
                  ground_truth=[{"path": "src/main.py", "start_line": 1, "end_line": line_count}]),
        _make_row(s["commit"], "q-partial",
                  ground_truth=[{"path": "src/main.py", "start_line": 1, "end_line": 2}]),
    ]
    q_file = _write_jsonl(tmp_path / "q.jsonl", rows)
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    q_map = {q["id"]: q for q in data["questions"]}
    assert q_map["q-whole"]["whole_file"] is True
    assert q_map["q-partial"]["whole_file"] is False


# 5. An index built at a different commit than the questions' repo_commit stops the run with a
#    clear error naming both commits, and writes no results file
def test_mismatched_index_commit_and_repo_commit_refuses_and_writes_no_file(test_setup, tmp_path):
    s = test_setup
    other_commit = s["repo"].commits["modify"]
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(other_commit)])
    with pytest.raises(ValueError) as exc:
        run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    msg = str(exc.value)
    assert s["commit"][:7] in msg or s["commit"] in msg
    assert other_commit[:7] in msg or other_commit in msg
    assert not list(s["out_dir"].glob("*.json"))


# 6. Question files that fail check_question_set stop the run with the problems listed
def test_invalid_question_set_stops_run_with_problems_listed(test_setup, tmp_path):
    s = test_setup
    bad_row = _make_row(s["commit"])
    bad_row["category"] = "invalid-category"
    q_file = _write_jsonl(tmp_path / "bad_q.jsonl", [bad_row])
    with pytest.raises(ValueError) as exc:
        run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    assert "invalid-category" in str(exc.value)
    assert not list(s["out_dir"].glob("*.json"))


# 7. The results file is written under out_dir as retrieval-<UTC time>.json and has "meta",
#    "questions", "summary"; meta contains every field in plan §2.2,
#    score_note, and omits user/host
def test_results_file_structure_and_meta_fields(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    assert res_path.name.startswith("retrieval-") and res_path.name.endswith(".json")
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"meta", "questions", "summary"}
    meta = data["meta"]
    expected_fields = {
        "codecompass_commit", "codecompass_clean", "repo_commit", "indexed_commit",
        "index_dir", "embedder", "reranker", "retrieval", "chunking", "config_path",
        "question_files", "ks", "label", "score_note", "started_at", "ended_at",
        "platform", "python",
    }
    assert expected_fields.issubset(set(meta.keys()))
    assert meta["repo_commit"] == s["commit"]
    assert meta["indexed_commit"] == s["commit"]
    assert isinstance(meta["question_files"], list)
    assert "sha256" in meta["question_files"][0]
    assert meta["label"] == "dev"
    assert "score_note" in meta
    assert "rank position" in meta["score_note"]
    assert "user" not in meta
    assert "host" not in meta


# 8. summary equals hitrate.hit_rates over the recorded lists with ks
#    {"vector":[1,5,10], "bm25":[1,5,10], "rrf":[1,5,10], "rrf+rerank":[1,5]}
def test_summary_equals_hitrate_hit_rates(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    expected_ks = {"vector": [1, 5, 10], "bm25": [1, 5, 10], "rrf": [1, 5, 10],
                   "rrf+rerank": [1, 5]}
    expected_summary = json.loads(
        json.dumps(hitrate.hit_rates(data["questions"], expected_ks))
    )
    assert data["summary"] == expected_summary


# 9. Without sent=True, no generator is called (use a generator stub that fails the test if
#    called) and the "sent" figure is recorded as not measured (null)
def test_without_sent_no_generator_called_and_sent_is_null(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"],
                             generator=FailingGenerator(), sent=False, out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert "sent" not in data["summary"]["setups"]
    assert data["meta"]["ks"].get("sent") is None
    assert "sent" not in data["questions"][0]["ranked"]


# 10. With sent=True and a stub generator, a "sent" list is recorded = fit_chunks(chunk_budget(...))
#     of the re-ranked chunks, and summary has "sent" at k "all"
def test_with_sent_records_fit_chunks_and_summary_at_k_all(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    gen = StubGenerator(["answer"])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"],
                             generator=gen, sent=True, out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert "sent" in data["summary"]["setups"]
    assert "all" in data["summary"]["setups"]["sent"]
    assert "sent" in data["questions"][0]["ranked"]
    assert len(data["questions"][0]["ranked"]["sent"]) > 0


# 10b. "sent" matches ask(): final_k cap, evidence gate, and docs_fallback rejection
def test_sent_respects_final_k_cap_and_evidence_gate(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    gen = StubGenerator(["answer"])

    # final_k cap
    cfg_k1 = dataclasses.replace(
        s["cfg"],
        retrieval=dataclasses.replace(s["cfg"].retrieval, final_k=1),
    )
    res_k1 = run_retrieval([q_file], s["repo"].path, config=cfg_k1, index_dir=s["idx_dir"],
                           embedder=s["embedder"], reranker=s["reranker"],
                           generator=gen, sent=True, out_dir=tmp_path / "res_k1")
    data_k1 = json.loads(res_k1.read_text(encoding="utf-8"))
    assert len(data_k1["questions"][0]["ranked"]["sent"]) <= 1

    # evidence gate: min_top_score above every score results in empty sent list, counted as a miss
    q_miss = _write_jsonl(tmp_path / "q_miss.jsonl",
                          [_make_row(s["commit"], question="xyznonexistent query term")])
    cfg_gate = dataclasses.replace(
        s["cfg"],
        retrieval=dataclasses.replace(s["cfg"].retrieval, min_top_score=1.0),
    )
    res_gate = run_retrieval([q_miss], s["repo"].path, config=cfg_gate, index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"],
                             generator=gen, sent=True, out_dir=tmp_path / "res_gate")
    data_gate = json.loads(res_gate.read_text(encoding="utf-8"))
    assert data_gate["questions"][0]["ranked"]["sent"] == []
    sent_summary = data_gate["summary"]["setups"]["sent"]["all"]["overall"]
    assert sent_summary["n"] == 1
    assert sent_summary["file_hits"] == 0


def test_sent_with_docs_fallback_true_raises_error(test_setup, tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    gen = StubGenerator(["answer"])
    cfg_docs = dataclasses.replace(
        s["cfg"],
        retrieval=dataclasses.replace(s["cfg"].retrieval, docs_fallback=True),
    )
    with pytest.raises(ValueError) as exc:
        run_retrieval([q_file], s["repo"].path, config=cfg_docs, index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"],
                      generator=gen, sent=True, out_dir=tmp_path / "res_docs")
    assert "--sent measures the docs_fallback-off path only" in str(exc.value)


# 11. index_dir and config passed in are the ones actually used
def test_custom_config_and_index_dir_are_used(test_setup, tmp_path):
    s = test_setup
    custom_idx = tmp_path / "custom_index"
    ensure_current(s["repo"].path, config=s["cfg"].offline, index_dir=custom_idx,
                   embedder=s["embedder"])
    custom_cfg = dataclasses.replace(
        s["cfg"],
        retrieval=dataclasses.replace(s["cfg"].retrieval, rerank_k=2),
    )
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=custom_cfg, index_dir=custom_idx,
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert data["meta"]["indexed_commit"] == s["commit"]
    expected_idx = index_path_for(s["repo"].path, custom_idx)
    assert data["meta"]["index_dir"] == str(expected_idx)
    assert data["meta"]["retrieval"]["rerank_k"] == 2
    assert len(data["questions"][0]["ranked"]["rrf"]) <= 2


# 11b. Default index dir resolves offline.index.dir
def test_default_index_dir_resolves_and_records_actual_index_dir(test_setup, tmp_path):
    s = test_setup
    base_idx = tmp_path / "base_idx"
    cfg_with_base = dataclasses.replace(
        s["cfg"],
        offline=dataclasses.replace(
            s["cfg"].offline,
            index=dataclasses.replace(s["cfg"].offline.index, dir=base_idx),
        ),
    )
    ensure_current(s["repo"].path, config=cfg_with_base.offline, embedder=s["embedder"])
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=cfg_with_base, index_dir=None,
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    expected_idx = index_path_for(s["repo"].path, base_idx)
    assert data["meta"]["index_dir"] == str(expected_idx)


# 12. label is "dev" by default; reported=True requires --config and clean git tree
def test_reported_requires_clean_git_tree_otherwise_raises_and_writes_nothing(test_setup,
                                                                             tmp_path):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    data = json.loads(res_path.read_text(encoding="utf-8"))
    assert data["meta"]["label"] == "dev"

    # Make a small temp git repo to simulate CodeCompass checkout
    cc_repo = tmp_path / "cc_repo"
    cc_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=cc_repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=cc_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=cc_repo, check=True)
    tracked_file = cc_repo / "file.txt"
    tracked_file.write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=cc_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=cc_repo, check=True)

    dummy_config_path = tmp_path / "codecompass.eval.toml"
    dummy_config_path.write_text("# eval config\n", encoding="utf-8")

    # 1. reported=True without config_path raises error
    with pytest.raises(ValueError) as exc_cfg:
        run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"], reported=True,
                      config_path=None, codecompass_dir=cc_repo, out_dir=tmp_path / "out_nocfg")
    assert "--reported needs --config" in str(exc_cfg.value)

    # 2. Uncommitted change: reported=True raises error mentioning uncommitted changes
    #    and writes nothing
    tracked_file.write_text("dirty\n", encoding="utf-8")
    reported_out = tmp_path / "reported_out"
    with pytest.raises(ValueError) as exc:
        run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"], reported=True,
                      config_path=dummy_config_path, codecompass_dir=cc_repo, out_dir=reported_out)
    assert "uncommitted" in str(exc.value).lower()
    assert not reported_out.exists() or not list(reported_out.glob("*.json"))

    # 3. After committing: reported=True succeeds and meta["label"] == "reported"
    subprocess.run(["git", "add", "file.txt"], cwd=cc_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "clean"], cwd=cc_repo, check=True)
    res_rep = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                            embedder=s["embedder"], reranker=s["reranker"], reported=True,
                            config_path=dummy_config_path, codecompass_dir=cc_repo,
                            out_dir=reported_out)
    data_rep = json.loads(res_rep.read_text(encoding="utf-8"))
    assert data_rep["meta"]["label"] == "reported"
    assert data_rep["meta"]["config_path"] == str(dummy_config_path)

    # 4. Directory without .git raises an error with reported=True
    non_git_dir = tmp_path / "non_git"
    non_git_dir.mkdir()
    with pytest.raises(ValueError) as exc_nongit:
        run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                      embedder=s["embedder"], reranker=s["reranker"], reported=True,
                      config_path=dummy_config_path, codecompass_dir=non_git_dir,
                      out_dir=tmp_path / "nongit_out")
    assert "git" in str(exc_nongit.value).lower()


# 13. main() returns 0 and prints the results path on success, 1 with an "error:" line otherwise
def test_main_cli_returns_0_and_prints_path_on_success_and_1_on_error(test_setup, tmp_path,
                                                                      capsys, monkeypatch):
    s = test_setup
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    fake_path = tmp_path / "results" / "retrieval-fake.json"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text("{}", encoding="utf-8")

    called_args = {}

    def fake_run_retrieval(question_files, repo_path, **kwargs):
        called_args["question_files"] = question_files
        called_args["repo_path"] = repo_path
        called_args.update(kwargs)
        return fake_path

    monkeypatch.setattr("codecompass.eval.retrieval_run.run_retrieval", fake_run_retrieval)

    rc = main([str(q_file), "--repo", str(s["repo"].path), "--index-dir", str(s["idx_dir"]),
               "--out", str(s["out_dir"])])
    captured = capsys.readouterr()
    assert rc == 0
    assert str(fake_path) in captured.out
    assert Path(called_args["repo_path"]) == s["repo"].path
    assert Path(called_args["index_dir"]) == s["idx_dir"]
    assert Path(called_args["out_dir"]) == s["out_dir"]

    # Error case: monkeypatch a fake that raises ValueError("boom")
    def failing_run_retrieval(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr("codecompass.eval.retrieval_run.run_retrieval", failing_run_retrieval)
    rc_err = main([str(q_file), "--repo", str(s["repo"].path),
                   "--index-dir", str(s["idx_dir"]), "--out", str(s["out_dir"])])
    captured_err = capsys.readouterr()
    assert rc_err == 1
    err_lines = (captured_err.out + captured_err.err).splitlines()
    assert any(line.strip().startswith("error:") and "boom" in line for line in err_lines)


# 17. a question mixing a whole-file entry with a real range records only the real range as
#     line_truth and is not whole_file; an all-whole-file question has empty line_truth
def test_line_truth_keeps_only_real_ranges(test_setup, tmp_path):
    s = test_setup
    line_count = len(subprocess.check_output(
        ["git", "show", f"{s['commit']}:src/main.py"], cwd=s["repo"].path, text=True
    ).splitlines())
    whole = {"path": "src/main.py", "start_line": 1, "end_line": line_count}
    part = {"path": "src/main.py", "start_line": 1, "end_line": 2}
    rows = [_make_row(s["commit"], "q-mixed", ground_truth=[whole, part]),
            _make_row(s["commit"], "q-whole", ground_truth=[whole])]
    q_file = _write_jsonl(tmp_path / "q.jsonl", rows)
    res_path = run_retrieval([q_file], s["repo"].path, config=s["cfg"], index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    q = {r["id"]: r for r in json.loads(res_path.read_text(encoding="utf-8"))["questions"]}
    assert q["q-mixed"]["line_truth"] == [part] and q["q-mixed"]["whole_file"] is False
    assert q["q-whole"]["line_truth"] == [] and q["q-whole"]["whole_file"] is True


# 18. embedder and re-ranker settings in meta come from the config, not from the objects
def test_meta_records_embedder_and_reranker_settings_from_config(test_setup, tmp_path):
    s = test_setup
    cfg = dataclasses.replace(
        s["cfg"], reranker=dataclasses.replace(s["cfg"].reranker, device="cuda", dtype="float16"))
    q_file = _write_jsonl(tmp_path / "q.jsonl", [_make_row(s["commit"])])
    res_path = run_retrieval([q_file], s["repo"].path, config=cfg, index_dir=s["idx_dir"],
                             embedder=s["embedder"], reranker=s["reranker"], out_dir=s["out_dir"])
    meta = json.loads(res_path.read_text(encoding="utf-8"))["meta"]
    assert meta["reranker"] == {"model": cfg.reranker.model, "revision": cfg.reranker.revision,
                                "device": "cuda", "dtype": "float16",
                                "class": type(s["reranker"]).__name__}
    emb = cfg.offline.embedder
    assert meta["embedder"] == {"model": emb.model, "revision": emb.revision,
                                "device": emb.device, "class": type(s["embedder"]).__name__}
