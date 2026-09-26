"""S03: Worker-only ERCOT ingestion against fixture responses on loopback."""

import asyncio
import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest

from gridmarket_server import ercot, main

FIXTURES = Path(__file__).parent / "fixtures/ercot"
REPORTS = {
    "/api/report/np6-905-cd/spp_node_zone_hub": "np6-905-cd.json",
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices": "np4-190-cd.json",
    "/api/report/np3-565-cd/lf_by_model_weather_zone": "np3-565-cd.json",
    "/api/report/np3-233-cd/hourly_res_outage_cap": "np3-233-cd.json",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const": "np6-86-cd.json",
}
PAYLOADS = {"/api/snapshot": "snapshot.json", **REPORTS}


@contextmanager
def worker(statuses: dict[str, list[int]] | None = None) -> Iterator[tuple[str, list[dict]]]:
    calls: list[dict] = []
    queued = {path: list(values) for path, values in (statuses or {}).items()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            calls.append({"path": self.path, "headers": dict(self.headers), "at": time.monotonic()})
            status = queued.get(path, [200]).pop(0) if queued.get(path) else 200
            if status == 0:
                self.close_connection = True
                return
            payload = json.loads((FIXTURES / PAYLOADS[path]).read_text()) if status == 200 else {}
            body = json.dumps(payload).encode()
            self.send_response(status)
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
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_seit_gm_data_01_ingests_snapshot_and_all_five_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with worker() as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        asyncio.run(ercot.poll())

    assert {urlsplit(call["path"]).path for call in calls} == set(PAYLOADS)
    assert ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON").value == 48.5
    assert ercot.signals.latest("NP4-190-CD", "LZ_HOUSTON").value == 60.75
    for zone, value in (("Coast", 1001), ("North Central", 1003), ("Far West", 1008)):
        assert ercot.signals.latest("NP3-565-CD", zone).value == value
    assert ercot.signals.latest("NP3-233-CD", "LZ_HOUSTON").value == 2310
    assert ercot.signals.latest("NP6-86-CD", "HOUSTON_NORTH_345KV").value == 125.5
    signal = ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON")
    assert signal.interval_minutes == 15
    assert signal.published_at == "2026-09-26T14:05:00Z"
    for report, zone in (
        ("NP6-905-CD", "LZ_HOUSTON"),
        ("NP4-190-CD", "LZ_HOUSTON"),
        ("NP3-565-CD", "Coast"),
        ("NP3-233-CD", "LZ_HOUSTON"),
        ("NP6-86-CD", "HOUSTON_NORTH_345KV"),
    ):
        stored = ercot.signals.latest(report, zone)
        assert stored.interval_start and stored.published_at and stored.fetched_at
    with sqlite3.connect(tmp_path / "signals.db") as db:
        assert {70234, 51.25, 60.75, 36.5} <= {
            row[0] for row in db.execute("SELECT value FROM signals")
        }
        snapshot = db.execute(
            "SELECT published_at, fetched_at FROM signals WHERE value=70234"
        ).fetchone()
    assert snapshot is not None
    assert snapshot[0] == "2026-09-26T14:00:00Z" and snapshot[1]


def test_seit_gm_data_02_sliding_budget_over_180_seconds() -> None:
    clock = [0.0]
    assert callable(getattr(ercot, "RequestBudget", None))
    budget = ercot.RequestBudget(limit=12, window_s=60, clock=lambda: clock[0])
    sent: list[float] = []
    for request in range(100):
        clock[0] = request * 1.8
        if budget.try_acquire():
            sent.append(clock[0])
    assert len(sent) <= 36
    assert all(sum(start <= at < start + 60 for at in sent) <= 12 for start in sent)
    assert budget.try_acquire() is False  # The 13th request in a full window waits.


def test_seit_gm_data_01_weather_zone_load_mapping() -> None:
    report = json.loads((FIXTURES / "np3-565-cd.json").read_text())
    rows = {row[2]: row[3] for row in report["data"]}
    assert callable(getattr(ercot, "map_weather_zone_load", None))
    assert ercot.map_weather_zone_load(rows) == {
        "LZ_HOUSTON": 1001,
        "LZ_NORTH": 3009,
        "LZ_SOUTH": 2011,
        "LZ_WEST": 2015,
    }


def test_seit_gm_data_04_uses_only_worker_key_and_never_fresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "fixture-market-key-do-not-print"
    with worker() as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", secret)
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        asyncio.run(ercot.poll())
    assert calls
    assert all("fresh" not in call["path"] for call in calls)
    for call in calls:
        key = call["headers"].get("x-gridmarket-key")
        assert key == (secret if urlsplit(call["path"]).path in REPORTS else None)
    assert secret not in caplog.text
    assert secret not in repr(ercot.worker_stats())

    async def read() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
        ) as client:
            return await client.get("/v1/signals")

    response = asyncio.run(read())
    assert secret not in response.text and url not in response.text
    source = "\n".join(path.read_text() for path in Path(ercot.__file__).parent.glob("*.py"))
    assert not any(
        name in source for name in ("ERCOT_USERNAME", "ERCOT_PASSWORD", "Ocp-Apim-Subscription-Key")
    )


