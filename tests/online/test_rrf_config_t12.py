"""T1.2 RRF configuration tests (tests-first).

Contract under test (Spec AC-2.5; Plan D2, §7):
  - the RRF constant and k are parameters, not hard-coded
  - the defaults come from the online config (rrf_constant=60, rerank_k=50)
  - empty and single-item inputs are handled
"""

import pytest

from codecompass.online.config import load_online_config
from codecompass.online.retrieval.rrf import rrf_merge


def test_changing_constant_changes_scores():
    a = dict(rrf_merge(["x"], [], k=5, constant=60))
    b = dict(rrf_merge(["x"], [], k=5, constant=10))
    assert a["x"] == pytest.approx(1 / 60)
    assert b["x"] == pytest.approx(1 / 10)


def test_changing_k_changes_output_length():
    ids = [f"c{i}" for i in range(8)]
    assert len(rrf_merge(ids, [], k=3, constant=60)) == 3
    assert len(rrf_merge(ids, [], k=8, constant=60)) == 8


def test_empty_inputs_give_empty_result():
    assert rrf_merge([], [], k=50, constant=60) == []


def test_single_item_returns_that_item():
    out = rrf_merge([], ["only"], k=50, constant=60)
    assert [cid for cid, _ in out] == ["only"]


def test_config_values_drive_the_merge(tmp_path):
    cfg_file = tmp_path / "codecompass.toml"
    cfg_file.write_text("[retrieval]\nrrf_constant = 5\nrerank_k = 2\n")
    r = load_online_config(cfg_file).retrieval
    out = rrf_merge(["a", "b", "c"], [], k=r.rerank_k, constant=r.rrf_constant)
    assert [cid for cid, _ in out] == ["a", "b"]
    assert out[0][1] == pytest.approx(1 / 5)
