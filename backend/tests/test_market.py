"""S02 market behavior against the real SQLite schema and HTTP order path."""

import asyncio
import hashlib
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from gridmarket_server import main, market, population, seed
from gridmarket_server.providers import enabled

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql"
HOUR = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=5)
SPOT_HOUR = HOUR - timedelta(hours=3)


def api_key(account: str) -> str:
    return "gm_" + hashlib.sha256(account.encode()).hexdigest()[:32]


@pytest.fixture
def exchange(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "market.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        for name in ("buyer", "seller", "second_seller"):
            db.execute("INSERT INTO accounts(id,display_name) VALUES (?,?)", (name, name))
            db.execute(
                "INSERT INTO api_keys(id,account_id,key_hash,label) VALUES (?,?,?,?)",
                (name, name, hashlib.sha256(api_key(name).encode()).hexdigest(), name),
            )
        db.execute("INSERT INTO providers VALUES ('base_sim','Base Simulation',1)")
        db.execute("INSERT INTO provider_health(provider_id,online) VALUES ('base_sim',1)")
        for name in ("seller", "second_seller"):
            db.execute(
                "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?)",
                (f"asset_{name}", name, "base_sim", "LZ_HOUSTON", 13.5, 13.5, 2.7, 5, 5),
            )
        for product, symbol, hour in (
            ("future", "FLEX-LZ_HOUSTON-test", HOUR),
            ("spot", "SPOT-LZ_HOUSTON-test", SPOT_HOUR),
        ):
            db.execute(
                "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES (?,?,?,?)",
                (product, symbol, "LZ_HOUSTON", hour.isoformat()),
            )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    app = main.create_app()
    app.state.providers = enabled()
    with TestClient(app) as client:
        yield path, client


def place(
    client: TestClient, account: str, product: str, side: str, quantity: int, price: int, key: str
):
    return client.post(
        "/v1/orders",
        headers={"Authorization": f"Bearer {api_key(account)}", "Idempotency-Key": key},
        json={"product_id": product, "side": side, "quantity": quantity, "price_cents": price},
    )


def count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seit_gm_acct_01_seed_uses_population_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "seed.db"
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s02-seed")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s02-local-test-secret")
    specs = population.sample("s02-seed")
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        seed.seed(db)
        accounts = db.execute("SELECT id,cash_cents,flex_credits FROM accounts").fetchall()
        bots = db.execute("SELECT account_id,bot_index,provider_id FROM bots").fetchall()
        assert len(accounts) == len(bots) == len(specs)
        by_account = {account_id: (cash, credits) for account_id, cash, credits in accounts}
        for account_id, index, provider_id in bots:
            spec = next(spec for spec in specs if spec.index == index)
            assert by_account[account_id] == (round(spec.start_cash * 100), 0)
            assert provider_id == spec.provider_id
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM api_keys WHERE account_id=?", (account_id,)
                ).fetchone()[0]
                == 1
            )
            assets = db.execute(
                "SELECT provider_id,zone,capacity_kwh,soc_kwh,min_reserve_kwh,charge_kw,discharge_kw "
                "FROM assets WHERE account_id=?",
                (account_id,),
            ).fetchall()
            assert len(assets) == len(spec.household["batteries"])
            for asset, capacity in zip(assets, spec.household["batteries"], strict=True):
                assert asset[0:3] == (spec.provider_id, spec.household["zone"], capacity)
                assert 0 <= asset[4] <= asset[3] <= capacity
                assert 2 <= asset[5] <= 10 and 2 <= asset[6] <= 10
        seed.seed(db)
        assert db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == len(specs)


def test_seit_gm_mkt_01_lists_spot_and_future_for_four_zones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "products.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        seed.seed(db)
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    response = TestClient(main.create_app()).get("/v1/market")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 4 * 24
    assert len({product["zone"] for product in products}) == 4
    for zone in {product["zone"] for product in products}:
        zone_products = [product for product in products if product["zone"] == zone]
        assert sum(product["symbol"].startswith("SPOT-") for product in zone_products) == 2
        assert sum(product["symbol"].startswith("FLEX-") for product in zone_products) == 22


