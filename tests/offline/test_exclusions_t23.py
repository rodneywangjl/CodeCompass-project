"""T2.3 non-code classification tests (tests-first)."""

from codecompass.offline.config import FilesConfig
from codecompass.offline.exclusions import decide


def test_prose_and_config_are_non_code():
    for p in ["README.md", "notes.txt", "data.json", "cfg.yaml", "cfg.yml"]:
        d = decide(p, FilesConfig())
        assert not d.included and d.reason == "non-code", p


def test_unsupported_language_source_is_included():
    d = decide("src/tool.go", FilesConfig())
    assert d.included, "source without a grammar must use fallback, not skip"


def test_source_extension_set_comes_from_config():
    cfg = FilesConfig(source_extensions=(".py",))
    assert decide("a.py", cfg).included
    assert not decide("a.js", cfg).included
