"""T9.6 citation checker is non-bypassable tests (tests-first).

Contract under test (Spec AC-4.2; Article VI.2):
  - every ask() runs the citation checker exactly once, in every mode and on
    the no-evidence path
  - no configuration field can switch it off
  - a generator citing a file that was not retrieved always yields G
"""

import dataclasses

import pytest

import codecompass.online as online
from codecompass.online.citation import checker, formatter
from codecompass.online.config import OnlineConfig
from tests.online.ask_support import config, docs_only_repo, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

FAKE = "Done [1].\n\nSources\n[1] src/missing.py, lines 1-5 (indexed at a1b2c3d)"


def _field_names(obj):
    for f in dataclasses.fields(obj):
        yield f.name
        value = getattr(obj, f.name)
        if dataclasses.is_dataclass(value):
            yield from _field_names(value)


def test_no_config_field_can_skip_the_checker():
    names = list(_field_names(OnlineConfig()))
    assert not [n for n in names if any(w in n for w in ("skip", "bypass", "citation"))]


def test_fabricated_citation_is_always_flagged(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    result = online.ask(repo.path, "Why retry?", config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs(StubGenerator([FAKE])))
    assert result.citation_outcome == "G"
    assert result.answer.startswith(formatter.BANNER)


@pytest.mark.parametrize("mode", ["rag_tools", "rag", "no_retrieval"])
def test_checker_runs_once_per_question_in_every_mode(monkeypatch, tmp_path, mode):
    repo = build_history_repo(tmp_path / "repo")
    seen = []
    real = checker.check
    monkeypatch.setattr(checker, "check", lambda *a, **k: seen.append(1) or real(*a, **k))
    online.ask(repo.path, "Why retry?", config=config(tmp_path, mode=mode),
               index_dir=tmp_path / "idx", **stubs(StubGenerator([FAKE])))
    assert seen == [1]


def test_checker_runs_on_the_no_evidence_path(monkeypatch, tmp_path):
    seen = []
    real = checker.check
    monkeypatch.setattr(checker, "check", lambda *a, **k: seen.append(1) or real(*a, **k))
    online.ask(docs_only_repo(tmp_path / "docs"), "Where?", config=config(tmp_path),
               index_dir=tmp_path / "idx", **stubs())
    assert seen == [1]