def test_seit_gm_mkt_01_unknown_and_closed_products_are_typed(exchange):
    path, client = exchange
    response = place(client, "buyer", "missing", "buy", 1, 20, "missing-product")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_PRODUCT"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE products SET status='closed' WHERE id='future'")
        db.commit()
    response = place(client, "buyer", "future", "buy", 1, 20, "closed-product")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRODUCT_CLOSED"
    assert count(path, "orders") == 0


def test_seit_gm_mkt_02_price_time_priority_and_append_only_ledger(exchange):
    path, client = exchange
    for account, price, key in (
        ("seller", 20, "first"),
        ("second_seller", 19, "best"),
        ("second_seller", 20, "last"),
    ):
        assert place(client, account, "future", "sell", 2, price, key).status_code < 300
    response = place(client, "buyer", "future", "buy", 5, 21, "take")
    assert response.status_code < 300
    with sqlite3.connect(path) as db:
        fills = db.execute(
            "SELECT t.price_cents,t.quantity,o.account_id FROM trades t "
            "JOIN orders o ON o.id=t.sell_order_id ORDER BY t.rowid"
        ).fetchall()
        assert fills == [(19, 2, "second_seller"), (20, 2, "seller"), (20, 1, "second_seller")]
        assert db.execute("SELECT COUNT(DISTINCT id) FROM trades").fetchone()[0] == 3
        for sql in ("UPDATE trades SET quantity=quantity", "DELETE FROM trades"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                db.execute(sql)


def test_seit_gm_mkt_03_capacity_rejects_and_reserves_atomically(exchange):
    path, client = exchange
    rejected = place(client, "seller", "spot", "sell", 11, 20, "too-much")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "INSUFFICIENT_CAPACITY"
    assert count(path, "orders") == count(path, "reservations") == 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(
            pool.map(
                lambda i: place(client, "seller", "spot", "sell", 1, 20, f"race-{i}"),
                range(20),
            )
        )
    assert all(response.status_code in (200, 201, 422) for response in responses)
    assert any(response.status_code < 300 for response in responses)
    with sqlite3.connect(path) as db:
        reserved = db.execute(
            "SELECT COALESCE(SUM(kwh),0) FROM reservations WHERE asset_id='asset_seller' "
            "AND status!='released'"
        ).fetchone()[0]
        assert 0 < reserved <= 10.8
        assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == sum(
            response.status_code < 300 for response in responses
        )


def test_seit_gm_mkt_04_size_position_and_cash_holds_leave_balances_unchanged(exchange):
    path, client = exchange
    with sqlite3.connect(path) as db:
        db.execute("UPDATE accounts SET cash_cents=40000 WHERE id='buyer'")
    assert place(client, "buyer", "future", "buy", 50, 400, "hold").status_code < 300
    with sqlite3.connect(path) as db:
        before = db.execute(
            "SELECT cash_cents,flex_credits FROM accounts WHERE id='buyer'"
        ).fetchone()
    cases = ((51, 1, "ORDER_TOO_LARGE"), (50, 500, "INSUFFICIENT_FUNDS"))
    for quantity, price, code in cases:
        response = place(client, "buyer", "future", "buy", quantity, price, code)
        assert response.status_code == 422 and response.json()["error"]["code"] == code
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO positions VALUES ('buyer','spot',200)")
        db.commit()
    assert place(client, "seller", "spot", "sell", 1, 20, "cross-position").status_code < 300
    response = place(client, "buyer", "spot", "buy", 1, 20, "position-limit")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "POSITION_LIMIT"
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT cash_cents,flex_credits FROM accounts WHERE id='buyer'").fetchone()
            == before
        )
        assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2


