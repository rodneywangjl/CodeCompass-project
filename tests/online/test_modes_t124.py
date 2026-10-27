"""T12.4 evaluation modes tests (tests-first).

Contract under test (Spec AC-10.1–10.5, FR-18; Plan D17; Article VII.3, VII.4):
  - pipeline.mode defaults to rag_tools; an unknown mode fails loudly at load
  - rag: retrieves and re-ranks, no tool rule in the prompt, no tool runs
    (a requested one is removed and logged)
  - no_retrieval: ensure_current runs, but no embedding, search or re-rank;
    no chunks are sent; a cited file is therefore flagged G
  - every mode uses the same profile and model; the log records the mode
"""

import pytest

import codecompass.online as online
from codecompass.online.config import OnlineConfig, load_online_config
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_LOG, StubGenerator

FAKE = "Done [1].\n\nSources\n[1] src/auth.py, lines 1-5 (indexed at a1b2c3d)"


def test_default_mode_and_loud_failure(tmp_path):
    assert OnlineConfig().pipeline.mode == "rag_tools"
    f = tmp_path / "codecompass.toml"
    f.write_text('[pipeline]\nmode = "rag_only"\n')
    with pytest.raises(ValueError, match="pipeline.mode"):
        load_online_config(f)
    f.write_text('[pipeline]\nmode = "no_retrieval"\n')
    assert load_online_config(f).pipeline.mode == "no_retrieval"


def test_rag_mode_retrieves_but_runs_no_tools(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    gen = CitingGenerator(before=[TOOL_CALL_LOG + "\nIt retries."])
    kit = stubs(gen)
    result = online.ask(repo.path, "Why retry?", config=config(tmp_path, mode="rag"),
                        index_dir=tmp_path / "idx", **kit)
    assert kit["reranker"].calls
    assert "<tool>" not in gen.calls[0][0]["content"]
    assert len(gen.calls) == 1
    assert result.audit_log["tool_calls"] == [
        {"round": 0, "ignored_calls": 1, "reason": "tools disabled"}]
    assert result.answer.endswith("It retries.")
    assert result.audit_log["mode"] == "rag"


def test_no_retrieval_mode_sends_no_chunks(monkeypatch, tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    called = []
    monkeypatch.setattr(online, "open_index", lambda *a, **k: called.append("open"))
    gen = StubGenerator([FAKE])
    kit = stubs(gen)
    result = online.ask(repo.path, "Why retry?", config=config(tmp_path, mode="no_retrieval"),
                        index_dir=tmp_path / "idx", **kit)
    assert called == [] and kit["reranker"].calls == []
    assert "--- " not in gen.calls[0][1]["content"]
    assert result.citation_outcome == "G"
    assert result.audit_log["mode"] == "no_retrieval"
    assert result.audit_log["retrieved"] == []


@pytest.mark.parametrize("mode", ["rag_tools", "rag", "no_retrieval"])
def test_every_mode_uses_the_same_model(tmp_path, mode):
    repo = build_history_repo(tmp_path / "repo")
    log = online.ask(repo.path, "Why?", config=config(tmp_path, mode=mode),
                     index_dir=tmp_path / "idx", **stubs(StubGenerator([FAKE]))).audit_log
    assert (log["profile"], log["model_id"]) == ("dev", "Qwen2.5-Coder-14B-Instruct")
