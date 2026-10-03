"""T0.1 skeleton tests (tests-first, must fail before implementation)."""

def test_package_imports():
    import codecompass.offline  # noqa: F401


def test_model_marker_registered():
    # Verified via `pytest --markers` listing `model` (strict markers on).
    # This placeholder keeps the requirement visible in the suite.
    import pathlib

    text = ""
    for name in ("pyproject.toml", "pytest.ini", "setup.cfg"):
        p = pathlib.Path(name)
        if p.exists():
            text += p.read_text()
    assert "model" in text, "pytest config must register the `model` marker"
