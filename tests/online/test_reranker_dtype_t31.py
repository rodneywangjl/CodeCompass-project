"""T3.1 (Spec 005) the re-ranker precision setting: tests first.

Contract under test (Spec 005 AC-1.1 to AC-1.6):
  [reranker] dtype = "float32" (default) | "float16"
  - anything else fails at config load and lists the allowed values; float16 on a CPU
    device fails and says it needs CUDA; both loaders accept the setting and layering
    merges it
  - BgeReranker loads exactly as before for float32, and with model_kwargs
    {"dtype": "float16"} for float16, at the same model and revision
  - every query's audit log records the re-ranker model, revision, device and dtype
No model, no GPU: CrossEncoder is a fake, except in the one marked test.
"""

import sys
import types

import pytest

import codecompass.online as online
from codecompass.online.config import (
    RerankerConfig, load_online_config, load_online_config_layers)
from codecompass.online.retrieval import reranker
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo


def write(path, text):
    path.write_text(text)
    return path


# --- the setting (AC-1.1, AC-1.2, AC-1.4) ----------------------------------------------


def test_the_default_is_float32():
    assert RerankerConfig().dtype == "float32"


@pytest.mark.parametrize("loader", [load_online_config,
                                    lambda path: load_online_config_layers([path])],
                         ids=["single", "layers"])
def test_both_loaders_accept_float16_on_cuda(tmp_path, loader):
    cfg = loader(write(tmp_path / "c.toml", '[reranker]\ndevice = "cuda"\ndtype = "float16"\n'))
    assert (cfg.reranker.device, cfg.reranker.dtype) == ("cuda", "float16")


def test_layers_merge_the_dtype_like_any_other_key(tmp_path):
    user = write(tmp_path / "user.toml", '[reranker]\ndevice = "cuda"\ndtype = "float16"\n')
    repo = write(tmp_path / "repo.toml", '[reranker]\nrevision = "' + "c" * 40 + '"\n')
    cfg = load_online_config_layers([user, repo])
    assert cfg.reranker.dtype == "float16" and cfg.reranker.revision == "c" * 40


@pytest.mark.parametrize("bad", ["int8", "bfloat16", "FLOAT16", ""])
def test_an_unknown_dtype_fails_and_lists_the_allowed_values(tmp_path, bad):
    path = write(tmp_path / "c.toml", f'[reranker]\ndevice = "cuda"\ndtype = "{bad}"\n')
    for loader in (load_online_config, lambda p: load_online_config_layers([p])):
        with pytest.raises(ValueError, match="float32.*float16|float16.*float32"):
            loader(path)


def test_float16_on_a_cpu_device_fails_and_says_it_needs_cuda(tmp_path):
    path = write(tmp_path / "c.toml", '[reranker]\ndtype = "float16"\n')  # device defaults to cpu
    with pytest.raises(ValueError, match="cuda"):
        load_online_config(path)
    with pytest.raises(ValueError, match="cuda"):
        RerankerConfig(device="cpu", dtype="float16")


@pytest.mark.parametrize("device, dtype", [("cpu", "float32"), ("cuda", "float32"),
                                           ("cuda", "float16"), ("cuda:0", "float16")])
def test_valid_combinations_are_accepted(device, dtype):
    assert RerankerConfig(device=device, dtype=dtype).dtype == dtype


# --- loading the model (AC-1.3) --------------------------------------------------------


def load_args(monkeypatch, cfg):
    seen = {}

    class FakeCrossEncoder:
        def __init__(self, model, **kwargs):
            seen.update(model=model, **kwargs)

        def predict(self, pairs, **kwargs):
            return [1.0 for _ in pairs]

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(CrossEncoder=FakeCrossEncoder))
    reranker.BgeReranker(cfg).rerank("q", ["text"])
    return seen


def test_float32_loads_exactly_as_before(monkeypatch):
    cfg = RerankerConfig(model="org/model", revision="b" * 40, device="cuda")
    assert load_args(monkeypatch, cfg) == {"model": "org/model", "revision": "b" * 40,
                                           "device": "cuda"}  # no extra argument


def test_float16_loads_in_half_precision_at_the_same_model_and_revision(monkeypatch):
    cfg = RerankerConfig(model="org/model", revision="b" * 40, device="cuda", dtype="float16")
    assert load_args(monkeypatch, cfg) == {"model": "org/model", "revision": "b" * 40,
                                           "device": "cuda",
                                           "model_kwargs": {"dtype": "float16"}}


# --- the audit log (AC-1.5) ------------------------------------------------------------


def test_every_query_log_records_the_reranker_settings(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    cfg = config(tmp_path)
    result = online.ask(repo.path, "Why does authenticate retry?", config=cfg,
                        index_dir=tmp_path / "idx", **stubs())
    assert result.audit_log["reranker"] == {
        "model": cfg.reranker.model, "revision": cfg.reranker.revision,
        "device": "cpu", "dtype": "float32"}


# --- the real model (AC-1.6) -----------------------------------------------------------


@pytest.mark.model
def test_the_fp16_reranker_still_prefers_the_relevant_chunk():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs a CUDA GPU")
    model = reranker.BgeReranker(RerankerConfig(device="cuda", dtype="float16"))
    relevant = ("def authenticate(client, user, password):\n"
                "    for attempt in range(MAX_RETRIES):\n"
                "        try:\n            return client.login(user, password)\n"
                "        except TimeoutError:\n            time.sleep(2 ** attempt)\n")
    irrelevant = "def noop():\n    return None\n"
    scores = model.rerank("Why does login retry when it times out?", [relevant, irrelevant])
    assert scores[0] > scores[1]
