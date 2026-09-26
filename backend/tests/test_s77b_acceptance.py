"""S77b acceptance repair: bots decide with strategies and learning (A2); bot
accounting matches the accepted definitions (A5 cash history, A6 net worth,
A7 dormancy). Red first: each test fails on the S77 exit."""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import bots, economy, market, population, scoring
from gridmarket_server import main as server_main
from gridmarket_server.contracts import Signal

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server" / "schema.sql"
MASTER = "20260926"
EPOCH = 1_800_000_000


def _db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.execute("INSERT INTO providers (id, display_name) VALUES ('base_sim', 'Base')")
    conn.commit()
    return conn


def _signal(report_id: str, value: float, published: str) -> Signal:
    return Signal(report_id, "LZ_HOUSTON", published, 60, value, "index", published, published)


def _profile(bot_type: str, **extra) -> dict:
    base: dict = {
        "bot_type": bot_type,
        "blend": {bot_type: 0.8, "noise trader": 0.1, "saver": 0.1},
        "traits": {"risk appetite": 0.6, "patience": 0.5},
        "household": {"batteries": [13.5], "zone": "LZ_HOUSTON", "reserve_pct": 0.2},
        "info": {"families": ["heat-stress"], "delay_s": 0, "ev_bias": 0.0, "noise": 0.02},
        "employed": True,
        "losses": 0,
        "loss_share": 0.0,
    }
    base.update(extra)
    return base


def _product(symbol: str, hour: str) -> dict:
    return {
        "id": symbol,
        "symbol": symbol,
        "zone": "LZ_HOUSTON",
        "delivery_hour": hour,
        "status": "open",
    }


def test_s77b_permitted_signals_change_decisions() -> None:
    """A2: live report ids map to families; observed heat changes the heat
    seller's quantity; unassigned signals are isolated; DART needs its family."""
    now = datetime(2026, 9, 26, 12, tzinfo=UTC)
    old = (now - timedelta(hours=1)).isoformat()
    older = (now - timedelta(hours=2)).isoformat()
    signals = [
        _signal("NWS-TEMP", 104.0, old),
        _signal("NWS-ALERTS", 2.0, old),
        _signal("NP6-905-CD", 30.0, old),
        _signal("NP4-190-CD", 60.0, older),
    ]
    heat_bot = SimpleNamespace(
        index=3, info={"families": ["heat-stress"], "delay_s": 0, "ev_bias": 0.0, "noise": 0.02}
    )
    observed = bots.observe_signals(heat_bot, signals, now)
    assert set(observed) == {"heat-stress"}
    assert observed["heat-stress"] == pytest.approx(104.0, rel=0.02)
    spread_bot = SimpleNamespace(
        index=4, info={"families": ["price-spread"], "delay_s": 0, "ev_bias": 0.0, "noise": 0.02}
    )
    spread = bots.observe_signals(spread_bot, signals, now)
    assert set(spread) == {"price-spread"}
    assert spread["price-spread"] == pytest.approx(30.0, rel=0.02)
    lagged = SimpleNamespace(
        index=5, info={"families": ["heat-stress"], "delay_s": 900, "ev_bias": 0.0, "noise": 0.02}
    )
    fresh = _signal("NWS-TEMP", 104.0, (now - timedelta(seconds=899)).isoformat())
    assert bots.observe_signals(lagged, [fresh], now) == {}

    products = [_product("SPOT-LZ_HOUSTON-2026092618", "2026-09-26T18:00:00+00:00")]
    row = {"bot_index": 3, "bot_type": "heat seller"}
    profile = _profile("heat seller")
    hot = bots.strategy_order(row, profile, products, [], [], {"heat-stress": 104.0}, 0)
    cold = bots.strategy_order(row, profile, products, [], [], {}, 0)
    assert hot is not None and cold is not None
    assert hot["side"] == cold["side"] == "sell"
    assert hot["product_id"] == cold["product_id"]
    assert hot["quantity"] == cold["quantity"] + 1

    flex = [_product("FLEX-LZ_HOUSTON-2026092618", "2026-09-26T18:00:00+00:00")]
    checks = [
        {"subject": "LZ_HOUSTON:2026-09-26T18:00:00+00:00", "probability": 0.7, "band": "review"}
    ]
    dart_row = {"bot_index": 6, "bot_type": "DART trader"}
    dart_in = _profile("DART trader", info={**profile["info"], "families": ["DART"]})
    dart_out = _profile("DART trader", info={**profile["info"], "families": ["heat-stress"]})
    assert bots.strategy_order(dart_row, dart_in, flex, [], checks, {}, 0) is not None
    assert bots.strategy_order(dart_row, dart_out, flex, [], checks, {}, 0) is None


