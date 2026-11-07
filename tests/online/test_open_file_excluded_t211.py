"""T21.1 open_file refuses files the indexer excludes (tests-first).

Contract under test (Constitution III.6, V.2, VI.1, X.4; Plan D6, D18):
  - open_file refuses a path whose file name matches files.exclude_patterns, or
    that has a directory in files.exclude_dirs, read from the merged config
  - the refusal is an error tool result naming the file as excluded, with none
    of the file's text; it applies with and without `lines`
  - the indexer's size, binary and non-code skips do not apply (README readable)
  - nothing from a refused file becomes citable evidence (citing it is G)
"""

import dataclasses
import subprocess

import pytest

import codecompass.online as online
from tests.online.ask_support import config, stubs
from tests.support.stub_generator import StubGenerator

SECRET = "SECRET=topsecret-7f3a"
KEY = "-----BEGIN OPENSSH PRIVATE KEY----- fake-key-91c2"
VENDORED = "vendored_marker_5d1e = 1;"
CUSTOM = "db_password: hunter2-4b8c"
APP = "def login(user):\n    return retry_login(user)\n"
README = "# Demo\nreadme_marker_2a6f explains login.\n"
QUESTION = "How does login retry?"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    files = {"src/app.py": APP, ".env": SECRET + "\n", "keys/id_rsa": KEY + "\n",
             "node_modules/lib/index.js": VENDORED + "\n",
             "config/secrets.yaml": CUSTOM + "\n", "README.md": README}
    for rel, text in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(text)
    for args in (["init", "-q"], ["add", "-A", "-f"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _sha(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()


def _ask(tmp_path, repo, call, answer="I could not find enough evidence.", cfg=None):
    gen = StubGenerator([f"<tool>{call}</tool>", answer])
    result = online.ask(repo, QUESTION, config=cfg or config(tmp_path),
                        index_dir=tmp_path / "idx", **stubs(gen))
    return result, gen


def _tool_messages(gen):
    """Every tool-result message the model received, across all its calls."""
    return [m["content"] for call in gen.calls for m in call
            if m["role"] == "user" and m["content"].startswith("<tool_result")]


def _everything_seen(gen):
    return "\n".join(m["content"] for call in gen.calls for m in call)


# --- excluded files are refused ---------------------------------------------------

@pytest.mark.parametrize("call, path, text", [
    ('open_file(path=".env", lines="1")', ".env", SECRET),
    ('open_file(path=".env")', ".env", SECRET),
    ('open_file(path="keys/id_rsa", lines="1")', "keys/id_rsa", KEY),
    ('open_file(path="node_modules/lib/index.js", lines="1")',
     "node_modules/lib/index.js", VENDORED),
], ids=["env-lines", "env-outline", "key-pattern", "excluded-dir"])
def test_excluded_file_is_refused(tmp_path, repo, call, path, text):
    result, gen = _ask(tmp_path, repo, call)
    [message] = _tool_messages(gen)
    assert 'error="' in message
    assert "excluded" in message and path in message
    assert text not in _everything_seen(gen)
    [entry] = result.audit_log["tool_calls"]
    assert entry["tool"] == "open_file" and entry["error"] is True


def test_refused_file_is_not_citable(tmp_path, repo):
    answer = (f"The secret is set in .env [1].\n\nSources\n"
              f"[1] .env, lines 1-1 (indexed at {_sha(repo)[:7]})")
    result, _ = _ask(tmp_path, repo, 'open_file(path=".env", lines="1")', answer)
    assert result.citation_outcome == "G"
    assert SECRET not in result.answer


# --- other files are still readable ---------------------------------------------

@pytest.mark.parametrize("call, text", [
    ('open_file(path="src/app.py", lines="1-2")', "return retry_login(user)"),
    ('open_file(path="README.md", lines="1-2")', "readme_marker_2a6f"),
], ids=["code", "readme-non-code"])
def test_other_files_still_open(tmp_path, repo, call, text):
    result, gen = _ask(tmp_path, repo, call)
    [message] = _tool_messages(gen)
    assert 'error="' not in message
    assert text in message
    assert result.audit_log["tool_calls"][0]["error"] is False


# --- the rule comes from config ---------------------------------------------------

def test_default_config_reads_a_file_it_does_not_exclude(tmp_path, repo):
    _, gen = _ask(tmp_path, repo, 'open_file(path="config/secrets.yaml", lines="1")')
    assert CUSTOM in _tool_messages(gen)[0]


def test_configured_pattern_is_refused(tmp_path, repo):
    cfg = config(tmp_path)
    files = dataclasses.replace(
        cfg.offline.files, exclude_patterns=(*cfg.offline.files.exclude_patterns, "secrets.yaml"))
    cfg = dataclasses.replace(cfg, offline=dataclasses.replace(cfg.offline, files=files))
    _, gen = _ask(tmp_path, repo, 'open_file(path="config/secrets.yaml", lines="1")', cfg=cfg)
    [message] = _tool_messages(gen)
    assert 'error="' in message and "excluded" in message
    assert CUSTOM not in _everything_seen(gen)
