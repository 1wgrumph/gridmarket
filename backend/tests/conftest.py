"""Keep all backend tests offline except their own loopback servers (TE-F2)."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_outbound_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = socket.socket.connect

    def loopback_only(sock: socket.socket, address: object) -> object:
        if sock.family == socket.AF_UNIX or (
            isinstance(address, tuple) and address[0] == "127.0.0.1"
        ):
            return connect(sock, address)
        raise RuntimeError("Outbound sockets are blocked in backend tests")

    monkeypatch.setattr(socket.socket, "connect", loopback_only)
