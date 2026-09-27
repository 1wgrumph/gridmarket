"""Keep all backend tests offline except their own loopback servers (TE-F2)."""

import socket
from collections import deque

import pytest

from gridmarket_server import ercot
from gridmarket_server.contracts import WorkerStats


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


@pytest.fixture(autouse=True)
def fresh_ercot_worker_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """ERCOT poller telemetry is process-global; one test's polling must not raise
    another app instance's health:worker alert (mutation clean-run order)."""
    monkeypatch.setattr(ercot, "stats", WorkerStats())
    monkeypatch.setattr(ercot, "_snapshot_asof", None)
    monkeypatch.setattr(ercot, "_latencies", deque())
    monkeypatch.setattr(ercot, "_last_polled", {})
