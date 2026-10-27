"""T11.3 profile and model in the log tests (tests-first).

Contract under test (Spec AC-5.8, AC-7.1; Article V.1, VII.3, VIII.4):
  - every audit log records the profile name, resolved model id,
    cache_prompt, pipeline mode and max_verifier_rounds in force
"""

import codecompass.online as online
from tests.online.ask_support import config, stubs
from tests.support.fixture_repo import build_history_repo


def test_run_settings_are_recorded(tmp_path):
    repo = build_history_repo(tmp_path / "repo")
    log = online.ask(repo.path, "Why retry?", config=config(tmp_path, max_verifier_rounds=2),
                     profile="prod", index_dir=tmp_path / "idx", **stubs()).audit_log
    assert log["profile"] == "prod"
    assert log["model_id"] == "Qwen2.5-Coder-32B-Instruct"
    assert log["cache_prompt"] is True
    assert log["mode"] == "rag_tools"
    assert log["max_verifier_rounds"] == 2
