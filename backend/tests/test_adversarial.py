"""SEIT-GM-ADV-01 / SEIT-GM-ADV-02: adversarial API and kill switch."""

import asyncio
import hashlib
import json
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
USER_KEY = "gm_" + "u" * 32
OTHER_KEY = "gm_" + "v" * 32
ADMIN_KEY = "gm_" + "a" * 32
PRODUCT = "spot-test"


@pytest.fixture
def market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "market.db"
    with sqlite3.connect(db_path) as db:
        db.executescript((ROOT / "backend/gridmarket_server/schema.sql").read_text())
        for account, key, admin in (
            ("adversary", USER_KEY, 0),
            ("other", OTHER_KEY, 0),
            ("owner", ADMIN_KEY, 1),
        ):
            db.execute("INSERT INTO accounts(id, display_name) VALUES (?, ?)", (account, account))
            db.execute(
                "INSERT INTO api_keys(id, account_id, key_hash, label, is_admin) VALUES (?, ?, ?, ?, ?)",
                (account, account, hashlib.sha256(key.encode()).hexdigest(), account, admin),
            )
        db.execute("INSERT INTO providers(id, display_name) VALUES ('base_sim', 'Base simulator')")
        db.execute(
            "INSERT INTO assets VALUES ('battery', 'adversary', 'base_sim', 'NORTH', 13.5, 13.5, 1, 5, 5)"
        )
        hour = (datetime.now(UTC) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        db.execute(
            "INSERT INTO products(id, symbol, zone, delivery_hour) VALUES (?, ?, ?, ?)",
            (PRODUCT, "SPOT-NORTH-TEST", "NORTH", hour.isoformat()),
        )
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setenv("GRIDMARKET_ADV_KEY", USER_KEY)
    monkeypatch.setenv("GRIDMARKET_NWS", "off")

    # Import the S01 module under test inside the fixture, never at collection.
    from gridmarket_server.main import create_app

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.01)
    assert server.started, "test-local server did not start"
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            yield client, db_path
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()


def rows(db_path: Path, sql: str, args: tuple = ()) -> list[tuple]:
    with sqlite3.connect(db_path) as db:
        return db.execute(sql, args).fetchall()


def account_state(db_path: Path, account: str = "adversary") -> tuple:
    return (
        rows(db_path, "SELECT cash_cents, flex_credits FROM accounts WHERE id=?", (account,)),
        rows(db_path, "SELECT id FROM orders WHERE account_id=? ORDER BY id", (account,)),
        rows(
            db_path,
            "SELECT id FROM reservations WHERE order_id IN (SELECT id FROM orders WHERE account_id=?) ORDER BY id",
            (account,),
        ),
        rows(
            db_path,
            "SELECT product_id, quantity FROM positions WHERE account_id=? ORDER BY product_id",
            (account,),
        ),
    )


def order(
    client: httpx.Client, key: str, nonce: str, side: str = "buy", quantity: int = 1
) -> httpx.Response:
    return client.post(
        "/v1/orders",
        headers={"Authorization": f"Bearer {key}", "Idempotency-Key": nonce},
        json={"product_id": PRODUCT, "side": side, "quantity": quantity, "price_cents": 1},
    )


def test_seit_gm_adv_01_over_capacity(market) -> None:
    client, db_path = market
    before = account_state(db_path)
    response = order(client, USER_KEY, "over-capacity", "sell", 20)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_CAPACITY"
    assert account_state(db_path) == before


def test_seit_gm_adv_01_idempotent_replay(market) -> None:
    client, db_path = market
    first = order(client, USER_KEY, "same-order")
    assert first.status_code in (200, 201)
    after_first = account_state(db_path)
    replay = order(client, USER_KEY, "same-order")
    assert replay.status_code in (200, 201)
    assert replay.json()["id"] == first.json()["id"]
    assert account_state(db_path) == after_first
    assert len(after_first[1]) == 1


