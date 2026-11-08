"""T5.1 run details tests (tests-first).

Contract under test (Spec AC-5.3, AC-6.2; Plan 003 §3.1):
  - codecompass.eval.run_meta.run_meta(config_path, repo_path, *, index_dir=None,
    profile=None, server_url=None, project_dir=None) -> dict
  - every key of plan §3.1 is always present; a value is None when it does not apply
  - /props is read through the module's ``urlopen`` (tests replace it: the required
    suite blocks real sockets); the GPU name comes from the module's ``gpu_name()``
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import subprocess
from datetime import datetime
from urllib.error import URLError

import pytest

import codecompass.offline as offline
from codecompass.eval import run_meta as rm
from codecompass.online.config import load_online_config
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_embedder import StubEmbedder

EXPECTED_KEYS = {
    "codecompass": {"commit", "tag", "dirty"},
    "repo": {"path", "head_commit"},
    "index": {"dir", "state", "indexed_commit", "embedder_model", "embedder_revision"},
    "config": {"path", "sha256", "retrieval", "chunking"},
    "embedder": {"model", "revision", "device"},
    "reranker": {"model", "revision", "device", "dtype"},
    "generator": {"profile", "model_id", "gguf_file", "gguf_checksum_pinned",
                  "context_window", "temperature", "seed", "timeout_seconds",
                  "max_verifier_rounds"},
    "server": {"url", "build_info", "model_path", "n_ctx"},
    "host": {"hostname", "gpu", "python", "started_at"},
}

TOML = """\
[embedder]
model = "stub"
revision = "stub-1"
dimension = 8
device = "cpu"

[reranker]
model = "rerank-test"
revision = "rev-r1"
device = "cuda"
dtype = "float16"

[retrieval]
rerank_k = 40
docs_fallback = false

[chunking]
target_tokens = 400

[tools]
max_verifier_rounds = 2

[generator]
timeout_seconds = 333

