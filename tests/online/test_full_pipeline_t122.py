"""T12.2 full pipeline integration test (stubs, real stores on the fixture repo).

Contract under test (Spec P1 and P2 ACs; Plan §1):
  ensure_current -> open_index -> embed -> vector + keyword search -> RRF ->
  re-rank -> budget -> generate -> tool round -> generate -> citation check
  -> rendered answer, sources and audit log
"""

import codecompass.online as online
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import TOOL_CALL_LOG


def test_question_runs_end_to_end(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    gen = CitingGenerator(before=[TOOL_CALL_LOG])
    kit = stubs(gen)
    result = online.ask(repo.path, "Why does authenticate retry on timeout?",
                        config=config(tmp_path), index_dir=tmp_path / "idx", **kit)
    log = result.audit_log
    # retrieval reached the re-ranker with a shortlist, and chunks were sent
    (query, texts), = kit["reranker"].calls
    assert query == "Why does authenticate retry on timeout?" and texts
    assert sum(c["sent"] for c in log["retrieved"]) >= 1
    # one tool round, then the answer
    assert [c["tool"] for c in log["tool_calls"]] == ["git_log"]
    assert gen.calls[1][3]["content"].startswith('<tool_result tool="git_log"')
    # the citation was verified against what the model saw
    assert result.citation_outcome == "F" and result.sources[0].verified
    assert result.answer.startswith("Login retries on timeout [1].")
    assert log["citation"] == {"outcome": "F", "unverified": []}
