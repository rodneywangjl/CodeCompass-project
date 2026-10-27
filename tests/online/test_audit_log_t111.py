"""T11.1 per-query audit log tests (tests-first).

Contract under test (Spec AC-7.1; Article V.4):
  - QueryResult.audit_log holds the question, profile, model id, every
    retrieved chunk with its RRF and re-ranker scores (and whether it was
    sent), every tool call (round, tool, args, cache hit), the citation
    outcome, and per-stage timings
"""

import codecompass.online as online
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_LOG

STAGES = {"ensure_current", "retrieval", "reranking", "generation", "tool_execution",
          "citation_check", "total"}


def test_audit_log_records_every_stage(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    gen = CitingGenerator(before=[TOOL_CALL_LOG])
    log = online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                     index_dir=tmp_path / "idx", **stubs(gen)).audit_log
    assert log["question"] == "Why does authenticate retry?"
    assert log["profile"] == "dev" and log["model_id"] == "Qwen2.5-Coder-14B-Instruct"
    assert log["retrieved"]
    for chunk in log["retrieved"]:
        assert {"chunk_id", "path", "lines", "rrf_score", "rerank_score", "sent"} <= set(chunk)
    assert any(c["sent"] for c in log["retrieved"])
    (call,) = log["tool_calls"]
    assert {"round": 0, "tool": "git_log", "cache_hit": False}.items() <= call.items()
    assert call["args"] == {"path": "src/auth.py", "n": 10}
    assert log["citation"]["outcome"] == "F"
    assert set(log["timings"]) == STAGES
    assert all(isinstance(v, float) and v >= 0 for v in log["timings"].values())
    assert log["generator_calls"] == 2 and log["round_limit_hit"] is False
