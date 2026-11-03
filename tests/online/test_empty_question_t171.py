"""T17.1 empty-question tests (tests-first); 2 Nov development test, problem 11.

Contract under test (Spec AC-9.3, AC-8.1):
  - ask() rejects a question with no letter or digit in it (empty, whitespace,
    punctuation or symbols only, an emoji) by raising ValueError before any
    work: no indexing, no retrieval, no generator call, and no audit log
    (nothing was processed)
  - the message says the question has no words, and that each question is
    answered on its own
  - a real question with spaces around it, and a non-English question, still
    run normally (the check does not change the question)
  - the CLI reports the problem in one line and exits 1; it does not crash
"""

import functools

import pytest

import codecompass.online as online
from codecompass.online import cli
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import build_history_repo

# Each input catches one realistic wrong check:
NO_WORDS = [
    "",                    # no check at all
    "   ",                 # a check for "" only
    "\n\t",                # a check for spaces only, not newlines or tabs
    ".",                   # a check that only strips whitespace
    "?",                   # the same, and the real case: a confused user typing "?"
    '!@#$%^&*()<>?:"{}|',  # a hand-written list of banned symbols that misses some
    "___",                 # a regex \w check, which counts "_" as a letter
    "\U0001F44D",          # thumbs-up emoji: a check that bans English symbols only
]


@pytest.fixture
def nothing_may_run(monkeypatch):
    """Any indexing or retrieval step fails the test if it is reached."""
    def must_not_run(*args, **kwargs):
        raise AssertionError("the pipeline ran, but it should not have")
    for name in ("ensure_current", "open_index", "status", "_retrieve_and_answer"):
        monkeypatch.setattr(online, name, must_not_run)


@pytest.mark.parametrize("question", NO_WORDS)
def test_a_question_with_no_words_is_rejected(tmp_path, nothing_may_run, question):
    with pytest.raises(ValueError, match="no words"):
        online.ask(tmp_path / "repo", question, config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs())


@pytest.mark.parametrize("question", NO_WORDS)
def test_the_generator_is_never_called(tmp_path, nothing_may_run, question):
    generator = CitingGenerator()
    with pytest.raises(ValueError):
        online.ask(tmp_path / "repo", question, config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs(generator))
    assert generator.calls == []


@pytest.mark.parametrize("question", NO_WORDS)
def test_no_audit_log_is_written(tmp_path, nothing_may_run, question):
    with pytest.raises(ValueError):
        online.ask(tmp_path / "repo", question, config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs())
    log_dir = tmp_path / "queries"
    assert not log_dir.exists() or list(log_dir.iterdir()) == []


@pytest.mark.parametrize("question", NO_WORDS)
def test_the_message_says_each_question_is_answered_on_its_own(tmp_path, nothing_may_run,
                                                                question):
    with pytest.raises(ValueError, match="answered on its own"):
        online.ask(tmp_path / "repo", question, config=config(tmp_path),
                   index_dir=tmp_path / "idx", **stubs())


@pytest.mark.parametrize("question", ["   Why does authenticate retry?   ",
                                      "authenticate 为什么会重试？",
                                      "x"])
def test_a_real_question_still_runs(tmp_path, question):
    repo = build_history_repo(tmp_path / "repo")
    generator = CitingGenerator()
    result = online.ask(repo.path, question, config=config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs(generator))
    assert len(generator.calls) >= 1
    assert result.audit_log["question"] == question  # checked, not changed


@pytest.mark.parametrize("question", ["", "   ", "."])
def test_the_cli_reports_it_in_one_line(monkeypatch, capsys, tmp_path, nothing_may_run,
                                        question):
    monkeypatch.setattr(cli, "ask", functools.partial(online.ask, **stubs()))
    code = cli.main(["ask", str(tmp_path / "repo"), question])
    out = capsys.readouterr()
    assert code == 1
    assert out.out == ""
    assert "error:" in out.err and "no words" in out.err
    assert "Traceback" not in out.err
