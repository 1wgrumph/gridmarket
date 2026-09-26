"""S63-T red tests: UX-01 (bots list economy) and UX-12 (exchange summaries).

GET /v1/bots omits the economy columns the dashboard needs (Home renders
$NaN, the Bots list renders dashes), and no exchange endpoint serves open
interest, active traders or per-provider participants. All fixtures use fixed
data; no wall-clock assertions.
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import main

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql"


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "s63.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        db.execute("INSERT INTO accounts(id,display_name) VALUES ('member','member')")
        db.execute("INSERT INTO accounts(id,display_name) VALUES ('member2','member2')")
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES "
            "('future','FLEX-LZ_HOUSTON-test','LZ_HOUSTON','2099-01-01T18:00:00+00:00')"
        )
        db.execute("INSERT INTO providers VALUES ('base_sim','Base Simulation',1)")
        db.execute(
            "INSERT INTO assets VALUES "
            "('member_asset','member','base_sim','LZ_HOUSTON',13.5,13.5,2.7,5,5)"
        )
        db.execute(
            "INSERT INTO assets VALUES "
            "('member2_asset','member2','base_sim','LZ_HOUSTON',13.5,13.5,2.7,5,5)"
        )
        db.execute(
            "INSERT INTO orders(id,account_id,product_id,side,quantity,remaining_qty,"
            "price_cents,status) VALUES "
            "('buy1','member','future','buy',2,2,20,'open'),"
            "('sell1','member2','future','sell',2,1,20,'open')"
        )
        db.execute(
            "INSERT INTO trades(id,product_id,buy_order_id,sell_order_id,quantity,"
            "price_cents) VALUES ('trade1','future','buy1','sell1',1,20)"
        )
        db.execute(
            "INSERT INTO positions(account_id,product_id,quantity) VALUES "
            "('member','future',1),('member2','future',-1)"
        )
        db.execute(
            "INSERT INTO bots(id,account_id,bot_index,bot_type,provider_id,profile_json)"
            " VALUES ('bot_0','member',0,'maker','base_sim','{}')"
        )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s63-seed")
    with TestClient(main.create_app()) as client:
        yield client


def test_ux01_bots_list_serves_economy(api: TestClient) -> None:
    """UX-01: every /v1/bots row carries the economy Home and Bots render."""
    response = api.get("/v1/bots")
    assert response.status_code == 200
    rows = response.json()
    assert rows, "expected the seeded bot in the list"
    for row in rows:
        for field in ("cash", "net_worth", "pnl"):
            assert row.get(field) is not None, f"{row['id']} lacks {field}"


def test_ux12_status_serves_exchange_summary(api: TestClient) -> None:
    """UX-12: the exchange summary reports open interest and active traders."""
    response = api.get("/v1/market/status")
    assert response.status_code == 200
    body = response.json()
    assert body.get("open_interest") is not None, "open interest is not served"
    assert body.get("active_traders") is not None, "active traders are not served"
    assert isinstance(body["open_interest"], int) and body["open_interest"] >= 0
    assert isinstance(body["active_traders"], int) and body["active_traders"] >= 0


def test_ux12_providers_serve_participants(api: TestClient) -> None:
    """UX-12: every provider row carries its participant count."""
    response = api.get("/v1/providers")
    assert response.status_code == 200
    rows = response.json()
    assert rows, "expected the seeded provider in the list"
    for row in rows:
        assert row.get("participants") is not None, f"{row['id']} lacks participants"
        assert isinstance(row["participants"], int) and row["participants"] >= 0
