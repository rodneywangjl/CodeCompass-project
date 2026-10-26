"""Online config merges offline sections faithfully (tests-first).

Fix outside a numbered task: T0.1's loader re-serialised the offline sections
to TOML text in a temp file. That broke on backslashes and quotes (e.g.
Windows paths) and resolved relative paths against the temp directory instead
of the config file's directory.
"""

import pytest

from codecompass.online.config import load_online_config


def test_index_dir_with_backslash_and_quote_survives(tmp_path):
    # TOML literal string: the value is exactly what is between the quotes.
    raw_dir = '/data/odd\\name"dir'
    f = tmp_path / "codecompass.toml"
    f.write_text("[index]\ndir = '/data/odd\\name\"dir'\n")
    cfg = load_online_config(f)
    assert cfg.offline.index.dir == raw_dir


def test_relative_index_dir_resolves_against_config_file(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text('[index]\ndir = "idx"\n')
    cfg = load_online_config(f)
    assert cfg.offline.index.dir == str(tmp_path / "idx")


def test_offline_and_online_sections_both_apply(tmp_path):
    f = tmp_path / "codecompass.toml"
    f.write_text(
        "[embedder]\n"
        'device = "mps"\n'
        "batch_size = 4\n"
        "[files]\n"
        'exclude_dirs = ["vendor", "C:\\\\build"]\n'
        "[retrieval]\n"
        "final_k = 4\n"
    )
    cfg = load_online_config(f)
    assert cfg.offline.embedder.device == "mps"
    assert cfg.offline.embedder.batch_size == 4
    assert cfg.offline.files.exclude_dirs == ("vendor", "C:\\build")
    assert cfg.retrieval.final_k == 4


def test_unknown_offline_key_still_rejected(tmp_path):
    # Regression guard: removing the temp-file step must keep validation.
    f = tmp_path / "codecompass.toml"
    f.write_text("[index]\nbogus = 1\n")
    with pytest.raises(ValueError, match="index.bogus"):
        load_online_config(f)
