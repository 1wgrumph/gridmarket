"""SEIT-GM-ROUTER-04: optional Jev calls use only a local HTTP stub."""

import importlib
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
                release.wait(15)
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
        return importlib.reload(importlib.import_module("gridmarket_server.jev"))

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


def test_seit_gm_router_04_ten_second_timeout(load_jev, stub_jev) -> None:
    stub_jev[4]["timeout"] = True
    jev = load_jev("on")
    start = time.monotonic()
    assert jev.probability(check("review")) is None
    elapsed = time.monotonic() - start
    assert stub_jev[2].is_set()
    assert 9 <= elapsed <= 11.5
