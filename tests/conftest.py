"""Any unexpected network access in the default suite is a test failure."""

import socket

import pytest


@pytest.fixture(autouse=True)
def disallow_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Network access in a deterministic test")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