[generator.profiles.evaltest]
model_id = "Test-Model-14B"
gguf_file = "test-model-q4_k_m.gguf"
gguf_checksum = "c0ffee"
context_window = 4096
temperature = 0.2
seed = 7
"""


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit_all(cwd, message="c"):
    _git(cwd, "add", "-A")
    _git(cwd, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """A config file, the history fixture repo, an index dir and a git project dir."""
    cfg = tmp_path / "eval.toml"
    cfg.write_text(TOML)
    repo = build_history_repo(tmp_path / "repo")
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q")
    (project / "README.md").write_text("project\n")
    commit = _commit_all(project)
    monkeypatch.setattr(rm, "gpu_name", lambda: None)
    return {"cfg": cfg, "repo": repo.path, "idx": tmp_path / "idx",
            "project": project, "commit": commit, "tmp": tmp_path}


def _meta(s, **kw):
    kw.setdefault("index_dir", s["idx"])
    kw.setdefault("project_dir", s["project"])
    return rm.run_meta(s["cfg"], s["repo"], **kw)


class _Props:
    """Fake urlopen answering GET /props like llama-server, recording the URLs asked."""

    def __init__(self, error=None):
        self.urls, self.error = [], error

    def __call__(self, request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else request
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        assert url.endswith("/props"), url
        body = {"build_info": "b11960-620d2225c",
                "model_path": "/models/test-model-q4_k_m.gguf",
                "default_generation_settings": {"n_ctx": 32768}}
        return _Resp(json.dumps(body).encode())


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# -- every key, every case (AC-5.3) ----------------------------------------------------


def test_every_key_present_without_profile_or_server(setup):
    meta = _meta(setup)
    assert {g: set(v) for g, v in meta.items()} == EXPECTED_KEYS
    assert all(v is None for v in meta["generator"].values())
    assert all(v is None for v in meta["server"].values())


def test_every_key_present_with_profile_and_server(setup, monkeypatch):
    monkeypatch.setattr(rm, "urlopen", _Props())
    meta = _meta(setup, profile="evaltest", server_url="http://127.0.0.1:8080")
    assert {g: set(v) for g, v in meta.items()} == EXPECTED_KEYS


def test_result_is_json_serialisable(setup, monkeypatch):
    monkeypatch.setattr(rm, "urlopen", _Props())
    meta = _meta(setup, profile="evaltest", server_url="http://127.0.0.1:8080")
    assert json.loads(json.dumps(meta)) == meta


# -- generator: the resolved profile and config (AC-6.2) ------------------------------


def test_generator_fields_come_from_the_profile_and_config(setup):
    gen = _meta(setup, profile="evaltest")["generator"]
    assert gen == {
        "profile": "evaltest", "model_id": "Test-Model-14B",
        "gguf_file": "test-model-q4_k_m.gguf", "gguf_checksum_pinned": "c0ffee",
        "context_window": 4096, "temperature": 0.2, "seed": 7,
        "timeout_seconds": 333, "max_verifier_rounds": 2,
    }


def test_unknown_profile_fails_loudly(setup):
    with pytest.raises(ValueError, match="nope"):
        _meta(setup, profile="nope")


# -- server: GET /props (AC-6.2) ------------------------------------------------------


def test_server_fields_come_from_props(setup, monkeypatch):
    fake = _Props()
    monkeypatch.setattr(rm, "urlopen", fake)
    server = _meta(setup, server_url="http://127.0.0.1:8080/")["server"]
    assert fake.urls == ["http://127.0.0.1:8080/props"]
    assert server == {"url": "http://127.0.0.1:8080/", "build_info": "b11960-620d2225c",
                      "model_path": "/models/test-model-q4_k_m.gguf", "n_ctx": 32768}


def test_unreachable_server_raises_value_error(setup, monkeypatch):
    monkeypatch.setattr(rm, "urlopen", _Props(error=URLError("refused")))
    with pytest.raises(ValueError, match="127.0.0.1:8080"):
        _meta(setup, server_url="http://127.0.0.1:8080")


def test_no_server_url_means_no_request(setup, monkeypatch):
    fake = _Props()
    monkeypatch.setattr(rm, "urlopen", fake)
    _meta(setup)
    assert fake.urls == []


# -- codecompass: commit, tag, dirty (AC-6.2, AC-6.4) ---------------------------------


def test_commit_is_read_from_git_and_clean_tree_is_not_dirty(setup):
    cc = _meta(setup)["codecompass"]
    assert cc == {"commit": setup["commit"], "tag": None, "dirty": False}


def test_tagged_head_gives_the_tag(setup):
    _git(setup["project"], "tag", "eval-v1")
    assert _meta(setup)["codecompass"]["tag"] == "eval-v1"


def test_uncommitted_change_makes_dirty_true(setup):
    (setup["project"] / "README.md").write_text("changed\n")
    assert _meta(setup)["codecompass"]["dirty"] is True


def test_not_a_git_checkout_gives_none(setup):
    plain = setup["tmp"] / "plain"
    plain.mkdir()
    assert _meta(setup, project_dir=plain)["codecompass"] == {
        "commit": None, "tag": None, "dirty": None}


# -- repo and index: offline status() (AC-6.2) ----------------------------------------


def test_repo_head_is_recorded(setup):
    repo = _meta(setup)["repo"]
    assert repo == {"path": str(setup["repo"]),
                    "head_commit": _git(setup["repo"], "rev-parse", "HEAD")}


def test_unindexed_repo_gives_empty_index(setup):
    index = _meta(setup)["index"]
    assert index["dir"] == str(setup["idx"])
    assert index["state"] == "empty"
    assert index["indexed_commit"] is None
    assert index["embedder_model"] is None


def test_index_fields_come_from_status(setup):
    cfg = load_online_config(setup["cfg"]).offline
    offline.ensure_current(setup["repo"], config=cfg, index_dir=setup["idx"],
                           embedder=StubEmbedder())
    index = _meta(setup)["index"]
    assert index["state"] == "current"
    assert index["indexed_commit"] == _git(setup["repo"], "rev-parse", "HEAD")
    assert (index["embedder_model"], index["embedder_revision"]) == ("stub", "stub-1")


# -- config, embedder, re-ranker (AC-5.4a, AC-6.2) ------------------------------------


def test_config_path_hash_and_settings(setup):
    meta = _meta(setup)
    assert meta["config"]["path"] == str(setup["cfg"])
    assert meta["config"]["sha256"] == hashlib.sha256(setup["cfg"].read_bytes()).hexdigest()
    assert meta["config"]["retrieval"]["rerank_k"] == 40
    assert meta["config"]["retrieval"]["docs_fallback"] is False
    assert meta["config"]["chunking"]["target_tokens"] == 400


def test_config_hash_changes_when_the_file_changes(setup):
    before = _meta(setup)["config"]["sha256"]
    setup["cfg"].write_text(TOML + "\n# edited\n")
    assert _meta(setup)["config"]["sha256"] != before


def test_embedder_and_reranker_come_from_config(setup):
    meta = _meta(setup)
    assert meta["embedder"] == {"model": "stub", "revision": "stub-1", "device": "cpu"}
    assert meta["reranker"] == {"model": "rerank-test", "revision": "rev-r1",
                                "device": "cuda", "dtype": "float16"}


# -- host (AC-6.2) --------------------------------------------------------------------


def test_host_fields(setup, monkeypatch):
    monkeypatch.setattr(rm, "gpu_name", lambda: "NVIDIA GeForce RTX 3090")
    host = _meta(setup)["host"]
    assert host["gpu"] == "NVIDIA GeForce RTX 3090"
    assert isinstance(host["hostname"], str) and host["hostname"]
    assert host["python"].count(".") == 2
    assert datetime.fromisoformat(host["started_at"]).utcoffset() is not None


def test_no_gpu_gives_none(setup):
    assert _meta(setup)["host"]["gpu"] is None


def test_retrieval_settings_are_a_plain_copy(setup):
    """The recorded settings are data, not the live config object."""
    meta = _meta(setup)
    assert isinstance(meta["config"]["retrieval"], dict)
    fields = {f.name for f in dataclasses.fields(load_online_config(setup["cfg"]).retrieval)}
    assert set(meta["config"]["retrieval"]) == fields
