"""T13.2 real generator smoke test (model-marked, local only).

Contract under test (Spec AC-5.1–5.11 end to end): LlamaServerGenerator
talks to a running llama-server for the active profile; a question about the
fixture repo gets an answer with a Sources section, and the citation checker
classifies it. Retrieval uses the stub embedder and re-ranker, so only the
generator is real.
"""

import dataclasses

import pytest

import codecompass.online as online
from codecompass.offline.config import EmbedderConfig, load_config
from tests.online.model_support import real_config, real_generator
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_reranker import StubReranker


@pytest.mark.model
def test_real_generator_answers_with_checked_sources(tmp_path):
    offline = dataclasses.replace(
        load_config(None), embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    cfg = real_config(tmp_path, offline=offline)
    gen = real_generator(cfg)
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "How many times does authenticate retry, and why?",
                        config=cfg, generator=gen, reranker=StubReranker(),
                        embedder=StubEmbedder(), index_dir=tmp_path / "idx")
    print(result.answer)
    assert result.sources, "the model must end with a Sources section (Article VI.4)"
    assert result.citation_outcome in ("F", "G")
    assert result.audit_log["citation"]["outcome"] == result.citation_outcome