def test_seit_gm_mkt_04_future_sells_also_hold_cash(exchange):
    path, client = exchange
    with sqlite3.connect(path) as db:
        db.execute("UPDATE accounts SET cash_cents=40000 WHERE id='seller'")
    assert place(client, "seller", "future", "sell", 50, 400, "short-hold").status_code < 300
    before = count(path, "orders")
    response = place(client, "seller", "future", "sell", 50, 500, "short-over")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_FUNDS"
    assert count(path, "orders") == before


def test_seit_gm_mkt_05_four_intervals_settle_once_and_record_positions(exchange):
    path, _ = exchange
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO positions VALUES ('buyer','future',10)")
        db.execute("INSERT INTO positions VALUES ('seller','future',-10)")
        db.execute(
            "INSERT INTO orders(id,account_id,product_id,side,quantity,remaining_qty,price_cents,status) "
            "VALUES ('buy','buyer','future','buy',10,0,20,'filled')"
        )
        db.execute(
            "INSERT INTO orders(id,account_id,product_id,side,quantity,remaining_qty,price_cents,status) "
            "VALUES ('sell','seller','future','sell',10,0,20,'filled')"
        )
        db.execute(
            "INSERT INTO trades(id,product_id,buy_order_id,sell_order_id,quantity,price_cents) "
            "VALUES ('fill','future','buy','sell',10,20)"
        )
        for index, value in enumerate((200, 220, 240)):
            db.execute(
                "INSERT INTO signals(id,report_id,zone,interval_start,interval_minutes,value,unit,published_at,fetched_at) "
                "VALUES (?,?,?,?,15,?,'$/MWh',?,?)",
                (
                    f"s{index}",
                    "NP6-905-CD",
                    "LZ_HOUSTON",
                    (HOUR + timedelta(minutes=15 * index)).isoformat(),
                    value,
                    HOUR.isoformat(),
                    HOUR.isoformat(),
                ),
            )
        db.commit()
        market.settle(db, HOUR + timedelta(hours=1))
        assert db.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 0
        db.execute(
            "INSERT INTO signals(id,report_id,zone,interval_start,interval_minutes,value,unit,published_at,fetched_at) "
            "VALUES ('s3','NP6-905-CD','LZ_HOUSTON',?,15,260,'$/MWh',?,?)",
            ((HOUR + timedelta(minutes=45)).isoformat(), HOUR.isoformat(), HOUR.isoformat()),
        )
        market.settle(db, HOUR + timedelta(hours=1))
        market.settle(db, HOUR + timedelta(hours=1))
        assert db.execute("SELECT price_cents FROM settlements").fetchall() == [(23,)]
        assert set(db.execute("SELECT account_id,quantity,pnl_cents FROM settled_positions")) == {
            ("buyer", 10, 30),
            ("seller", -10, -30),
        }
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE settled_positions SET pnl_cents=pnl_cents")
        assert dict(db.execute("SELECT id,cash_cents FROM accounts")) == {
            "buyer": 100030,
            "seller": 99970,
            "second_seller": 100000,
        }


def test_seit_gm_mkt_06_spot_fill_moves_cash_and_credits_only_on_fill(exchange):
    path, client = exchange
    assert place(client, "buyer", "spot", "buy", 3, 20, "resting").status_code < 300
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT cash_cents,flex_credits FROM accounts WHERE id='buyer'"
        ).fetchone() == (100000, 0)
    assert place(client, "seller", "spot", "sell", 3, 20, "fill").status_code < 300
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT cash_cents,flex_credits FROM accounts WHERE id='buyer'"
        ).fetchone() == (99940, 3)
        assert (
            db.execute("SELECT cash_cents FROM accounts WHERE id='seller'").fetchone()[0] == 100060
        )
        assert db.execute("SELECT quantity,price_cents FROM trades").fetchall() == [(3, 20)]


