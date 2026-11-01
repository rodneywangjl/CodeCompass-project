"""T1.2 (Spec 004) startup and wiring: tests first.

Contract under test (Spec 004 AC-1.1, 1.3, 1.4, 1.9, 1.10, 1.13):
  main(argv=None, *, stdin=None, stdout=None, stderr=None) -> int
  - the repository root is `git rev-parse --show-toplevel` of REPO (default:
    the working directory); that root, not the working directory, reaches ask()
  - config: --config, else <root>/codecompass.toml, else
    $XDG_CONFIG_HOME (or ~/.config)/codecompass/codecompass.toml, else defaults
  - startup banner (profile, model id, root, config file) on stderr, once, only
    on a terminal; a generator that is down or mismatched gives a warning with
    the llama-server start command, and the session still runs
  - one generator for the whole session; the re-ranker and embedder are built
    on first use and then reused (T0.1); importing the module loads no model
  - startup failures return 1 with "error: ..." and ask nothing
No network, no model: the generator, the re-ranker and the embedder are fakes, and
the ask() spy is used except in the one end-to-end test.
"""

import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import codecompass.online as online
from codecompass.offline.models import EmbedderIdentity
from codecompass.online.citation.formatter import BANNER, MARK
from codecompass.online.tui import main
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

ROOT = Path(__file__).resolve().parents[2]


class In:
    def __init__(self, *lines, tty=False):
        self._lines, self._tty = list(lines), tty

    def isatty(self):
        return self._tty

    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class Out(io.StringIO):
    def __init__(self, tty=False):
        super().__init__()
        self._tty = tty

    def isatty(self):
        return self._tty


