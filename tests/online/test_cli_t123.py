"""T12.3 CLI entry point tests (tests-first).

Contract under test (Spec AC-8.1–8.4, AC-5.8):
  - codecompass.online.cli.main(["ask", REPO, QUESTION, ...]) -> exit code
  - prints the rendered answer to stdout; logs "profile <name> (<model id>)"
    once to stderr at startup; --profile selects a profile; --verbose prints
    retrieved chunks and tool calls to stderr; flagged and stale answers show
    their warnings before the answer text
  - python -m codecompass.online.cli --help works
"""

import functools
import os
import subprocess
import sys
from pathlib import Path

import pytest

import codecompass.online as online
from codecompass.offline import EnsureResult
from codecompass.online import cli
from codecompass.online.citation import formatter
from tests.online.ask_support import stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

ROOT = Path(__file__).resolve().parents[2]
FAKE = "Done [1].\n\nSources\n[1] src/missing.py, lines 1-5 (indexed at a1b2c3d)"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    repo = build_history_repo(tmp_path / "repo")
    toml = tmp_path / "codecompass.toml"
    # as_posix(): Windows backslashes are escape sequences in TOML basic strings.
    toml.write_text(f'[index]\ndir = "{(tmp_path / "idx").as_posix()}"\n'
                    '[embedder]\nmodel = "stub"\nrevision = "stub-1"\ndimension = 8\n'
                    f'[logging]\nquery_log_dir = "{(tmp_path / "queries").as_posix()}"\n')
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    return repo.path, toml


def use(monkeypatch, generator=None):
    monkeypatch.setattr(cli, "ask", functools.partial(online.ask, **stubs(generator)))


def run(capsys, *args):
    code = cli.main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_prints_answer_and_logs_profile(monkeypatch, capsys, setup):
    repo, toml = setup
    use(monkeypatch)
    code, out, err = run(capsys, "ask", str(repo), "Why retry?", "--config", str(toml))
    assert code == 0
    assert out.startswith("Login retries on timeout [1].")
    assert err.count("profile dev (Qwen2.5-Coder-14B-Instruct)") == 1


def test_profile_flag_selects_prod(monkeypatch, capsys, setup):
    repo, toml = setup
    use(monkeypatch)
    _, _, err = run(capsys, "ask", str(repo), "Why?", "--config", str(toml), "--profile", "prod")
    assert "profile prod (Qwen2.5-Coder-32B-Instruct)" in err


def test_verbose_prints_retrieval_and_tool_details(monkeypatch, capsys, setup):
    repo, toml = setup
    use(monkeypatch)
    _, out, err = run(capsys, "ask", str(repo), "Why retry?", "--config", str(toml), "--verbose")
    assert "src/auth.py" in err and "rrf" in err.lower() and "tool calls: 0" in err
    assert "rrf" not in out.lower()


def test_flagged_answer_shows_the_banner(monkeypatch, capsys, setup):
    repo, toml = setup
    use(monkeypatch, StubGenerator([FAKE]))
    _, out, _ = run(capsys, "ask", str(repo), "Why?", "--config", str(toml))
    assert out.startswith(formatter.BANNER)


def test_stale_warning_comes_first(monkeypatch, capsys, setup):
    repo, toml = setup
    use(monkeypatch)
    run(capsys, "ask", str(repo), "Why?", "--config", str(toml))  # build the index
    monkeypatch.setattr(online, "ensure_current", lambda *a, **k: EnsureResult(
        ok=False, status="locked", message="locked"))
    _, out, _ = run(capsys, "ask", str(repo), "Why?", "--config", str(toml))
    assert out.startswith(online.STALE_WARNING)


def test_module_help_runs():
    proc = subprocess.run([sys.executable, "-m", "codecompass.online.cli", "--help"],
                          capture_output=True, text=True, cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert proc.returncode == 0 and "ask" in proc.stdout
