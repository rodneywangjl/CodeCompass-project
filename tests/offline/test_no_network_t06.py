"""T0.6 network-free required suite and CI tests (tests-first)."""

import pathlib
import socket
import subprocess
import sys

import pytest


def test_socket_blocked_in_required_suite():
    with pytest.raises(RuntimeError):
        socket.socket()


@pytest.mark.model
def test_model_test_can_use_network():
    socket.socket().close()


def test_model_tests_deselected_by_default():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-m", "not model", "-p", "no:cacheprovider",
         "tests/offline/test_no_network_t06.py"],
        capture_output=True, text=True,
    )
    assert "test_model_test_can_use_network" not in r.stdout


def test_ci_runs_required_suite():
    text = pathlib.Path(".github/workflows/ci.yml").read_text()
    assert "-m" in text and "not model" in text
