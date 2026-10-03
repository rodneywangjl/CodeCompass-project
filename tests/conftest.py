"""Shared fixtures: block network sockets for the required (non-model) suite."""

import socket

import pytest


@pytest.fixture(autouse=True)
def _no_network(request):
    if "model" in request.keywords:
        yield
        return
    real_socket = socket.socket

    def blocked(*args, **kwargs):
        raise RuntimeError("network access blocked in the required test suite")

    socket.socket = blocked
    try:
        yield
    finally:
        socket.socket = real_socket
