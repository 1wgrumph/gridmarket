"""Ledger-backed bot payroll, dormancy and account statistics."""

import json
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import health, market, population
from .providers import enabled


def _db() -> sqlite3.Connection:
    return sqlite3.connect(Path(os.getenv("GRIDMARKET_DB") or "/data/gridmarket.db"))


def _predictions() -> list:
    from . import scoring

    return scoring.predict()


def _has_capacity(conn: sqlite3.Connection, account_id: str) -> bool:
    """True when the account could sell into some listed spot-like product.

    Mirrors the order path: any offline asset blocks every sell, and each
    product sums same-zone adapter capacity net of reservations.
    """
    products = conn.execute(
        "SELECT zone, delivery_hour FROM products WHERE status = 'open' AND symbol NOT LIKE 'FLEX-%'"
    ).fetchall()
    if not products:
        return False
    assets = conn.execute(
        "SELECT id, provider_id, zone FROM assets WHERE account_id = ?", (account_id,)
    ).fetchall()
    if not assets:
        return False
    adapters = {name: cls(conn) for name, cls in enabled().items()}
    for asset_id, provider_id, _zone in assets:
        adapter = adapters.get(provider_id)
        if adapter is None:
            continue
        if not health.is_online(provider_id) or not adapter.asset_status(asset_id)["online"]:
            return False
    for zone, hour in products:
        total = sum(
            adapters[provider_id].available_capacity(asset_id, hour)
            for asset_id, provider_id, asset_zone in assets
            if asset_zone == zone and provider_id in adapters
        )
        if total > 0:
            return True
    return False