def test_seit_gm_adv_01_burst_rate_limit(market) -> None:
    client, db_path = market

    async def burst() -> list[httpx.Response]:
        async with httpx.AsyncClient(base_url=client.base_url, timeout=5) as sender:
            return await asyncio.gather(
                *(
                    sender.post(
                        "/v1/orders",
                        headers={
                            "Authorization": f"Bearer {USER_KEY}",
                            "Idempotency-Key": f"burst-{n}",
                        },
                        json={
                            "product_id": PRODUCT,
                            "side": "buy",
                            "quantity": 1,
                            "price_cents": 1,
                        },
                    )
                    for n in range(50)
                )
            )

    start = time.monotonic()
    responses = asyncio.run(burst())
    assert time.monotonic() - start < 1, "burst must contain 50 orders in one second"
    limited = [response for response in responses if response.status_code == 429]
    assert limited
    assert all(response.json()["error"]["code"] == "RATE_LIMITED" for response in limited)
    assert all("Retry-After" in response.headers for response in limited)
    assert len(account_state(db_path)[1]) == sum(
        response.status_code in (200, 201) for response in responses
    )
    assert rows(db_path, "SELECT cash_cents, flex_credits FROM accounts WHERE id='adversary'") == [
        (100000, 0)
    ]


def test_seit_gm_adv_01_scenario_anomalies(market) -> None:
    client, db_path = market
    before = rows(db_path, "SELECT cash_cents, flex_credits FROM accounts WHERE id='adversary'")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gridmarket_server.adversary",
            "--base-url",
            str(client.base_url).rstrip("/"),
            "--key-env",
            "GRIDMARKET_ADV_KEY",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    report = (result.stdout + result.stderr).lower()
    assert result.returncode == 0, report
    assert "capacity" in report and "idempoten" in report and ("429" in report or "rate" in report)
    anomalies = rows(db_path, "SELECT kind, subject_id, detail FROM anomalies")
    assert len(anomalies) >= 3
    details = " ".join(str(field).lower() for row in anomalies for field in row)
    assert (
        "capacity" in details and "idempoten" in details and ("rate" in details or "429" in details)
    )
    status = client.get("/v1/market/status")
    assert status.status_code == 200
    assert len(status.json()["anomalies"]) >= 3
    assert (
        rows(db_path, "SELECT cash_cents, flex_credits FROM accounts WHERE id='adversary'")
        == before
    )


@pytest.mark.parametrize("scope", ["market", "account:adversary"])
def test_seit_gm_adv_02_admin_halt_resume(market, scope: str) -> None:
    client, db_path = market
    body = {"scope": scope, "reason": "test halt"}
    admin = {"Authorization": f"Bearer {ADMIN_KEY}"}
    user = {"Authorization": f"Bearer {USER_KEY}"}
    for path in ("halt", "resume"):
        denied = client.post(f"/v1/admin/{path}", json=body, headers=user)
        assert denied.status_code in (401, 403)
    assert rows(db_path, "SELECT entry_type FROM events") == []
    remote = client.post(
        "/v1/admin/halt", json=body, headers={**admin, "CF-Connecting-IP": "203.0.113.1"}
    )
    assert remote.status_code == 403
    assert rows(db_path, "SELECT entry_type FROM events") == []

    halt = client.post("/v1/admin/halt", json=body, headers=admin)
    assert halt.status_code in (200, 201, 204)
    before = account_state(db_path)
    blocked = order(client, USER_KEY, "blocked-order")
    assert blocked.status_code == 423
    assert blocked.json()["error"]["code"] == "MARKET_HALTED"
    assert account_state(db_path) == before
    if scope == "market":
        assert order(client, OTHER_KEY, "other-blocked").status_code == 423
    else:
        assert order(client, OTHER_KEY, "other-allowed").status_code in (200, 201)

    denied = client.post("/v1/admin/resume", json=body, headers=user)
    assert denied.status_code in (401, 403)
    assert order(client, USER_KEY, "still-blocked").status_code == 423
    resume = client.post("/v1/admin/resume", json=body, headers=admin)
    assert resume.status_code in (200, 201, 204)
    assert order(client, USER_KEY, "after-resume").status_code in (200, 201)
    events = rows(
        db_path,
        "SELECT entry_type, account_id, subject_id, payload_json FROM events WHERE entry_type IN ('halt', 'lift') ORDER BY rowid",
    )
    assert [event[0] for event in events] == ["halt", "lift"]
    assert all((scope.split(":")[-1] in json.dumps(event[1:])) for event in events)
    with sqlite3.connect(db_path) as db, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE events SET entry_type='lift' WHERE entry_type='halt'")
