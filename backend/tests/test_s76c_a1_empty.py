"""S76c: empty Worker snapshot marks sections failed without raising (A1-empty).

Provenance (rule 7): payload shape follows the real Worker /api/snapshot body
(ercot-hackathon/src/snapshot.js, backend/tests/fixtures/ercot/snapshot.json);
every section nulled to represent total data loss. Values are synthetic.
"""

import asyncio
import copy
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from gridmarket_server import ercot
from gridmarket_server.contracts import Signal

EMPTY = {
    "asOf": "2026-09-26T14:00:00Z",
    "ct": {"date": "2026-09-26", "hour": 9, "minute": 0},
    "heNow": 10,
    "errors": {"demand": "timeout", "spp": "timeout", "dam": "timeout", "adders": "timeout"},
    "demand": None,
    "hubs": None,
    "dam": None,
    "sced": None,
    "checks": [],
}
SECTIONS = ("SNAPSHOT-DEMAND", "SNAPSHOT-HUBS", "SNAPSHOT-DAM", "SNAPSHOT-SCED")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "a1.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db))
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    ercot.stats.snapshot_age_s = None
    ercot._snapshot_asof = None
    return db


def test_a1_empty_snapshot_marks_failed_without_raise(isolated: Path) -> None:
    ercot.parse_snapshot(copy.deepcopy(EMPTY))  # Must not raise (A1-empty).
    assert ercot.signals.series("SNAPSHOT-DEMAND", "ERCOT", "2020-01-01", "2030-01-01") == []
    assert ercot._snapshot_asof is None
    assert ercot.stats.snapshot_age_s is None
    for report in SECTIONS:
        assert (str(isolated), report) in ercot.signals.failed
    assert ercot.signals.current() == []  # Unavailable: nothing stored.


@contextmanager
def empty_worker() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps(EMPTY).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_a1_empty_snapshot_poll_path_marks_stale(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stamp = datetime.now(UTC).isoformat()
    ercot.signals.add(Signal("SNAPSHOT-DEMAND", "ERCOT", stamp, 5, 70000.0, "MW", stamp, stamp))
    assert ercot.signals.current()[0]["stale"] is False
    with empty_worker() as url:
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "test-key")
        monkeypatch.setattr(ercot, "REPORTS", {})
        asyncio.run(ercot.poll())
    assert ercot._snapshot_asof is None
    assert ercot.stats.snapshot_age_s is None
    for report in SECTIONS:
        assert (str(isolated), report) in ercot.signals.failed
    current = ercot.signals.current()
    assert len(current) == 1 and current[0]["stale"] is True