def _dormant(conn: sqlite3.Connection, account_id: str, employed: bool) -> bool:
    if employed:
        return False
    cash = conn.execute("SELECT cash_cents FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if cash is None:
        return False
    if cash[0] - market.cash_held(conn, account_id) >= 100:
        return False
    return not _has_capacity(conn, account_id)


def _refresh_dormancy(conn: sqlite3.Connection) -> None:
    for bot_id, account_id, raw in conn.execute(
        "SELECT id, account_id, profile_json FROM bots"
    ).fetchall():
        profile = json.loads(raw)
        conn.execute(
            "UPDATE bots SET dormant = ? WHERE id = ?",
            (int(_dormant(conn, account_id, profile.get("employed", False))), bot_id),
        )


def tick(tx: Any = None, now: Any = None) -> None:
    owned = tx is None
    conn = _db() if owned else tx
    try:
        stamp = int(time.time() if now is None else now)
        for bot_id, account_id, raw in conn.execute(
            "SELECT id, account_id, profile_json FROM bots"
        ).fetchall():
            profile = json.loads(raw)
            if not profile.get("employed"):
                continue
            offset = int(profile.get("pay_offset_s", 0))
            period, elapsed = divmod(stamp, 1800)
            if elapsed < offset:
                continue
            amount = round(float(profile.get("pay", 0)) * 100)
            if amount <= 0:
                continue
            deposit_id = f"pay:{bot_id}:{period}"
            inserted = conn.execute(
                "INSERT OR IGNORE INTO deposits (id, account_id, amount_cents, reason) "
                "VALUES (?, ?, ?, 'pay')",
                (deposit_id, account_id, amount),
            )
            if inserted.rowcount:
                conn.execute(
                    "UPDATE accounts SET cash_cents = cash_cents + ? WHERE id = ?",
                    (amount, account_id),
                )
        _refresh_dormancy(conn)
        if owned:
            conn.commit()
    finally:
        if owned:
            conn.close()


def rebuild(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM bot_meta WHERE key = 'master_seed'").fetchone()
    master = row[0] if row else os.getenv("GRIDMARKET_BOT_MASTER_SEED") or "20260926"
    for bot_id, _account_id, index, raw in conn.execute(
        "SELECT id, account_id, bot_index, profile_json FROM bots"
    ).fetchall():
        cohort = json.loads(raw).get("cohort_seed") if raw else None
        spec = population.sample(master, index, 1, seed=cohort)[0]
        profile = asdict(spec) | {"cohort_seed": cohort}
        conn.execute(
            "UPDATE bots SET bot_type = ?, provider_id = ?, profile_json = ? WHERE id = ?",
            (spec.bot_type, spec.provider_id, json.dumps(profile), bot_id),
        )
    _refresh_dormancy(conn)


def dormant_rate(conn: sqlite3.Connection) -> float:
    dormant, total = conn.execute("SELECT COALESCE(SUM(dormant), 0), COUNT(*) FROM bots").fetchone()
    return dormant / total if total else 0.0


def _balance_history(
    conn: sqlite3.Connection, account_id: str, cash_cents: int
) -> list[dict[str, str | float]]:
    """Cash after each fill, deposit and cash-moving settlement in ledger order.

    Futures fills move no cash at fill; their P&L lands at settlement. Order is
    the stable (created_at, event kind, ledger rowid): same-second fills stay in
    trade order instead of random trade-id order.
    """
    fills = conn.execute(
        "SELECT t.created_at, t.rowid, p.symbol, CASE WHEN b.account_id = ? AND s.account_id = ? THEN 0 "
        "WHEN s.account_id = ? THEN t.quantity * t.price_cents "
        "ELSE -t.quantity * t.price_cents END FROM trades t "
        "JOIN orders b ON b.id = t.buy_order_id JOIN orders s ON s.id = t.sell_order_id "
        "JOIN products p ON p.id = t.product_id "
        "WHERE b.account_id = ? OR s.account_id = ?",
        (account_id, account_id, account_id, account_id, account_id),
    ).fetchall()
    events = [
        (created, 0, rowid, 0 if str(symbol).startswith("FLEX-") else delta)
        for created, rowid, symbol, delta in fills
    ]
    events += [
        (created, 1, rowid, amount)
        for created, rowid, amount in conn.execute(
            "SELECT created_at, rowid, amount_cents FROM deposits WHERE account_id = ?",
            (account_id,),
        )
    ]
    events += [
        (created, 2, rowid, pnl)
        for created, rowid, pnl in conn.execute(
            "SELECT sp.created_at, sp.rowid, sp.pnl_cents FROM settled_positions sp "
            "JOIN products p ON p.id = sp.product_id "
            "WHERE sp.account_id = ? AND p.symbol NOT LIKE 'SPOT-%'",
            (account_id,),
        )
    ]
    events.sort(key=lambda event: (event[0], event[1], event[2]))
    running = cash_cents - sum(delta for _, _, _, delta in events)
    history = []
    for created, _, _, delta in events:
        running += delta
        history.append({"at": created, "balance": running / 100})
    return history


def stats(
    account_id: str,
) -> dict[str, float | bool | int | list[float] | list[dict[str, str | float]]]:
    with _db() as conn:
        account = conn.execute(
            "SELECT cash_cents FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if account is None:
            raise KeyError(account_id)
        cash = account[0] / 100
        settled = [
            row[0]
            for row in conn.execute(
                "SELECT pnl_cents FROM settled_positions WHERE account_id = ?", (account_id,)
            )
        ]
        losses = [value for value in settled if value < 0]
        trade_count = conn.execute(
            "SELECT COUNT(DISTINCT t.id) FROM trades t "
            "JOIN orders b ON b.id = t.buy_order_id "
            "JOIN orders s ON s.id = t.sell_order_id "
            "WHERE b.account_id = ? OR s.account_id = ?",
            (account_id, account_id),
        ).fetchone()[0]
        # Net worth = cash + unsettled flat futures P&L (owed, paid once at expiry)
        # + open futures marked to reference + no spot inventory revaluation.
        # Marks follow the account endpoint: last trade, else book mid, else
        # the prediction's expected value.
        unrealized = 0
        for product_id, qty, zone, hour in conn.execute(
            "SELECT p.product_id, p.quantity, x.zone, x.delivery_hour FROM positions p "
            "JOIN products x ON x.id = p.product_id WHERE p.account_id = ? "
            "AND x.status != 'settled' AND x.symbol NOT LIKE 'SPOT-%'",
            (account_id,),
        ):
            if qty == 0:
                price = 0
            else:
                mark = conn.execute(
                    "SELECT price_cents FROM trades WHERE product_id = ? ORDER BY rowid DESC LIMIT 1",
                    (product_id,),
                ).fetchone()
                if mark:
                    price = mark[0]
                else:
                    book = conn.execute(
                        "SELECT MAX(CASE WHEN side = 'buy' THEN price_cents END),"
                        "MIN(CASE WHEN side = 'sell' THEN price_cents END) FROM orders "
                        "WHERE product_id = ? AND status = 'open'",
                        (product_id,),
                    ).fetchone()
                    if all(value is not None for value in book):
                        price = sum(book) / 2
                    else:
                        prediction = next(
                            (
                                item
                                for item in _predictions()
                                if item.zone == zone and item.delivery_hour == hour
                            ),
                            None,
                        )
                        if prediction is None:
                            continue
                        price = prediction.expected_value * 100
            unrealized += round(market.trade_value(conn, account_id, product_id) + qty * price)
        deposited = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM deposits WHERE account_id = ?",
            (account_id,),
        ).fetchone()[0]
        bot = conn.execute(
            "SELECT dormant FROM bots WHERE account_id = ?", (account_id,)
        ).fetchone()
        return {
            "cash": cash,
            "balance": [(account[0] - deposited) / 100, cash],
            "balance_history": _balance_history(conn, account_id, account[0]),
            "trades": trade_count,
            "losses": len(losses),
            "loss_share": len(losses) / len(settled) if settled else 0.0,
            "worst_loss": min(losses, default=0) / 100,
            "pnl": sum(settled) / 100,
            "net_worth": cash + unrealized / 100,
            "dormant": bool(bot[0]) if bot else False,
        }
