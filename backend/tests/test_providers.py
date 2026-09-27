"""S10 provider adapter and shared-book checks (SEIT-GM-PROV-01/02)."""

import hashlib
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import health, main, population
from gridmarket_server.providers import enabled


@pytest.fixture
def market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "market.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_LONESTAR", "on")
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        with sqlite3.connect(db_path) as db:
            for provider in ("base_sim", "lonestar"):
                db.execute(
                    "INSERT OR IGNORE INTO providers (id, display_name) VALUES (?, ?)",
                    (provider, provider),
                )
            for account, provider in (("buyer", "base_sim"), ("seller", "lonestar")):
                key = "gm_" + account.ljust(32, "x")
                db.execute(
                    "INSERT INTO accounts (id, display_name) VALUES (?, ?)", (account, account)
                )
                db.execute(
                    "INSERT INTO api_keys (id, account_id, key_hash, label) VALUES (?, ?, ?, ?)",
                    (account, account, hashlib.sha256(key.encode()).hexdigest(), account),
                )
                db.execute(
                    """INSERT INTO assets
                       (id, account_id, provider_id, zone, capacity_kwh, soc_kwh,
                        min_reserve_kwh, charge_kw, discharge_kw)
                       VALUES (?, ?, ?, 'LZ_HOUSTON', 13.5, 13.5, 2, 5, 5)""",
                    (account + "-battery", account, provider),
                )
                db.execute(
                    "INSERT OR REPLACE INTO provider_health "
                    "(provider_id, online, last_heartbeat) VALUES (?, 1, CURRENT_TIMESTAMP)",
                    (provider,),
                )
            delivery = (datetime.now(UTC) + timedelta(hours=1)).replace(
                minute=0, second=0, microsecond=0
            )
            symbol = f"SPOT-LZ_HOUSTON-{delivery:%Y%m%d%H}"
            db.execute("DELETE FROM products WHERE symbol=?", (symbol,))
            db.execute(
                "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, ?, ?)",
                ("spot", symbol, "LZ_HOUSTON", delivery.isoformat()),
            )
        yield client, db_path


def test_seit_gm_prov_01_adapters_conform(market) -> None:
    client, db_path = market
    adapters = {name: cls() for name, cls in enabled().items()}
    assert set(adapters) == {"base_sim", "lonestar"}
    for name, adapter in adapters.items():
        assert adapter.provider_id == name
        assert adapter.display_name
        for method in (
            "list_customers",
            "list_assets",
            "available_capacity",
            "reserve_capacity",
            "release_capacity",
            "verify_delivery",
            "asset_status",
            "heartbeat",
        ):
            assert callable(getattr(adapter, method))
        assert adapter.list_customers(), name
        assets = adapter.list_assets()
        assert assets, name
        with sqlite3.connect(db_path) as db:
            hour = db.execute("SELECT delivery_hour FROM products WHERE id='spot'").fetchone()[0]
        assert adapter.available_capacity(assets[0]["id"], hour) > 0
        assert adapter.asset_status(assets[0]["id"])["online"] is True
    assert client.get("/v1/providers").status_code == 200


def test_seit_gm_prov_01_sell_reserves_through_adapter(market, monkeypatch) -> None:
    client, db_path = market
    adapter = enabled()["lonestar"]
    original = adapter.reserve_capacity
    calls = []

    def record(self, tx, asset_id, hour, kwh):
        calls.append((asset_id, hour, kwh))
        return original(self, tx, asset_id, hour, kwh)

    monkeypatch.setattr(adapter, "reserve_capacity", record)
    response = client.post(
        "/v1/orders",
        headers={
            "Authorization": "Bearer gm_" + "seller".ljust(32, "x"),
            "Idempotency-Key": "provider-reserve",
        },
        json={"product_id": "spot", "side": "sell", "quantity": 1, "price_cents": 100},
    )
    assert response.status_code in (200, 201), response.text
    assert calls and calls[0][0] == "seller-battery" and calls[0][2] >= 1
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


def test_seit_gm_prov_02_lonestar_population_and_public_counts(market) -> None:
    client, db_path = market
    specs = population.sample("s10-seed")
    counts = Counter(spec.provider_id for spec in specs)
    assert counts["lonestar"] >= 20
    assert counts["base_sim"] >= 1
    with sqlite3.connect(db_path) as db:
        seeded = dict(db.execute("SELECT provider_id, COUNT(*) FROM bots GROUP BY provider_id"))
    assert seeded["lonestar"] >= 20
    response = client.get("/v1/providers")
    assert response.status_code == 200
    assert "lonestar" in response.text and "base_sim" in response.text
    # UX-12 includes the non-bot seller who owns a provider asset.
    summary = {row["id"]: row["participants"] for row in response.json()}
    assert summary["lonestar"] == seeded["lonestar"] + 1
    assert summary["base_sim"] == seeded["base_sim"] + 1


def test_seit_gm_prov_02_cross_provider_fill(market) -> None:
    client, db_path = market
    for account, side, price in (("buyer", "buy", 120), ("seller", "sell", 100)):
        response = client.post(
            "/v1/orders",
            headers={
                "Authorization": "Bearer gm_" + account.ljust(32, "x"),
                "Idempotency-Key": f"cross-provider-{account}",
            },
            json={"product_id": "spot", "side": side, "quantity": 1, "price_cents": price},
        )
        assert response.status_code in (200, 201), response.text
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM trades WHERE product_id='spot'").fetchone()[0] == 1


def test_seit_gm_prov_04_offline_sell_changes_no_state(market) -> None:
    client, db_path = market
    stale = (datetime.now(UTC) - timedelta(seconds=31)).isoformat()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "UPDATE provider_health SET last_heartbeat=? WHERE provider_id='lonestar'", (stale,)
        )
        before = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("orders", "reservations", "trades")
        }
        balance = db.execute("SELECT cash_cents FROM accounts WHERE id='seller'").fetchone()[0]
    assert health.is_online("lonestar") is False
    response = client.post(
        "/v1/orders",
        headers={
            "Authorization": "Bearer gm_" + "seller".ljust(32, "x"),
            "Idempotency-Key": "offline-sell",
        },
        json={"product_id": "spot", "side": "sell", "quantity": 1, "price_cents": 100},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROVIDER_OFFLINE"
    with sqlite3.connect(db_path) as db:
        assert before == {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("orders", "reservations", "trades")
        }
        assert (
            db.execute("SELECT cash_cents FROM accounts WHERE id='seller'").fetchone()[0] == balance
        )
    buy = client.post(
        "/v1/orders",
        headers={
            "Authorization": "Bearer gm_" + "buyer".ljust(32, "x"),
            "Idempotency-Key": "offline-provider-buy",
        },
        json={"product_id": "spot", "side": "buy", "quantity": 1, "price_cents": 100},
    )
    assert buy.status_code in (200, 201), buy.text


def test_seit_gm_prov_01_no_direct_capacity_sql() -> None:
    for module in ("market.py", "api.py"):
        source = (Path(main.__file__).parent / module).read_text().lower()
        assert not re.search(r"\b(?:from|join|into|update)\s+(?:assets|reservations)\b", source), (
            module
        )
