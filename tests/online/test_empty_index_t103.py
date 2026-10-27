"""T10.3 empty index and no-evidence tests (tests-first).

Contract under test (Spec AC-6.3 edge case, AC-1.3; Plan D12; Article I.3):
  - an index with no chunks: online.NO_EVIDENCE answer, no generator call,
    not stale
  - an index with chunks but a context budget that fits none: the same
"""

import dataclasses

import codecompass.online as online
from codecompass.online.agent.harness import system_prompt
from codecompass.online.config import ModelProfile
from tests.online.ask_support import CitingGenerator, config, docs_only_repo, stubs
from tests.support.fixture_repo import build_history_repo


def test_empty_index_answers_no_evidence_without_generating(tmp_path):
    repo = docs_only_repo(tmp_path / "docs")
    gen = CitingGenerator()
    result = online.ask(repo, "Where is login?", config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs(gen))
    assert online.NO_EVIDENCE in result.answer
    assert gen.calls == [] and result.stale_index is False


def test_budget_with_room_for_no_chunk_answers_no_evidence(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    gen = CitingGenerator()
    cfg = config(tmp_path, max_verifier_rounds=0)
    window = 10 + gen.count_tokens(system_prompt(tools_enabled=True)) + 1
    tight = ModelProfile(model_id="m", context_window=window, max_tokens=10)
    cfg = dataclasses.replace(cfg, generator=dataclasses.replace(
        cfg.generator, profiles={"dev": tight}))
    result = online.ask(repo.path, "Why does authenticate retry?", config=cfg,
                        profile="dev", index_dir=tmp_path / "idx", **stubs(gen))
    assert online.NO_EVIDENCE in result.answer
    assert gen.calls == []
