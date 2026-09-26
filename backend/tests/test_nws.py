"""S03: NWS forecast and alert ingestion with an offline loopback server."""

import asyncio
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from gridmarket_server import ercot, main, nws

FIXTURES = Path(__file__).parent / "fixtures/nws"
POINTS = {
    "LZ_HOUSTON": (29.76, -95.37),
    "LZ_NORTH": (32.78, -96.80),
    "LZ_SOUTH": (29.42, -98.49),
    "LZ_WEST": (31.99, -102.08),
}


@pytest.fixture(autouse=True)
def _reset_poller_state() -> Iterator[None]:
    nws._next_zone = 0
    nws._forecasts.clear()
    ercot._last_polled.clear()
    ercot.signals.failed.clear()
    yield
    nws._next_zone = 0
    nws._forecasts.clear()
    ercot._last_polled.clear()
    ercot.signals.failed.clear()


@contextmanager
def weather(statuses: list[int] | None = None) -> Iterator[tuple[str, list[dict]]]:
    calls: list[dict] = []
    queued = list(statuses or [])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            calls.append({"path": self.path, "headers": dict(self.headers)})
            status = queued.pop(0) if queued else 200
            if path.startswith("/points/"):
                name = "point.json"
            elif path.startswith("/gridpoints/"):
                name = "hourly.json"
            elif path == "/alerts/active":
                name = "alerts.json"
            else:
                status, name = 404, "point.json"
            raw = (
                (FIXTURES / name)
                .read_text()
                .replace("__BASE_URL__", f"http://127.0.0.1:{self.server.server_port}")
            )
            body = raw.encode() if status == 200 else b"{}"
            self.send_response(status)
            self.send_header("Content-Type", "application/geo+json")
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


def test_seit_gm_data_05_representative_points_and_forecast_alerts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert getattr(nws, "POINTS", None) == POINTS
    with weather() as (url, calls):
        monkeypatch.setattr(nws, "BASE_URL", url, raising=False)
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        asyncio.run(nws.poll())
    paths = [urlsplit(call["path"]).path for call in calls]
    assert any(path.startswith("/points/29.76,-95.37") for path in paths)
    assert any(path.startswith("/gridpoints/") for path in paths)
    assert "/alerts/active" in paths
    assert all(
        call["headers"].get("User-Agent", "").startswith("gridmarket-hackathon") for call in calls
    )
    assert all(
        "point" in parse_qs(urlsplit(call["path"]).query)
        for call in calls
        if urlsplit(call["path"]).path == "/alerts/active"
    )
    first = ercot.signals.series(
        "NWS-TEMP", "LZ_HOUSTON", "2026-09-26T20:00:00+00:00", "2026-09-26T21:00:00+00:00"
    )
    assert [signal.value for signal in first] == [89]
    assert ercot.signals.latest("NWS-ALERTS", "LZ_HOUSTON").value == 1


def test_seit_gm_data_05_six_request_sliding_budget() -> None:
    clock = [0.0]
    assert callable(getattr(nws, "RequestBudget", None))
    budget = nws.RequestBudget(limit=6, window_s=60, clock=lambda: clock[0])
    sent: list[float] = []
    for request in range(100):
        clock[0] = request * 1.8
        if budget.try_acquire():
            sent.append(clock[0])
    assert all(sum(start <= at < start + 60 for at in sent) <= 6 for start in sent)
    assert len(sent) <= 18
    assert budget.try_acquire() is False


def test_seit_gm_data_05_nws_failure_keeps_stale_weather(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(Path(ercot.__file__).with_name("schema.sql").read_text())
        fetched = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        db.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("temp", "NWS-TEMP", "LZ_HOUSTON", fetched, 60, 91, "F", fetched, fetched),
        )
    with weather([503]) as (url, calls):
        monkeypatch.setattr(nws, "BASE_URL", url, raising=False)
        monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
        try:
            asyncio.run(asyncio.wait_for(nws.poll(), timeout=1))
        except TimeoutError:
            pass
    assert calls

    async def read() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
        ) as client:
            return await client.get("/v1/signals")

    response = asyncio.run(read())
    assert response.status_code == 200
    assert "NWS-TEMP" in response.text
    assert '"stale":true' in response.text.replace(" ", "")
    assert "age_s" in response.text


def test_dir_p1a_08_lifespan_survives_poller_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "app.db"))
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)

    async def boom(*args: object, **kwargs: object) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(nws, "_get", boom)
    with TestClient(main.create_app()) as client:
        time.sleep(1)  # Let the background poller hit the failure before shutdown.
        assert client.get("/v1/market/status").status_code == 200


def test_dir_p1a_12_missing_updated_timestamp_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_get(_client: object, url: str, _budget: object) -> dict:
        if url.startswith("/points/"):
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/X"}}
        if "alerts" in url:
            return {"features": []}
        return {
            "properties": {
                "updateTime": "2026-09-26T14:00:00+00:00",
                "periods": [
                    {
                        "startTime": "2026-09-26T15:00:00+00:00",
                        "temperature": 91,
                        "temperatureUnit": "F",
                    }
                ],
            }
        }

    monkeypatch.setattr(nws, "_get", fake_get)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    asyncio.run(nws.poll())
    latest = ercot.signals.latest("NWS-TEMP", "LZ_HOUSTON")
    assert latest is not None
    assert latest.value == 91
    assert latest.published_at == "2026-09-26T14:00:00+00:00"
