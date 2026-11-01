"""T2.1 (Spec 004) layered config: tests first.

Contract under test (Spec 004 AC-3.1, amending AC-1.13):
  load_online_config_layers(paths) -> OnlineConfig
  - paths run from the LOWEST priority to the highest; a later file's keys win,
    keys it does not set keep the earlier value, section by section
  - a [generator.profiles.X] table replaces the whole profile X of earlier files
  - a relative index.dir resolves against the file that set it
  - the merged result is validated as one config (unknown keys, bad values)
  codecompass: the user-level file is the base layer under the repo file; the
  banner lists every file used, highest priority first; --config uses only
  that file.
No network, no model: the T1.2 `world` fixture supplies fakes and isolated dirs.
"""

import pytest

from codecompass.online.config import load_online_config_layers
from tests.online.test_tui_main_t12 import world, write_toml  # noqa: F401 (fixture)

USER_AND_REPO_DEVICES = '[embedder]\ndevice = "cuda"\n[reranker]\ndevice = "cuda"\n'


def toml(tmp_path, name, text):
    path = tmp_path / name / "codecompass.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- the merge rules ------------------------------------------------------------------


def test_a_later_file_wins_and_earlier_keys_it_does_not_set_are_kept(tmp_path):
    user = toml(tmp_path, "user", '[generator]\ndefault_profile = "dev"\n'
                                  '[embedder]\ndevice = "cuda"\nbatch_size = 8\n')
    repo = toml(tmp_path, "repo", '[generator]\ndefault_profile = "prod"\n'
                                  '[embedder]\nbatch_size = 64\n')
    cfg = load_online_config_layers([user, repo])
    assert cfg.generator.default_profile == "prod"  # repo wins the conflict
    assert cfg.offline.embedder.batch_size == 64
    assert cfg.offline.embedder.device == "cuda"  # inherited from the user file


def test_sections_merge_key_by_key(tmp_path):
    user = toml(tmp_path, "user", "[retrieval]\nvector_k = 10\nkeyword_k = 20\n")
    repo = toml(tmp_path, "repo", "[retrieval]\nvector_k = 5\n")
    cfg = load_online_config_layers([user, repo])
    assert (cfg.retrieval.vector_k, cfg.retrieval.keyword_k) == (5, 20)


def test_the_order_of_the_paths_decides_who_wins(tmp_path):
    a = toml(tmp_path, "a", "[retrieval]\nvector_k = 1\n")
    b = toml(tmp_path, "b", "[retrieval]\nvector_k = 2\n")
    assert load_online_config_layers([a, b]).retrieval.vector_k == 2
    assert load_online_config_layers([b, a]).retrieval.vector_k == 1


def test_a_profile_table_replaces_the_whole_profile_of_that_name(tmp_path):
    user = toml(tmp_path, "user",
                '[generator.profiles.x]\nmodel_id = "m-user"\ncontext_window = 4096\n'
                'gguf_file = "user.gguf"\n')
    repo = toml(tmp_path, "repo", '[generator.profiles.x]\nmodel_id = "m-repo"\n')
    x = load_online_config_layers([user, repo]).generator.profiles["x"]
    assert x.model_id == "m-repo"
    assert x.context_window == 32768 and x.gguf_file == ""  # not mixed with the user's


def test_profiles_with_different_names_from_both_files_are_available(tmp_path):
    user = toml(tmp_path, "user", '[generator.profiles.mine]\nmodel_id = "m-mine"\n')
    repo = toml(tmp_path, "repo", '[generator.profiles.team]\nmodel_id = "m-team"\n')
    profiles = load_online_config_layers([user, repo]).generator.profiles
    assert {"dev", "prod", "mine", "team"} <= set(profiles)


def test_a_relative_index_dir_resolves_against_the_file_that_set_it(tmp_path):
    user = toml(tmp_path, "user", '[index]\ndir = "user-idx"\n')
    repo = toml(tmp_path, "repo", "")
    assert load_online_config_layers([user, repo]).offline.index.dir == str(
        user.parent / "user-idx")
    repo.write_text('[index]\ndir = "repo-idx"\n')
    assert load_online_config_layers([user, repo]).offline.index.dir == str(
        repo.parent / "repo-idx")


