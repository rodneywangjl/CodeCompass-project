"""T3.4 (Spec 005) the precision setting assumes no GPU API: tests first.

Contract under test (Spec 005 AC-1.2, AC-4.1; constitution Article VIII.2):
  [reranker] dtype = "float16" is accepted on any device except the CPU (cuda, mps,
  xpu, ...) and rejected on "cpu" in any form, with an error that names a GPU device
  (cuda and mps). float32 works everywhere.
"""

import pytest

from codecompass.online.config import (
    RerankerConfig, load_online_config, load_online_config_layers)


@pytest.mark.parametrize("device", ["mps", "cuda:1", "xpu", "cuda"])
def test_float16_is_accepted_on_any_gpu_device(device):
    assert RerankerConfig(device=device, dtype="float16").device == device


@pytest.mark.parametrize("device", ["cpu", "cpu:0", "CPU", "Cpu:1"])
def test_float16_is_rejected_on_the_cpu_in_any_form(device):
    with pytest.raises(ValueError) as failure:
        RerankerConfig(device=device, dtype="float16")
    message = str(failure.value)
    assert "GPU" in message and "cuda" in message and "mps" in message


@pytest.mark.parametrize("device", ["cpu", "mps", "cuda", "xpu"])
def test_float32_works_on_every_device(device):
    assert RerankerConfig(device=device, dtype="float32").dtype == "float32"


@pytest.mark.parametrize("loader", [load_online_config,
                                    lambda path: load_online_config_layers([path])],
                         ids=["single", "layers"])
def test_both_loaders_accept_half_precision_on_a_mac_gpu(tmp_path, loader):
    path = tmp_path / "c.toml"
    path.write_text('[reranker]\ndevice = "mps"\ndtype = "float16"\n')
    cfg = loader(path)
    assert (cfg.reranker.device, cfg.reranker.dtype) == ("mps", "float16")