def test_s77b_settled_results_change_roster_decisions(tmp_path: Path, monkeypatch) -> None:
    """A2: the roster replays ledger thresholds; one settled loss moves them and
    flips a score follower's HIGH decision at fixed confidence."""
    db_path = tmp_path / "s77b-learn.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    conn = _db(db_path)
    conn.execute("INSERT INTO bot_meta VALUES ('master_seed', ?)", (MASTER,))
    spec = population.sample(MASTER, 7, 1)[0]
    assert spec.bot_type == "score follower"
    conn.execute(
        "INSERT INTO accounts (id, display_name, cash_cents) VALUES ('acct-sf', 'sf', 100000)"
    )
    conn.execute(
        "INSERT INTO bots (id, account_id, bot_index, bot_type, provider_id, profile_json)"
        " VALUES ('bot-sf', 'acct-sf', 7, 'score follower', 'base_sim', ?)",
        (json.dumps(asdict(spec)),),
    )
    hour = "2030-01-01T01:00:00+00:00"
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES "
        "('FLEX-LZ_HOUSTON-2030010101', 'FLEX-LZ_HOUSTON-2030010101', 'LZ_HOUSTON', ?)",
        (hour,),
    )
    conn.execute(
        "INSERT INTO settlements (id, product_id, price_cents)"
        " VALUES ('s1', 'FLEX-LZ_HOUSTON-2030010101', 50)"
    )
    conn.commit()

    client = TestClient(server_main.create_app())
    before = next(row for row in client.get("/v1/bots").json() if row["id"] == "bot-sf")
    assert before["thresholds"]["buy"]["value"] == pytest.approx(0.5)
    with sqlite3.connect(db_path) as check:
        assert bots.thresholds_from_ledger(check, MASTER, 7) == before["thresholds"]

    conn.execute(
        "INSERT INTO settled_positions (id, settlement_id, account_id, product_id,"
        " quantity, pnl_cents) VALUES ('sp1', 's1', 'acct-sf', 'FLEX-LZ_HOUSTON-2030010101', 1, -100)"
    )
    conn.commit()
    after = next(row for row in client.get("/v1/bots").json() if row["id"] == "bot-sf")
    assert after["thresholds"]["buy"]["value"] < before["thresholds"]["buy"]["value"]
    conn.close()

    def gate(thresholds: dict) -> float:
        return 0.75 + (0.5 - thresholds["buy"]["value"]) * 0.4

    confidence = (gate(before["thresholds"]) + gate(after["thresholds"])) / 2
    predictions = [
        {
            "zone": "LZ_HOUSTON",
            "delivery_hour": hour,
            "score": 80.0,
            "level": "HIGH",
            "confidence": confidence,
            "expected_value": 0.5,
            "market_price": 0.10,
            "drivers": [],
        }
    ]
    products = [_product("FLEX-LZ_HOUSTON-2030010101", hour)]
    row = {"bot_index": 7, "bot_type": "score follower"}

    def decide(roster_row: dict) -> dict | None:
        profile = dict(
            roster_row,
            blend={"score follower": 0.8, "noise trader": 0.1, "saver": 0.1},
            household={"batteries": [13.5], "zone": "LZ_HOUSTON", "reserve_pct": 0.2},
        )
        return bots.strategy_order(row, profile, products, predictions, [], {}, 0)

    buys = decide(before)
    assert buys is not None and buys["side"] == "buy"
    assert decide(after) is None


