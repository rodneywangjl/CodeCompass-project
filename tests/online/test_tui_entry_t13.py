"""T1.3 (Spec 004) the `codecompass` command: tests first.

Contract under test (Spec 004 AC-1.12, AC-1.1):
  - pyproject.toml declares the console script
        codecompass = "codecompass.online.tui:main"
    and that target resolves to a callable
  - the build setup is declared and pinned (Article VIII.3): setuptools with a
    pinned version, packaging only codecompass*, never tests/ or docs/
  - `codecompass --help` exits 0 and documents the repo argument and the
    --profile, --config and --index-dir options
No install is run: the test reads pyproject.toml, so it needs no network.
"""

import importlib
import tomllib
from pathlib import Path

import pytest
from setuptools import find_packages

from codecompass.online.tui import main

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pyproject():
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_the_codecompass_script_points_at_main(pyproject):
    assert pyproject["project"]["scripts"] == {"codecompass": "codecompass.online.tui:main"}


def test_the_script_target_resolves_to_a_callable(pyproject):
    module, _, attr = pyproject["project"]["scripts"]["codecompass"].partition(":")
    assert callable(getattr(importlib.import_module(module), attr))


def test_the_build_backend_is_a_pinned_setuptools(pyproject):
    build = pyproject["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"
    assert len(build["requires"]) == 1
    assert build["requires"][0].startswith("setuptools==")  # pinned, like requirements.txt


def test_only_the_codecompass_packages_are_packaged(pyproject):
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    found = find_packages(where=str(ROOT), include=include)
    assert "codecompass" in found and "codecompass.online" in found
    assert "codecompass.offline" in found
    assert not [p for p in found if p.split(".")[0] != "codecompass"]  # no tests, no docs


def test_the_script_adds_no_runtime_dependency(pyproject):
    # dependencies stay in requirements.txt, the single pinned list (Article VIII.3)
    assert "dependencies" not in pyproject["project"]


def test_help_exits_zero_and_documents_the_arguments(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    text = capsys.readouterr().out.lower()
    for word in ("codecompass", "repo", "--profile", "--config", "--index-dir"):
        assert word in text