def test_seit_gm_prov_04_offline_seller_rejected_but_buyer_allowed(exchange):
    path, client = exchange
    with sqlite3.connect(path) as db:
        db.execute("UPDATE provider_health SET online=0 WHERE provider_id='base_sim'")
        db.commit()
    before = (count(path, "orders"), count(path, "reservations"))
    response = place(client, "seller", "spot", "sell", 1, 20, "offline")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROVIDER_OFFLINE"
    assert (count(path, "orders"), count(path, "reservations")) == before
    assert place(client, "buyer", "spot", "buy", 1, 20, "offline-buy").status_code < 300
    with sqlite3.connect(path) as db:
        db.execute("UPDATE provider_health SET online=1 WHERE provider_id='base_sim'")
        db.commit()
    assert place(client, "seller", "spot", "sell", 1, 20, "online").status_code < 300


def test_s05_anom_status_returns_newest_50_rows(exchange):
    path, client = exchange
    response = client.get("/v1/market/status")
    assert response.status_code == 200
    assert response.json() == {
        "status": "open",
        "anomalies": [],
        "open_interest": 0,
        "active_traders": 0,
    }
    anomalies = [
        {
            "id": f"anomaly-{i}",
            "kind": "order_burst",
            "subject_id": "buyer" if i < 54 else None,
            "detail": f"Burst {i}" if i < 54 else None,
            "created_at": (HOUR + timedelta(seconds=i // 2)).isoformat(),
        }
        for i in range(55)
    ]
    with sqlite3.connect(path) as db:
        # Insert out of timestamp order, including ties at the 50-row boundary.
        db.executemany(
            "INSERT INTO anomalies(id,kind,subject_id,detail,created_at) "
            "VALUES (:id,:kind,:subject_id,:detail,:created_at)",
            reversed(anomalies),
        )
    response = client.get("/v1/market/status")
    assert response.status_code == 200
    assert response.json() == {
        "status": "open",
        "anomalies": sorted(anomalies, key=lambda row: row["created_at"], reverse=True)[:50],
        "open_interest": 0,
        "active_traders": 0,
    }


def test_s05_anom_live_burst_finishes_under_half_second_without_lost_orders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "burst.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s05-anom")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s05-local-test-secret")
    server = uvicorn.Server(
        uvicorn.Config(main.create_app(), host="127.0.0.1", port=0, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started, "loopback uvicorn did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO accounts(id,display_name) VALUES ('burst','Burst')")
            db.execute(
                "INSERT INTO api_keys(id,account_id,key_hash,label) VALUES (?,?,?,?)",
                ("burst", "burst", hashlib.sha256(api_key("burst").encode()).hexdigest(), "Burst"),
            )

        async def burst():
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
            ) as client:
                response = await client.get("/v1/market")
                assert response.status_code == 200
                product = next(p["id"] for p in response.json() if p["symbol"].startswith("FLEX-"))
                start = time.perf_counter()
                responses = await asyncio.gather(
                    *(
                        client.post(
                            "/v1/orders",
                            headers={
                                "Authorization": f"Bearer {api_key('burst')}",
                                "Idempotency-Key": str(i),
                            },
                            json={
                                "product_id": product,
                                "side": "buy",
                                "quantity": 1,
                                "price_cents": 1,
                            },
                        )
                        for i in range(50)
                    )
                )
                return responses, time.perf_counter() - start

        responses, elapsed = asyncio.run(burst())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert len(responses) == 50
    assert all(response.status_code in (200, 429) for response in responses)
    accepted = {response.json()["id"] for response in responses if response.status_code == 200}
    assert len(accepted) >= 40
    limited = [response for response in responses if response.status_code == 429]
    assert limited
    for response in limited:
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response.headers["Retry-After"]) >= 1
    # Reopen after server shutdown: every acknowledged order and retry record survived.
    with sqlite3.connect(path) as db:
        assert {row[0] for row in db.execute("SELECT id FROM orders")} == accepted
        assert db.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == len(accepted)
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert elapsed < 1.0, f"50-order burst took {elapsed:.3f}s"