def test_s77b_cash_history_uses_actual_ledger_events(tmp_path: Path, monkeypatch) -> None:
    """A5: futures fills hold cash flat, then the deposit and the futures
    settlement move it; every point matches the engine's own cash record."""
    db_path = tmp_path / "s77b-cash.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    conn = _db(db_path)
    for account in ("buyer", "seller"):
        conn.execute(
            "INSERT INTO accounts (id, display_name, cash_cents) VALUES (?, ?, 100000)",
            (account, account),
        )
    delivery = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=3)
    stamp = delivery.strftime("%Y%m%d%H")
    symbol = f"FLEX-LZ_HOUSTON-{stamp}"
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, 'LZ_HOUSTON', ?)",
        (symbol, symbol, delivery.isoformat()),
    )
    conn.commit()
    for qty, price in ((2, 50), (1, 100)):
        with market.connection(write=True) as tx:
            market.place_order(
                tx,
                "seller",
                {"product_id": symbol, "side": "sell", "quantity": qty, "price_cents": price},
            )
            market.place_order(
                tx,
                "buyer",
                {"product_id": symbol, "side": "buy", "quantity": qty, "price_cents": price},
            )
    with market.connection() as tx:
        assert (
            tx.execute("SELECT cash_cents FROM accounts WHERE id='buyer'").fetchone()[0] == 100000
        )
    with market.connection(write=True) as tx:
        tx.execute(
            "INSERT INTO bots (id, account_id, bot_index, bot_type, provider_id, profile_json)"
            " VALUES ('bot-buyer', 'buyer', 0, 'saver', 'base_sim', ?)",
            (json.dumps({"employed": True, "pay": 40.0, "pay_offset_s": 0}),),
        )
        economy.tick(tx, EPOCH + 1800)
    with market.connection(write=True) as tx:
        past = datetime.now(UTC) - timedelta(hours=2)
        hour = past.replace(minute=0, second=0, microsecond=0)
        tx.execute("UPDATE products SET delivery_hour=? WHERE id=?", (hour.isoformat(), symbol))
        for offset in range(4):
            interval = (hour + timedelta(minutes=15 * offset)).isoformat()
            tx.execute(
                "INSERT INTO signals (id, report_id, zone, interval_start, interval_minutes,"
                " value, unit, published_at, fetched_at) VALUES (?, 'NP6-905-CD',"
                " 'LZ_HOUSTON', ?, 15, 30.0, '$/MWh', ?, ?)",
                (f"rt-{offset}", interval, interval, interval),
            )
        market.settle(tx)
    conn.close()

    report = economy.stats("buyer")
    history = report["balance_history"]
    assert [point["balance"] for point in history] == pytest.approx(
        [1000.0, 1000.0, 1040.0, 1038.09]
    )
    assert [point["at"] for point in history] == sorted(point["at"] for point in history)
    with market.connection() as tx:
        recorded = [
            json.loads(row[0])["cash_cents"] / 100
            for row in tx.execute(
                "SELECT payload_json FROM events WHERE entry_type='fill' AND account_id='buyer'"
                " ORDER BY rowid"
            )
        ]
        pnl = tx.execute(
            "SELECT pnl_cents FROM settled_positions WHERE account_id='buyer'"
        ).fetchone()[0]
    assert recorded == [1000.0, 1000.0]
    assert history[0]["balance"] == recorded[0] and history[1]["balance"] == recorded[1]
    assert history[3]["balance"] - history[2]["balance"] == pytest.approx(pnl / 100)