def write_toml(path, name):
    """A config whose default profile p-<name> (model m-<name>) shows which file was read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'[generator]\ndefault_profile = "p-{name}"\n'
        f'[generator.profiles.p-{name}]\nmodel_id = "m-{name}"\n'
        f'gguf_file = "{name}.gguf"\ncontext_window = 16384\n')
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Isolated home and config dirs, a fake generator class, and an ask() spy."""
    tmp = tmp_path.resolve()
    monkeypatch.setenv("HOME", str(tmp / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp / "home"))  # Windows: Path.home() ignores HOME
    monkeypatch.delenv("APPDATA", raising=False)  # Windows: the runner's real one would be read
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "xdg"))
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    w = SimpleNamespace(tmp=tmp, asks=[], generators=[], healthy=True, health_error=None,
                        ask_error=None, repo=build_history_repo(tmp / "repo"))

    class FakeGenerator:
        def __init__(self, profile, *, server_url, timeout_seconds):
            self.profile, self.server_url = profile, server_url
            w.generators.append(self)

        def health_check(self):
            if w.health_error:
                raise w.health_error
            return w.healthy

    def fake_ask(repo_path, question, **kw):
        w.asks.append(SimpleNamespace(repo=Path(repo_path), question=question, **kw))
        if w.ask_error:
            raise w.ask_error
        return SimpleNamespace(answer=f"answer to {question}")

    monkeypatch.setattr("codecompass.online.generator.llama.LlamaServerGenerator",
                        FakeGenerator)
    monkeypatch.setattr(online, "ask", fake_ask)

    def run(args=(), *lines, tty=False):
        stdout, stderr = Out(), Out(tty=tty)
        code = main(list(args), stdin=In(*lines, tty=tty), stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    w.run = run
    return w


# --- repository root (AC-1.1, AC-1.9) -----------------------------------------------


def test_started_in_the_repo_root_uses_it(world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    code, out, _ = world.run([], "why?\n")
    assert code == 0 and out == "answer to why?\n"
    assert [a.repo for a in world.asks] == [world.repo.path.resolve()]


def test_started_in_a_subdirectory_uses_the_repo_root(world, monkeypatch):
    monkeypatch.chdir(world.repo.path / "src")
    world.run([], "why?\n")
    assert world.asks[0].repo == world.repo.path.resolve()


def test_an_explicit_repo_argument_is_resolved_to_its_root(world, monkeypatch):
    monkeypatch.chdir(world.tmp)  # not inside the repo
    world.run([str(world.repo.path / "src")], "why?\n")
    assert world.asks[0].repo == world.repo.path.resolve()


def test_a_path_that_is_not_a_git_repository_fails_loudly(world, monkeypatch):
    plain = world.tmp / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    code, out, err = world.run([], "why?\n")
    assert code == 1 and out == ""
    assert err.startswith("error:") and "not a git repository" in err
    assert world.asks == [] and world.generators == []


def test_a_path_that_does_not_exist_fails_loudly(world):
    code, _, err = world.run([str(world.tmp / "nope")], "why?\n")
    assert code == 1 and "error:" in err and "nope" in err
    assert world.asks == [] and world.generators == []


# --- config lookup (AC-1.13) --------------------------------------------------------


@pytest.mark.parametrize("present, args, profile, source", [
    (("cli", "repo", "xdg", "home"), ["--config", "{cli}"], "p-cli", "{cli}"),
    (("repo", "xdg", "home"), [], "p-repo", "{repo}"),
    (("xdg", "home"), [], "p-xdg", "{xdg}"),
    (("home",), [], "p-home", "{home}"),
    ((), [], "dev", "built-in defaults"),
], ids=["explicit", "repo-root", "xdg", "home-config", "defaults"])
def test_config_lookup_order(world, monkeypatch, present, args, profile, source):
    paths = {"cli": world.tmp / "elsewhere" / "my.toml",
             "repo": world.repo.path / "codecompass.toml",
             "xdg": world.tmp / "xdg" / "codecompass" / "codecompass.toml",
             "home": world.tmp / "home" / ".config" / "codecompass" / "codecompass.toml"}
    for name in present:
        write_toml(paths[name], name)
    if "xdg" not in present:  # no XDG file: an unset variable falls back to ~/.config
        monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.chdir(world.repo.path)
    args = [a.format(**paths) for a in args]
    code, _, err = world.run(args, tty=True)  # banner needs a terminal; input ends at once
    assert code == 0
    assert f"profile {profile} (" in err
    assert f"config: {source.format(**paths)}" in err


def test_a_missing_config_option_is_an_error_not_a_fallback(world, monkeypatch):
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    missing = world.tmp / "missing.toml"
    code, _, err = world.run(["--config", str(missing)], "why?\n")
    assert code == 1 and "error:" in err and str(missing) in err
    assert world.asks == []


def test_a_malformed_config_fails_loudly(world, monkeypatch):
    bad = world.repo.path / "codecompass.toml"
    bad.write_text("[generator\nbroken")
    monkeypatch.chdir(world.repo.path)
    code, _, err = world.run([], "why?\n")
    assert code == 1 and err.startswith("error:") and "Traceback" not in err
    assert world.asks == []


def test_the_profile_option_overrides_the_config_default(world, monkeypatch):
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    world.run(["--profile", "prod"], "why?\n")
    assert world.asks[0].profile == "prod"
    assert world.generators[0].profile.model_id == "Qwen2.5-Coder-32B-Instruct"


def test_an_unknown_profile_fails_loudly(world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    code, _, err = world.run(["--profile", "nope"], "why?\n")
    assert code == 1 and "error:" in err and "nope" in err
    assert world.asks == [] and world.generators == []


# --- startup banner and generator health (AC-1.10, AC-1.11) -------------------------


def test_a_terminal_session_prints_one_banner(world, monkeypatch):
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    _, _, err = world.run([], "a?\n", "b?\n", tty=True)
    assert err.count("profile p-repo (m-repo)") == 1
    assert f"repo: {world.repo.path.resolve()}" in err


def test_piped_input_prints_no_banner(world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    _, out, err = world.run([], "a?\n")
    assert err == "" and out == "answer to a?\n"


def test_a_generator_that_is_down_gives_a_warning_with_the_start_command(world, monkeypatch):
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    world.healthy = False
    for tty in (False, True):  # the warning is not part of the banner: it shows when piped too
        code, out, err = world.run([], "a?\n", tty=tty)
        assert code == 0 and "answer to a?\n" in out  # the session still runs
        assert "warning:" in err and "http://127.0.0.1:8080" in err
        assert "llama-server -m" in err and "repo.gguf" in err
        assert "--port 8080" in err and "-c 16384" in err


def test_a_server_that_does_not_match_the_profile_gives_its_message_as_a_warning(
        world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    world.health_error = RuntimeError("llama-server context is 4096 tokens per slot")
    code, out, err = world.run([], "a?\n")
    assert code == 0 and out == "answer to a?\n"
    assert "warning:" in err and "context is 4096 tokens per slot" in err


def test_a_healthy_generator_gives_no_warning(world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    _, _, err = world.run([], "a?\n")
    assert "warning" not in err


# --- wiring (AC-1.2, AC-1.4) ----------------------------------------------------------


def test_one_generator_serves_every_question_and_ask_gets_the_session_settings(
        world, monkeypatch):
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    world.run(["--index-dir", str(world.tmp / "idx")], "a?\n", "b?\n", "c?\n")
    assert len(world.generators) == 1
    assert [a.question for a in world.asks] == ["a?", "b?", "c?"]
    assert all(a.generator is world.generators[0] for a in world.asks)
    assert all(a.profile == "p-repo" for a in world.asks)
    assert all(str(a.index_dir) == str(world.tmp / "idx") for a in world.asks)
    assert world.asks[0].config.generator.default_profile == "p-repo"


def test_a_failing_question_is_reported_and_the_session_survives(world, monkeypatch):
    monkeypatch.chdir(world.repo.path)
    world.ask_error = RuntimeError("no index is available")
    code, out, err = world.run([], "a?\n", "b?\n")
    assert code == 0 and out == ""
    assert err.count("error: no index is available") == 2
    assert [a.question for a in world.asks] == ["a?", "b?"]


def test_importing_the_module_loads_no_model_library():
    probe = ("import sys, codecompass.online.tui; "
             "bad = [m for m in ('torch', 'sentence_transformers', 'transformers', "
             "'chromadb', 'tantivy') if m in sys.modules]; "
             "sys.exit(','.join(bad) or 0)")
    run = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, capture_output=True,
                         text=True)
    assert run.returncode == 0, f"imported at startup: {run.stderr or run.stdout}"


# --- the real ask(), with stub models (AC-1.3, AC-1.4) --------------------------------


def test_the_real_pipeline_end_to_end_flags_a_bad_citation_and_builds_models_once(
        world, monkeypatch):
    """Real ask(), real citation checker; only the models are stand-ins."""
    monkeypatch.undo()  # drop the ask() spy and the fake generator class...
    tmp = world.tmp
    monkeypatch.setenv("HOME", str(tmp / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp / "xdg"))
    monkeypatch.delenv("GENERATOR_PROFILE", raising=False)
    built = {"generator": [], "embedder": [], "reranker": []}

    class Generator(StubGenerator):
        def __init__(self, profile, *, server_url, timeout_seconds):
            super().__init__(["It retries [1].\n\nSources\n"
                              "[1] src/nowhere.py, lines 1-3 (indexed at abc1234)\n"])
            self.profile = profile
            built["generator"].append(self)

        def health_check(self):
            return True

    class Embedder(StubEmbedder):
        def __init__(self, embedder_config):
            super().__init__(embedder_config.dimension)
            self.identity = EmbedderIdentity(model=embedder_config.model,
                                             revision=embedder_config.revision,
                                             dimension=embedder_config.dimension)
            built["embedder"].append(self)

    class Reranker(StubReranker):
        def __init__(self, reranker_config):
            super().__init__()
            built["reranker"].append(self)

    monkeypatch.setattr("codecompass.online.generator.llama.LlamaServerGenerator", Generator)
    monkeypatch.setattr("codecompass.offline.embedding.CodeEmbedder", Embedder)
    monkeypatch.setattr("codecompass.online.retrieval.reranker.BgeReranker", Reranker)
    cfg = world.repo.path / "codecompass.toml"
    cfg.write_text(f'[embedder]\nmodel = "stub"\nrevision = "stub-{tmp.name}"\ndimension = 8\n'
                   f'[reranker]\nrevision = "rerank-{tmp.name}"\n'
                   '[retrieval]\nmin_top_score = 0\n')  # not about the evidence gate (T15.1)
    monkeypatch.chdir(world.repo.path)
    stdout, stderr = Out(), Out()
    code = main(["--index-dir", str(tmp / "idx")], stdin=In("a?\n", "b?\n", "c?\n"),
                stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue()
    assert stdout.getvalue().count(BANNER) == 3  # a flagged answer never looks verified
    assert stdout.getvalue().count(f"{MARK}[1] src/nowhere.py") == 3
    assert {k: len(v) for k, v in built.items()} == {"generator": 1, "embedder": 1,
                                                       "reranker": 1}
