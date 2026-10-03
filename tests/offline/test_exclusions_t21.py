"""T2.1 pattern and directory exclusion tests (tests-first)."""

from codecompass.offline.config import FilesConfig
from codecompass.offline.exclusions import decide


def _decided(path, cfg=None):
    return decide(path, cfg or FilesConfig())


def test_defaults_exclude_secrets_keys_lockfiles():
    for p in [".env", ".env.local", "id_rsa", "server.pem", "cert.crt",
              "package-lock.json", "yarn.lock"]:
        d = _decided(f"src/{p}" if not p.startswith(".env") else p)
        assert not d.included, p
        assert d.reason != "include", p


def test_defaults_exclude_dirs_and_minified():
    for p in ["node_modules/x.js", "build/out.js", "dist/b.js",
              "__pycache__/a.pyc", "app.min.js", "static/bundle.min.css"]:
        d = _decided(p)
        assert not d.included, p


def test_source_files_included_and_rule_reported():
    d = _decided("src/main.py")
    assert d.included and d.reason == "include"
    d = _decided(".env")
    assert not d.included and ".env" in d.reason


def test_custom_rules_work():
    cfg = FilesConfig(exclude_patterns=("*.gen.py",), exclude_dirs=("gen",))
    assert not decide("src/x.gen.py", cfg).included
    assert not decide("gen/y.py", cfg).included
    assert decide("src/y.py", cfg).included
