"""S55: ESR battery charging ingestion from the Worker ESR route."""

import asyncio
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from gridmarket_server import ercot

FIXTURES = Path(__file__).parent / "fixtures/ercot"
ESR_PATH = "/api/report/esr/charging_mw"
PAYLOADS = {
    "/api/snapshot": "snapshot.json",
    "/api/report/np6-905-cd/spp_node_zone_hub": "np6-905-cd.json",
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices": "np4-190-cd.json",
    "/api/report/np3-565-cd/lf_by_model_weather_zone": "np3-565-cd.json",
    "/api/report/np3-233-cd/hourly_res_outage_cap": "np3-233-cd.json",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const": "np6-86-cd.json",
}
ESR_FIXTURE = json.loads((Path(__file__).parent / "fixtures/esr_charging.json").read_text())


@contextmanager
def worker(statuses: dict[str, list[int]] | None = None) -> Iterator[tuple[str, list[dict]]]:
    calls: list[dict] = []
    queued = {path: list(values) for path, values in (statuses or {}).items()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            calls.append({"path": self.path, "headers": dict(self.headers)})
            status = queued.get(path, [200]).pop(0) if queued.get(path) else 200
            if path == ESR_PATH and status == 200:
                payload: dict = ESR_FIXTURE
            elif status == 200:
                payload = json.loads((FIXTURES / PAYLOADS[path]).read_text())
            else:
                payload = {}
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


def test_s55_esr_fixture_parses_to_latest_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert ercot.REPORTS["ESR"] == ESR_PATH
    assert ercot.POLL_MINUTES["ESR"] == 5
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    ercot.parse_report("ESR", ESR_FIXTURE)
    signal = ercot.signals.latest("ESR", "ERCOT")
    assert signal is not None
    assert (signal.report_id, signal.zone, signal.unit) == ("ESR", "ERCOT", "MW")
    assert signal.value == -120.75  # Latest interval; negative = discharging.
    assert signal.interval_start == "2026-09-26T14:00:08+00:00"
    assert signal.published_at and signal.fetched_at
    series = ercot.signals.series("ESR", "ERCOT", "2020-01-01", "2030-01-01")
    assert len(series) == 1  # Latest interval only, not one row per 4-second sample.


def test_s55_esr_parses_object_rows_by_field_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    ercot.parse_report(
        "ESR",
        {
            "fields": [
                {"name": "scedTimestamp", "label": "SCED Timestamp", "dataType": "DATETIME"},
                {"name": "chargingMW", "label": "Charging MW", "dataType": "DOUBLE"},
            ],
            "data": [
                {"scedTimestamp": "2026-09-26T14:00:00Z", "chargingMW": 500},
                {"scedTimestamp": "2026-09-26T14:00:04Z", "chargingMW": 510.5},
            ],
            "_meta": {},
        },
    )
    signal = ercot.signals.latest("ESR", "ERCOT")
    assert signal is not None and signal.value == 510.5
    assert signal.interval_start == "2026-09-26T14:00:04+00:00"


def test_s55_esr_poll_failure_marks_failed_without_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    with worker({ESR_PATH: [503] * 7}) as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
        monkeypatch.setenv("GRIDMARKET_ESR", "on")
        try:
            asyncio.run(asyncio.wait_for(ercot.poll(), timeout=5))
        except TimeoutError:
            pass  # Waiting for the next retry is allowed.
    assert calls
    assert ESR_PATH in {urlsplit(call["path"]).path for call in calls}
    assert (str(db_path), "*") in ercot.signals.failed
    assert ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON").value == 48.5


def test_s55_esr_skipped_unless_opted_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with worker() as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "fixture-market-key")
        monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
        monkeypatch.delenv("GRIDMARKET_ESR", raising=False)
        asyncio.run(asyncio.wait_for(ercot.poll(), timeout=30))
    assert ESR_PATH not in {urlsplit(call["path"]).path for call in calls}
    assert ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON").value == 48.5
