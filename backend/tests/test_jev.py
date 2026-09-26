"""SEIT-GM-ROUTER-04: optional Jev calls use only a local HTTP stub."""

import asyncio
import importlib
import json
import sqlite3
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from gridmarket_server.contracts import CheckResult


def check(band: str, number: int = 0) -> CheckResult:
    return CheckResult(
        check_id=f"market-{number}",
        family="market",
        subject="HB_NORTH",
        horizon_s=3600,
        probability={"log": 0.3, "review": 0.6, "alert": 0.9}[band],
        band=band,
        baseline=True,
        jev_probability=None,
        created_at="2026-09-26T12:00:00Z",
        resolves_at="2026-09-26T13:00:00Z",
    )


@pytest.fixture
def stub_jev():
    calls: list[str] = []
    entered = threading.Event()
    release = threading.Event()
    mode = {"status": 200, "timeout": False}

    class Handler(BaseHTTPRequestHandler):
        def respond(self) -> None:
            calls.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            entered.set()
            if mode["timeout"]:
                release.wait()
                return
            body = json.dumps({"probability": 0.73}).encode()
            self.send_response(mode["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = respond
        do_POST = respond

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/jev", calls, entered, release, mode
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def load_jev(monkeypatch: pytest.MonkeyPatch, stub_jev):
    url, *_ = stub_jev

    def load(flag: str | None):
        monkeypatch.setenv("GRIDMARKET_JEV_URL", url)
        monkeypatch.setenv("GRIDMARKET_JEV_KEY", "stub-key")
        if flag is None:
            monkeypatch.delenv("GRIDMARKET_JEV", raising=False)
        else:
            monkeypatch.setenv("GRIDMARKET_JEV", flag)
        jev = importlib.reload(importlib.import_module("gridmarket_server.jev"))
        monkeypatch.setattr(jev, "time", SimpleNamespace(monotonic=lambda: 100.0))
        return jev

    return load


def test_seit_gm_router_04_default_off_no_call(load_jev, stub_jev) -> None:
    jev = load_jev(None)
    assert not jev.enabled()
    assert jev.probability(check("review")) is None
    assert stub_jev[1] == []


def test_seit_gm_router_04_bands_and_market_state(
    load_jev, stub_jev, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    with sqlite3.connect(db_path) as db:
        db.executescript(
            (Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql").read_text()
        )
        db.execute("INSERT INTO accounts (id, display_name) VALUES ('a', 'test')")
        db.commit()
        before = tuple(db.iterdump())
        jev = load_jev("on")
        assert jev.enabled()
        log, review, alert = check("log"), check("review", 1), check("alert", 2)
        assert jev.probability(log) is None
        assert stub_jev[1] == []
        assert jev.probability(review) == pytest.approx(0.73)
        assert jev.probability(alert) == pytest.approx(0.73)
        assert len(stub_jev[1]) == 2
        assert (log.jev_probability, review.jev_probability, alert.jev_probability) == (
            None,
            None,
            None,
        )
        assert (log.probability, review.probability, alert.probability) == (0.3, 0.6, 0.9)
        assert tuple(db.iterdump()) == before


def test_seit_gm_router_04_six_calls_per_minute(load_jev, stub_jev) -> None:
    jev = load_jev("on")
    results = [jev.probability(check("review", i)) for i in range(7)]
    assert results[:6] == pytest.approx([0.73] * 6)
    assert len(stub_jev[1]) <= 6


def test_seit_gm_router_04_http_error_is_empty(load_jev, stub_jev) -> None:
    stub_jev[4]["status"] = 503
    jev = load_jev("on")
    assert jev.probability(check("alert")) is None
    assert len(stub_jev[1]) == 1


def test_seit_gm_router_04_bounded_timeout(load_jev, monkeypatch: pytest.MonkeyPatch) -> None:
    jev = load_jev("on")
    timeouts = []

    def timed_out(request, *, timeout):
        timeouts.append(timeout)
        raise TimeoutError("injected transport timeout")

    monkeypatch.setattr(jev, "urlopen", timed_out)
    assert jev.probability(check("review")) is None
    # DIR-PS-13 permits a shorter budget; do not require ten seconds to elapse.
    assert len(timeouts) == 1
    assert 0 < timeouts[0] <= 10


def test_r4_10_pending_jev_does_not_stall_market(
    load_jev, stub_jev, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gridmarket_server import decision_router, main, market

    _, calls, entered, release, mode = stub_jev
    mode["timeout"] = True
    jev = load_jev("on")
    urlopen = jev.urlopen

    def held_connection(request, *, timeout):
        # R4-10's recorded blackhole scenario, using real loopback HTTP and no
        # response payload. Disable the socket timer only here so a short product
        # timeout cannot masquerade as an independently responsive event loop.
        return urlopen(request, timeout=None)

    monkeypatch.setattr(jev, "urlopen", held_connection)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "market.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    fixed_now = datetime(2026, 9, 26, 10, tzinfo=UTC)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(market, "datetime", FixedDatetime)
    monkeypatch.setattr(decision_router, "now", lambda: fixed_now)
    # Control the registered input, retaining the real tick, Jev client, scheduler
    # and market route. This check resolves three hours after the frozen clock.
    monkeypatch.setattr(decision_router, "registry", {"market": lambda: [check("review")]})
    app = main.create_app()
    ready = Future()

    async def serve():
        stop = asyncio.Event()
        async with app.router.lifespan_context(app):
            ready.set_result((asyncio.get_running_loop(), stop))
            await stop.wait()

    async def request_market():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/v1/market")
            return response, not release.is_set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        serving = executor.submit(asyncio.run, serve())
        loop, stop = ready.result(timeout=5)
        try:
            assert entered.wait(5), "router tick never reached the local Jev endpoint"
            request = asyncio.run_coroutine_threadsafe(request_market(), loop)
            try:
                response, while_pending = request.result(timeout=5)
            except TimeoutError:
                # Watchdog only: release the blocked socket and collect the HTTP
                # response. The assertion below is event ordering, not latency.
                release.set()
                response, while_pending = request.result(timeout=5)
            assert response.status_code == 200
            assert response.json(), "expected the real seeded market products"
            assert len(calls) == 1
            assert while_pending, "/v1/market stalled until the pending Jev call was released"
        finally:
            release.set()
            loop.call_soon_threadsafe(stop.set)
            serving.result(timeout=5)