def test_a_single_file_and_no_files_behave_like_the_plain_loader(tmp_path):
    only = toml(tmp_path, "only", "[retrieval]\nvector_k = 7\n")
    assert load_online_config_layers([only]).retrieval.vector_k == 7
    assert load_online_config_layers([]).retrieval.vector_k == 50  # built-in default


def test_unknown_keys_and_sections_in_either_file_are_rejected(tmp_path):
    good = toml(tmp_path, "good", "[retrieval]\nvector_k = 7\n")
    bad_key = toml(tmp_path, "bad-key", "[retrieval]\nnope = 1\n")
    bad_section = toml(tmp_path, "bad-section", "[nonsense]\nx = 1\n")
    for bad in (bad_key, bad_section):
        with pytest.raises(Exception, match="nope|nonsense"):
            load_online_config_layers([bad, good])
        with pytest.raises(Exception, match="nope|nonsense"):
            load_online_config_layers([good, bad])


def test_the_merged_result_is_validated_not_each_file(tmp_path):
    user = toml(tmp_path, "user", "[tools]\nmax_verifier_rounds = -1\n")
    repo = toml(tmp_path, "repo", "[tools]\nmax_verifier_rounds = 3\n")
    assert load_online_config_layers([user, repo]).tools.max_verifier_rounds == 3
    with pytest.raises(ValueError, match="max_verifier_rounds"):
        load_online_config_layers([user])


# --- codecompass: the user-level file is the base layer (AC-3.1) ------------------------


def user_file(world, text):  # noqa: F811
    return toml(world.tmp, "xdg/codecompass", text)


def test_user_settings_reach_a_repo_that_has_its_own_config(world, monkeypatch):  # noqa: F811
    user_file(world, USER_AND_REPO_DEVICES)
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    code, _, _ = world.run([], "why?\n")
    cfg = world.asks[0].config
    assert code == 0
    assert (cfg.offline.embedder.device, cfg.reranker.device) == ("cuda", "cuda")
    assert world.asks[0].profile == "p-repo"  # and the repo's own settings still apply


def test_the_repo_wins_a_conflict_with_the_user_file(world, monkeypatch):  # noqa: F811
    user_file(world, '[generator]\ndefault_profile = "prod"\n[embedder]\ndevice = "cuda"\n')
    write_toml(world.repo.path / "codecompass.toml", "repo")
    (world.repo.path / "codecompass.toml").write_text(
        (world.repo.path / "codecompass.toml").read_text() + '[embedder]\ndevice = "cpu"\n')
    monkeypatch.chdir(world.repo.path)
    world.run([], "why?\n")
    assert world.asks[0].profile == "p-repo"
    assert world.asks[0].config.offline.embedder.device == "cpu"


def test_the_banner_lists_every_file_used_highest_priority_first(world, monkeypatch):  # noqa: F811
    user = user_file(world, USER_AND_REPO_DEVICES)
    repo = write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    _, _, err = world.run([], tty=True)
    assert f"config: {repo}, {user}" in err
    assert err.count("config:") == 1


def test_config_option_uses_only_that_file(world, monkeypatch):  # noqa: F811
    user_file(world, USER_AND_REPO_DEVICES)
    write_toml(world.repo.path / "codecompass.toml", "repo")
    mine = write_toml(world.tmp / "elsewhere" / "my.toml", "cli")
    monkeypatch.chdir(world.repo.path)
    _, _, err = world.run(["--config", str(mine)], "why?\n", tty=True)
    cfg = world.asks[0].config
    assert cfg.offline.embedder.device == "cpu" and cfg.reranker.device == "cpu"
    assert f"config: {mine}\n" in err and "xdg" not in err


def test_a_malformed_user_file_is_an_error_that_names_it(world, monkeypatch):  # noqa: F811
    bad = user_file(world, "[embedder\nbroken")
    write_toml(world.repo.path / "codecompass.toml", "repo")
    monkeypatch.chdir(world.repo.path)
    code, _, err = world.run([], "why?\n")
    assert code == 1 and err.startswith("error:") and str(bad) in err
    assert world.asks == []
