"""Run MCP system tests against a real, local GridMarket backend."""

import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def allowed(sock: socket.socket, address: object) -> bool:
        return sock.family == socket.AF_UNIX or (
            sock.family == socket.AF_INET
            and isinstance(address, tuple)
            and address[0] == "127.0.0.1"
        )

    def guarded_connect(sock: socket.socket, address: object) -> None:
        if not allowed(sock, address):
            raise RuntimeError("Outbound sockets are blocked in MCP tests")
        connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object) -> int:
        if not allowed(sock, address):
            raise RuntimeError("Outbound sockets are blocked in MCP tests")
        return connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture
def backend(tmp_path: Path):
    @contextmanager
    def start():
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        db = tmp_path / "gridmarket.db"
        env = os.environ.copy()
        env.update(GRIDMARKET_DB=str(db), GRIDMARKET_NWS="off")
        env.pop("GRIDMARKET_WORKER_URL", None)
        with (tmp_path / "uvicorn.log").open("w") as log:
            process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "--project",
                    str(ROOT / "backend"),
                    "--frozen",
                    "uvicorn",
                    "gridmarket_server.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(150):
                    if process.poll() is not None:
                        break
                    try:
                        with urlopen(f"{url}/v1/market/status", timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    pytest.fail("uvicorn did not start on loopback")
                assert process.poll() is None, "uvicorn exited before readiness"
                yield url, db
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    return start
