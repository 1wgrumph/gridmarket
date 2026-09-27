"""S76 red tests: bounded report queries (R1-03), snapshot freshness (R1-05),
fail-fast fetch without a blocking loop (R1-16)."""

import asyncio
import json
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import s76_spec

from gridmarket_server import ercot

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
POINTS = {"LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST", "HB_HUBAVG"}
NOW = datetime(2026, 9, 26, 14, 0, 10, tzinfo=UTC)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(ercot, "datetime", FrozenDatetime)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    monkeypatch.delenv("GRIDMARKET_ESR", raising=False)
    ercot.stats.snapshot_age_s = None
    ercot._last_polled.clear()
    ercot.signals.failed.clear()
    yield
    ercot._last_polled.clear()
    ercot.signals.failed.clear()


@contextmanager
def worker(statuses: dict[str, list[int]] | None = None) -> Iterator[tuple[str, list[dict]]]:
    calls: list[dict] = []
    queued = {path: list(values) for path, values in (statuses or {}).items()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            calls.append({"path": self.path, "at": time.monotonic()})
            status = queued.get(parts.path, [200]).pop(0) if queued.get(parts.path) else 200
            qs = parse_qs(parts.query)
            payload: dict = {}
            if status == 200:
                payload = handle(parts.path, qs)
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


def handle(path: str, qs: dict[str, list[str]]) -> dict:
    day = (qs.get("deliveryDateFrom") or qs.get("operatingDateFrom") or ["2026-09-26"])[0]
    if path == "/api/snapshot":
        return json.loads(json.dumps(s76_spec.SNAPSHOT))
    if path.endswith("spp_node_zone_hub"):
        point = (qs.get("settlementPoint") or ["LZ_HOUSTON"])[0]
        return s76_spec.np6_905([[day, 10, 1, point, "LZ", 50.0, False]])
    if path.endswith("dam_stlmnt_pnt_prices"):
        point = (qs.get("settlementPoint") or ["LZ_HOUSTON"])[0]
        return s76_spec.np4_190([[day, "10:00", point, 61.0, False]])
    if path.endswith("lf_by_model_weather_zone"):
        return s76_spec.np3_565(
            [
                [
                    f"{day}T08:30:00",
                    day,
                    "10:00",
                    18000,
                    2000,
                    6000,
                    1500,
                    14000,
                    9000,
                    4000,
                    1300,
                    55800,
                    "E",
                    True,
                    False,
                ]
            ]
        )
    if path.endswith("hourly_res_outage_cap"):
        page = int((qs.get("page") or ["1"])[0])
        opday = (qs.get("operatingDateFrom") or ["2026-09-26"])[0]
        if page == 1:
            return s76_spec.np3_233(
                [[f"{opday}T08:05:00", opday, 10, 3000, 4000, 1500, 2310]], total_pages=2
            )
        return s76_spec.np3_233(
            [[f"{opday}T09:05:00", opday, 11, 3100, 4100, 1600, 2410]], total_pages=2
        )
    if path.endswith("shdw_prices_bnd_trns_const"):
        return s76_spec.np6_86([s76_spec.sced_row(f"{day}T09:05:13", "C1", 125.5)])
    raise AssertionError(f"unexpected path {path}")


def queries(calls: list[dict], suffix: str) -> list[dict[str, list[str]]]:
    return [
        parse_qs(urlsplit(call["path"]).query)
        for call in calls
        if urlsplit(call["path"]).path.endswith(suffix)
    ]


# R1-03: every report query is bounded, sorted, and paged by spec parameter names.
def test_s76_r1_03_report_queries_bounded_sorted_paged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with worker() as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "k")
        asyncio.run(ercot.poll())

    for suffix in ("spp_node_zone_hub", "dam_stlmnt_pnt_prices"):
        qs_list = queries(calls, suffix)
        assert qs_list, f"no queries for {suffix}"
        for qs in qs_list:
            assert DATE.match(qs["deliveryDateFrom"][0])
            assert DATE.match(qs["deliveryDateTo"][0])
            assert qs["settlementPoint"][0] in POINTS
            assert qs["size"] and qs["sort"] and qs["page"]

    qs_list = queries(calls, "lf_by_model_weather_zone")
    assert qs_list
    for qs in qs_list:
        assert DATE.match(qs["deliveryDateFrom"][0])
        assert DATE.match(qs["deliveryDateTo"][0])
        assert qs["inUseFlag"][0] == "true"
        assert qs["size"] and qs["sort"] and qs["page"]

    qs_list = queries(calls, "hourly_res_outage_cap")
    assert qs_list
    for qs in qs_list:
        assert "deliveryDateFrom" not in qs  # Spec names it operatingDate.
        assert DATE.match(qs["operatingDateFrom"][0])
        assert DATE.match(qs["operatingDateTo"][0])
        assert qs["size"] and qs["sort"] and qs["page"]
    assert {q["page"][0] for q in qs_list} == {"1", "2"}  # Followed _meta.totalPages.

    qs_list = queries(calls, "shdw_prices_bnd_trns_const")
    assert qs_list
    for qs in qs_list:
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", qs["SCEDTimestampFrom"][0])
        assert qs["size"] and qs["sort"] and qs["page"]

    assert ercot.signals.failed == set()  # Realistic page counts complete the cycle.
    assert ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON").value == 50.0
    assert ercot.signals.latest("NP6-905-CD", "HB_HUBAVG").value == 50.0
    assert ercot.signals.latest("NP4-190-CD", "LZ_NORTH").value == 61.0
    assert ercot.signals.latest("NP3-565-CD", "Coast").value == 18000
    assert ercot.signals.latest("NP3-233-CD", "LZ_HOUSTON").value == 2410  # Page 2, HE11.
    assert ercot.signals.latest("NP6-86-CD", "C1").value == 125.5


# R1-05: snapshot age is recomputed at read time, never frozen at parse time.
def test_s76_r1_05_snapshot_age_recomputed_at_read_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ercot.parse_snapshot(json.loads(json.dumps(s76_spec.SNAPSHOT)))
    assert ercot.worker_stats().snapshot_age_s == pytest.approx(10)

    from datetime import timedelta

    later = NOW + timedelta(minutes=10)

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return later.astimezone(tz) if tz else later.replace(tzinfo=None)

    monkeypatch.setattr(ercot, "datetime", Later)
    assert ercot.worker_stats().snapshot_age_s == pytest.approx(610)


# R1-16: deterministic 4xx fails fast; an exhausted budget raises instead of blocking.
@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_s76_r1_16_client_errors_fail_fast(status: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ercot, "backoff_seconds", lambda attempt: 0)
    path = "/api/report/np6-86-cd/shdw_prices_bnd_trns_const"
    with worker({path: [status] * 7}) as (url, calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        monkeypatch.setenv("GRIDMARKET_WORKER_KEY", "k")
        asyncio.run(ercot.poll())
    attempts = [c for c in calls if urlsplit(c["path"]).path == path]
    assert len(attempts) == 1


def test_s76_r1_16_exhausted_budget_raises_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with worker() as (url, _calls):
        monkeypatch.setenv("GRIDMARKET_WORKER_URL", url)
        budget = ercot.RequestBudget(limit=1, window_s=60)
        assert budget.try_acquire()

        async def fetch() -> dict:
            async with httpx.AsyncClient(base_url=url, timeout=20) as client:
                return await ercot._get(client, "/api/snapshot", budget, "k")

        with pytest.raises(Exception, match="[Bb]udget"):
            asyncio.run(asyncio.wait_for(fetch(), timeout=5))
