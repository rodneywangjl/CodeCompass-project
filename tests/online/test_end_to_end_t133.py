"""T13.3 end-to-end smoke test (model-marked, local only).

Contract under test (whole spec): ask() on the fixture repo with the real
embedder, re-ranker and generator gives a grounded answer (at least one
citation verified against the evidence), a complete audit log, and a
recorded citation outcome. Runs for the profile in GENERATOR_PROFILE; run it
again per profile whose server is available.
"""

import pytest

import codecompass.online as online
from codecompass.online.logging import STAGES
from tests.online.model_support import real_config, real_generator
from tests.support.fixture_repo import build_history_repo


@pytest.mark.model
def test_real_pipeline_end_to_end(tmp_path):
    cfg = real_config(tmp_path)
    gen = real_generator(cfg)
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "Why does authenticate retry on timeout?",
                        config=cfg, generator=gen, index_dir=tmp_path / "idx")
    print(result.answer)
    log = result.audit_log
    assert any(s.verified for s in result.sources), "no citation matched the evidence"
    assert log["retrieved"] and any(c["sent"] for c in log["retrieved"])
    assert set(log["timings"]) == set(STAGES) | {"total"}
    assert log["citation"]["outcome"] == result.citation_outcome in ("F", "G")
    assert log["model_id"] == gen.profile.model_id
