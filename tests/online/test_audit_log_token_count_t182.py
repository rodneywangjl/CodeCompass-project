"""T18.2 audit log when token counting fails (tests-first); found in a real run, 3 Nov.

Contract under test (Spec AC-7.6; Article V.4):
  - ask() counts the system prompt's tokens with llama-server (/tokenize) before
    indexing, to check the round reserve. If that call fails, for example
    because llama-server is down or times out, the audit log is still written
    with the error, and the same error reaches the caller unchanged
  - a successful count still leads to a normal answer (unchanged)
"""

import json

import pytest

import codecompass.online as online
from codecompass.online.generator.protocol import GeneratorError
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo

TIMEOUT = "llama-server timed out after 120s: http://127.0.0.1:8080/tokenize"


class CountFailingGenerator(CitingGenerator):
    """count_tokens fails, as /tokenize does when llama-server is down."""

    def count_tokens(self, text: str) -> int:
        raise GeneratorError(TIMEOUT)


def logs(tmp_path):
    folder = tmp_path / "queries"
    return sorted(folder.glob("*.json")) if folder.exists() else []


def test_a_failed_token_count_still_writes_the_log(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    with pytest.raises(GeneratorError) as raised:
        online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs(CountFailingGenerator()))
    assert str(raised.value) == TIMEOUT
    files = logs(tmp_path)
    assert len(files) == 1, f"expected one audit log, found {len(files)}"
    log = json.loads(files[0].read_text(encoding="utf-8"))
    assert log["question"] == "Why does authenticate retry?"
    assert log["error"] == {"type": "GeneratorError", "message": TIMEOUT}


def test_the_model_is_never_asked_to_answer(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    generator = CountFailingGenerator()
    with pytest.raises(GeneratorError):
        online.ask(repo.path, "Why does authenticate retry?", config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs(generator))
    assert generator.calls == []
