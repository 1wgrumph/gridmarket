"""S28 red tests for payroll, losses, dormancy, and restart (SEIT-GM-ECON-02/03/04)."""

import json
import sqlite3
from pathlib import Path

import pytest

from gridmarket_server import economy, population

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server" / "schema.sql"
MASTER = "20260926"
EPOCH = 1_800_000_000


def _db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    path = tmp_path / "gridmarket.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.execute("INSERT INTO providers (id, display_name) VALUES ('base_sim', 'Base Simulation')")
    conn.commit()
    return path, conn


def _account(conn: sqlite3.Connection, account_id: str, cash_cents: int) -> None:
    conn.execute(
        "INSERT INTO accounts (id, display_name, cash_cents) VALUES (?, ?, ?)",
        (account_id, account_id, cash_cents),
    )


def _bot(
    conn: sqlite3.Connection,
    account_id: str,
    index: int,
    profile: dict,
    dormant: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO bots (
            id, account_id, bot_index, bot_type, provider_id, profile_json, dormant
        ) VALUES (?, ?, ?, ?, 'base_sim', ?, ?)
        """,
        (
            f"bot-{index}",
            account_id,
            index,
            profile.get("bot_type", "saver"),
            json.dumps(profile),
            dormant,
        ),
    )


def test_SEIT_GM_ECON_02_payroll_excludes_pnl(tmp_path: Path, monkeypatch) -> None:
    """Employed bots are paid once per 30 minutes; deposits do not change P&L."""
    path, conn = _db(tmp_path)
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    _account(conn, "acct-emp", 10_000)
    _account(conn, "acct-unemp", 10_000)
    _account(conn, "acct-human", 10_000)
    _account(conn, "acct-sandbox", 10_000)
    _bot(
        conn,
        "acct-emp",
        0,
        {"employed": True, "pay": 40.0, "pay_offset_s": 600, "bot_type": "saver"},
    )
    _bot(
        conn,
        "acct-unemp",
        1,
        {"employed": False, "pay": 40.0, "pay_offset_s": 600, "bot_type": "noise trader"},
    )
    conn.execute(
        "INSERT INTO api_keys (id, account_id, key_hash, label) VALUES ('k-sand', 'acct-sandbox', 'hash', 'sandbox')"
    )
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES ('p1', 'LZ_HOUSTON-H', 'LZ_HOUSTON', '2026-09-26T00:00:00Z')"
    )
    conn.execute("INSERT INTO settlements (id, product_id, price_cents) VALUES ('set-1', 'p1', 50)")
    conn.execute(
        """
        INSERT INTO settled_positions (
            id, settlement_id, account_id, product_id, quantity, pnl_cents
        ) VALUES ('sp-1', 'set-1', 'acct-emp', 'p1', 1, -250)
        """
    )
    conn.commit()

    def deposits(account_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM deposits WHERE account_id = ?", (account_id,)
        ).fetchone()
        return int(row[0])

    def cash(account_id: str) -> int:
        row = conn.execute("SELECT cash_cents FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return int(row[0])

    economy.tick(conn, EPOCH + 599)
    conn.commit()
    assert deposits("acct-emp") == 0
    economy.tick(conn, EPOCH + 600)
    conn.commit()
    assert deposits("acct-emp") == 1
    assert cash("acct-emp") == 14_000
    paid = conn.execute(
        "SELECT amount_cents FROM deposits WHERE account_id = 'acct-emp'"
    ).fetchone()
    assert int(paid[0]) == 4_000
    economy.tick(conn, EPOCH + 1799)
    conn.commit()
    assert deposits("acct-emp") == 1
    economy.tick(conn, EPOCH + 1800 + 600)
    conn.commit()
    assert deposits("acct-emp") == 2
    assert cash("acct-emp") == 18_000
    assert deposits("acct-unemp") == 0
    assert deposits("acct-human") == 0
    assert deposits("acct-sandbox") == 0
    assert cash("acct-unemp") == 10_000
    assert economy.stats("acct-emp")["pnl"] == pytest.approx(-2.5)


def test_SEIT_GM_ECON_03_losses_net_worth_dormancy(tmp_path: Path, monkeypatch) -> None:
    """One loss per negative settlement, no bailout, dormant rate is dormant/all."""
    path, conn = _db(tmp_path)
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    rows = (
        ("acct-dormant", 50, 0, False),
        ("acct-cash", 100, 1, False),
        ("acct-capacity", 50, 2, True),
        ("acct-employed", 0, 3, False),
    )
    for account_id, cash_cents, index, employed in rows:
        _account(conn, account_id, cash_cents)
        _bot(
            conn,
            account_id,
            index,
            {"employed": employed, "pay": 40.0, "pay_offset_s": 0, "bot_type": "saver"},
            dormant=0,
        )
    conn.execute(
        """
        INSERT INTO assets (
            id, account_id, provider_id, zone, capacity_kwh, soc_kwh,
            min_reserve_kwh, charge_kw, discharge_kw
        ) VALUES ('a-cap', 'acct-capacity', 'base_sim', 'LZ_HOUSTON', 10, 5, 1, 2, 2)
        """
    )
    conn.execute(
        """
        INSERT INTO assets (
            id, account_id, provider_id, zone, capacity_kwh, soc_kwh,
            min_reserve_kwh, charge_kw, discharge_kw
        ) VALUES ('a-empty', 'acct-dormant', 'base_sim', 'LZ_HOUSTON', 10, 1, 1, 2, 2)
        """
    )
    _account(conn, "trader", 14_000)
    _account(conn, "other-1", 0)
    _account(conn, "other-2", 0)
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES ('p1', 'LZ_HOUSTON-H', 'LZ_HOUSTON', '2026-09-26T00:00:00Z')"
    )
    conn.execute("INSERT INTO settlements (id, product_id, price_cents) VALUES ('set-1', 'p1', 80)")
    for row_id, pnl in (("sp-neg", -500), ("sp-small", -100), ("sp-zero", 0), ("sp-pos", 400)):
        conn.execute(
            """
            INSERT INTO settled_positions (
                id, settlement_id, account_id, product_id, quantity, pnl_cents
            ) VALUES (?, 'set-1', 'trader', 'p1', 1, ?)
            """,
            (row_id, pnl),
        )
    conn.execute(
        "INSERT INTO deposits (id, account_id, amount_cents, reason) VALUES ('dep-1', 'trader', 4000, 'pay')"
    )
    for order_id, account_id, side, price, created in (
        ("o-open", "trader", "buy", 50, "2026-01-01T00:00:00Z"),
        ("o-open-sell", "other-1", "sell", 50, "2026-01-01T00:00:00Z"),
        ("o-mark-buy", "other-2", "buy", 80, "2026-01-01T01:00:00Z"),
        ("o-mark-sell", "other-1", "sell", 80, "2026-01-01T01:00:00Z"),
    ):
        conn.execute(
            """
            INSERT INTO orders (
                id, account_id, product_id, side, quantity, remaining_qty,
                price_cents, status, created_at
            ) VALUES (?, ?, 'p1', ?, 2, 0, ?, 'filled', ?)
            """,
            (order_id, account_id, side, price, created),
        )
    conn.execute(
        """
        INSERT INTO trades (
            id, product_id, buy_order_id, sell_order_id, quantity, price_cents, created_at
        ) VALUES ('t-open', 'p1', 'o-open', 'o-open-sell', 2, 50, '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO trades (
            id, product_id, buy_order_id, sell_order_id, quantity, price_cents, created_at
        ) VALUES ('t-mark', 'p1', 'o-mark-buy', 'o-mark-sell', 1, 80, '2026-01-01T01:00:00Z')
        """
    )
    conn.execute(
        "INSERT INTO positions (account_id, product_id, quantity) VALUES ('trader', 'p1', 2)"
    )
    conn.commit()
    before = conn.execute("SELECT cash_cents FROM accounts WHERE id = 'acct-dormant'").fetchone()[0]
    economy.tick(conn, EPOCH + 1800)
    conn.commit()
    after = conn.execute("SELECT cash_cents FROM accounts WHERE id = 'acct-dormant'").fetchone()[0]
    assert after == before
    assert economy.stats("acct-dormant")["dormant"] is True
    assert economy.stats("acct-cash")["dormant"] is False
    assert economy.stats("acct-capacity")["dormant"] is False
    assert economy.stats("acct-employed")["dormant"] is False
    report = economy.stats("trader")
    assert report["losses"] == 2
    assert report["loss_share"] == pytest.approx(0.5)
    assert report["worst_loss"] == pytest.approx(-5.0)
    assert report["pnl"] == pytest.approx(-2.0)
    assert report["net_worth"] == pytest.approx(140.60)
    assert callable(getattr(economy, "dormant_rate", None))
    assert economy.dormant_rate(conn) == pytest.approx(0.25)


def test_SEIT_GM_ECON_04_restart_rebuild(tmp_path: Path, monkeypatch) -> None:
    """Restart rebuilds parameters from the master seed and cash from the ledger."""
    path, conn = _db(tmp_path)
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    decoy = tmp_path / "bots-state.json"
    decoy.write_text('{"cash_cents": 1, "dormant": 0}')
    monkeypatch.setenv("GRIDMARKET_STATE_FILE", str(decoy))
    conn.execute("INSERT INTO bot_meta (key, value) VALUES ('master_seed', ?)", (MASTER,))
    _account(conn, "acct-0", 50)
    _bot(conn, "acct-0", 0, {"bot_type": "tampered", "traits": {}}, dormant=0)
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES ('p1', 'LZ_HOUSTON-H', 'LZ_HOUSTON', '2026-09-26T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO positions (account_id, product_id, quantity) VALUES ('acct-0', 'p1', 4)"
    )
    conn.commit()
    assert callable(getattr(economy, "rebuild", None))
    economy.rebuild(conn)
    conn.commit()
    spec = population.sample(MASTER, 0, 1)[0]
    profile = json.loads(
        conn.execute("SELECT profile_json FROM bots WHERE bot_index = 0").fetchone()[0]
    )
    assert profile["bot_type"] == spec.bot_type
    assert profile["traits"] == spec.traits
    assert profile["household"] == spec.household
    assert profile["employed"] == spec.employed
    assert profile["pay"] == spec.pay
    assert profile["pay_offset_s"] == spec.pay_offset_s
    assert profile["provider_id"] == spec.provider_id
    cash = conn.execute("SELECT cash_cents FROM accounts WHERE id = 'acct-0'").fetchone()[0]
    qty = conn.execute("SELECT quantity FROM positions WHERE account_id = 'acct-0'").fetchone()[0]
    assert cash == 50
    assert qty == 4
    expected_dormant = (not spec.employed) and cash < 100
    assert economy.stats("acct-0")["dormant"] is expected_dormant
    assert (
        bool(conn.execute("SELECT dormant FROM bots WHERE bot_index = 0").fetchone()[0])
        is expected_dormant
    )