def test_s77b_net_worth_matches_account_on_mixed_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A6: profile net worth equals account cash plus futures-only unrealized on
    one mixed ledger; spot inventory adds nothing; all three mark rules agree."""
    db_path = tmp_path / "s77b-worth.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    conn = _db(db_path)
    for account in ("trader", "seller", "other"):
        conn.execute(
            "INSERT INTO accounts (id, display_name, cash_cents) VALUES (?, ?, 100000)",
            (account, account),
        )
    conn.execute(
        "INSERT INTO api_keys (id, account_id, key_hash, label) VALUES ('k-t', 'trader', ?, 'bot')",
        (hashlib.sha256(b"test-key-t").hexdigest(),),
    )
    spec = population.sample(MASTER, 11, 1)[0]
    conn.execute(
        "INSERT INTO bots (id, account_id, bot_index, bot_type, provider_id, profile_json)"
        " VALUES ('bot-t', 'trader', 11, ?, 'base_sim', ?)",
        (spec.bot_type, json.dumps(asdict(spec))),
    )
    conn.execute(
        "INSERT INTO assets VALUES ('batt', 'seller', 'base_sim', 'LZ_HOUSTON', 20, 20, 2, 5, 5)"
    )
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=3)
    hours = [(base + timedelta(hours=n)).isoformat() for n in range(4)]
    symbols = {
        "spot": f"SPOT-LZ_HOUSTON-{(base).strftime('%Y%m%d%H')}",
        "last": f"FLEX-LZ_HOUSTON-{(base + timedelta(hours=1)).strftime('%Y%m%d%H')}",
        "mid": f"FLEX-LZ_HOUSTON-{(base + timedelta(hours=2)).strftime('%Y%m%d%H')}",
        "ev": f"FLEX-LZ_HOUSTON-{(base + timedelta(hours=3)).strftime('%Y%m%d%H')}",
    }
    for key, hour in zip(("spot", "last", "mid", "ev"), hours, strict=True):
        conn.execute(
            "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, 'LZ_HOUSTON', ?)",
            (symbols[key], symbols[key], hour),
        )
    conn.commit()

    def cross(
        side_first: str,
        first: str,
        side_second: str,
        second: str,
        symbol: str,
        qty: int,
        price: int,
    ) -> None:
        with market.connection(write=True) as tx:
            market.place_order(
                tx,
                first,
                {"product_id": symbol, "side": side_first, "quantity": qty, "price_cents": price},
            )
            market.place_order(
                tx,
                second,
                {"product_id": symbol, "side": side_second, "quantity": qty, "price_cents": price},
            )

    cross("sell", "seller", "buy", "trader", symbols["spot"], 1, 50)
    cross("sell", "seller", "buy", "other", symbols["spot"], 1, 100)
    cross("sell", "seller", "buy", "trader", symbols["last"], 2, 50)
    cross("sell", "other", "buy", "seller", symbols["last"], 1, 80)
    with market.connection(write=True) as tx:
        market.place_order(
            tx,
            "seller",
            {"product_id": symbols["mid"], "side": "sell", "quantity": 1, "price_cents": 100},
        )
        market.place_order(
            tx,
            "other",
            {"product_id": symbols["mid"], "side": "buy", "quantity": 1, "price_cents": 80},
        )
        tx.execute(
            "INSERT INTO positions VALUES ('trader', ?, 2), ('trader', ?, 1)",
            (symbols["mid"], symbols["ev"]),
        )
    conn.close()

    with TestClient(server_main.create_app()) as client:
        account = client.get("/v1/account", headers={"Authorization": "Bearer test-key-t"})
        assert account.status_code == 200
        body = account.json()
        profile = client.get("/v1/bots/bot-t")
        assert profile.status_code == 200
        worth = profile.json()["net_worth"]
    cash = body["cash_cents"] / 100
    assert worth == pytest.approx(cash + body["unrealized_pnl_cents"] / 100)
    expected_value = next(
        item.expected_value
        for item in scoring.predict()
        if item.zone == "LZ_HOUSTON" and item.delivery_hour == hours[3]
    )
    assert body["unrealized_pnl_cents"] == pytest.approx(60 + 180 + round(expected_value * 100))
    assert worth == pytest.approx(cash + (60 + 180 + round(expected_value * 100)) / 100)


def test_s77b_dormancy_uses_canonical_cash_and_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A7: offline or fully reserved batteries dorm; FLEX-sell cash holds count;
    available cash or capacity keeps the bot active."""
    hour = "2030-01-01T01:00:00+00:00"

    def seed(path: Path, online: bool) -> sqlite3.Connection:
        conn = _db(path)
        if not online:
            conn.execute("INSERT INTO provider_health (provider_id, online) VALUES ('base_sim', 0)")
        conn.execute(
            "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES "
            "('S', 'SPOT-LZ_HOUSTON-2030010101', 'LZ_HOUSTON', ?),"
            "('F', 'FLEX-LZ_HOUSTON-2030010101', 'LZ_HOUSTON', ?)",
            (hour, hour),
        )
        return conn

    def bot(conn: sqlite3.Connection, account: str, index: int, cash: int) -> None:
        conn.execute(
            "INSERT INTO accounts (id, display_name, cash_cents) VALUES (?, ?, ?)",
            (account, account, cash),
        )
        conn.execute(
            "INSERT INTO bots (id, account_id, bot_index, bot_type, provider_id, profile_json)"
            " VALUES (?, ?, ?, 'saver', 'base_sim', ?)",
            (f"bot-{account}", account, index, json.dumps({"employed": False})),
        )

    offline_path = tmp_path / "s77b-off.db"
    offline = seed(offline_path, online=False)
    bot(offline, "a-off", 0, 0)
    offline.execute(
        "INSERT INTO assets VALUES ('batt-off', 'a-off', 'base_sim', 'LZ_HOUSTON', 20, 20, 2, 5, 5)"
    )
    offline.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(offline_path))
    economy.tick(offline, EPOCH)
    offline.commit()
    assert economy.stats("a-off")["dormant"] is True
    offline.close()

    online_path = tmp_path / "s77b-on.db"
    online = seed(online_path, online=True)
    bot(online, "b-res", 1, 0)
    online.execute(
        "INSERT INTO assets VALUES ('batt-res', 'b-res', 'base_sim', 'LZ_HOUSTON', 10, 10, 1, 5, 5)"
    )
    online.execute(
        "INSERT INTO orders (id, account_id, product_id, side, quantity, remaining_qty,"
        " price_cents, status) VALUES ('o-res', 'b-res', 'S', 'sell', 1, 1, 100, 'open')"
    )
    online.execute(
        "INSERT INTO reservations VALUES ('r-res', 'o-res', 'batt-res', ?, 9, 'reserved')", (hour,)
    )
    bot(online, "c-hold", 2, 150)
    online.execute(
        "INSERT INTO orders (id, account_id, product_id, side, quantity, remaining_qty,"
        " price_cents, status) VALUES ('o-hold', 'c-hold', 'F', 'sell', 1, 1, 100, 'open')"
    )
    bot(online, "d-ok", 3, 0)
    online.execute(
        "INSERT INTO assets VALUES ('batt-ok', 'd-ok', 'base_sim', 'LZ_HOUSTON', 10, 10, 1, 5, 5)"
    )
    bot(online, "e-cash", 4, 250)
    online.execute(
        "INSERT INTO orders (id, account_id, product_id, side, quantity, remaining_qty,"
        " price_cents, status) VALUES ('o-cash', 'e-cash', 'F', 'sell', 1, 1, 100, 'open')"
    )
    online.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(online_path))
    economy.tick(online, EPOCH)
    online.commit()
    assert economy.stats("b-res")["dormant"] is True
    assert economy.stats("c-hold")["dormant"] is True
    assert economy.stats("d-ok")["dormant"] is False
    assert economy.stats("e-cash")["dormant"] is False
    online.close()