@pytest.mark.parametrize("status", [0, 401, 404, 429, 500, 502, 503])
def test_seit_gm_data_03_retries_worker_failures(
    status: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with worker({"/api/snapshot": [status, 200]}) as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        asyncio.run(ercot.poll())
    snapshot_calls = [call for call in calls if urlsplit(call["path"]).path == "/api/snapshot"]
    assert len(snapshot_calls) >= 2
    assert snapshot_calls[1]["at"] - snapshot_calls[0]["at"] >= 5
    assert ercot.worker_stats().errors >= 1
    if status == 429:
        assert ercot.worker_stats().http_429 >= 1


def test_seit_gm_data_03_backoff_caps_at_five_minutes() -> None:
    assert callable(getattr(ercot, "backoff_seconds", None))
    assert [ercot.backoff_seconds(attempt) for attempt in (0, 1, 2, 6, 20)] == [
        5,
        10,
        20,
        300,
        300,
    ]


def test_seit_gm_data_03_failed_poll_keeps_stale_signal_api_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(Path(ercot.__file__).with_name("schema.sql").read_text())
        fetched = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        db.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("one", "NP6-905-CD", "LZ_HOUSTON", fetched, 15, 48.5, "$/MWh", fetched, fetched),
        )
    with worker({"/api/snapshot": [503]}) as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
        try:
            asyncio.run(asyncio.wait_for(ercot.poll(), timeout=1))
        except TimeoutError:
            pass  # Waiting for the next retry is allowed.
    assert calls

    async def read() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
        ) as client:
            return await client.get("/v1/signals")

    response = asyncio.run(read())
    assert response.status_code == 200
    assert "48.5" in response.text
    assert '"stale":true' in response.text.replace(" ", "")
    assert "age_s" in response.text


def test_seit_gm_data_01_worker_stats_keep_only_counters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with worker() as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        asyncio.run(ercot.poll())
    stats = ercot.worker_stats()
    assert stats.requests >= len(calls) >= 6
    assert stats.errors >= 0 and stats.http_429 >= 0
    assert stats.latencies_ms and all(latency >= 0 for latency in stats.latencies_ms)
    assert stats.snapshot_age_s is not None and stats.snapshot_age_s >= 0
    assert set(vars(stats)) == {"requests", "errors", "http_429", "latencies_ms", "snapshot_age_s"}


def test_dir_p1a_08_poll_contains_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    monkeypatch.setenv("GRIDMARKET_WORKER_URL", "http://127.0.0.2/")
    asyncio.run(ercot.poll())  # Must not raise: conftest blocks the socket.
