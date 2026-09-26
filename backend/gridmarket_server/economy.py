"""Ledger-backed bot payroll, dormancy and account statistics."""

import json
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import population


def _db() -> sqlite3.Connection:
    return sqlite3.connect(Path(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db")))


def _dormant(conn: sqlite3.Connection, account_id: str, employed: bool) -> bool:
    if employed:
        return False
    cash = conn.execute("SELECT cash_cents FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if cash is None:
        return False
    held = conn.execute(
        "SELECT COALESCE(SUM(remaining_qty * price_cents), 0) FROM orders "
        "WHERE account_id = ? AND status = 'open' AND side = 'buy'",
        (account_id,),
    ).fetchone()[0]
    if cash[0] - held >= 100:
        return False
    capacity = conn.execute(
        "SELECT 1 FROM assets WHERE account_id = ? AND soc_kwh > min_reserve_kwh LIMIT 1",
        (account_id,),
    ).fetchone()
    return capacity is None


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
    master = row[0] if row else os.getenv("GRIDMARKET_BOT_MASTER_SEED", "20260926")
    for bot_id, account_id, index in conn.execute(
        "SELECT id, account_id, bot_index FROM bots"
    ).fetchall():
        spec = population.sample(master, index, 1)[0]
        profile = asdict(spec)
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
    fills = conn.execute(
        "SELECT t.created_at, t.id, CASE WHEN b.account_id = ? AND s.account_id = ? THEN 0 "
        "WHEN s.account_id = ? THEN t.quantity * t.price_cents "
        "ELSE -t.quantity * t.price_cents END FROM trades t "
        "JOIN orders b ON b.id = t.buy_order_id JOIN orders s ON s.id = t.sell_order_id "
        "WHERE b.account_id = ? OR s.account_id = ?",
        (account_id, account_id, account_id, account_id, account_id),
    ).fetchall()
    events = [(created, ref, delta) for created, ref, delta in fills]
    events += [
        (created, ref, amount)
        for created, ref, amount in conn.execute(
            "SELECT created_at, id, amount_cents FROM deposits WHERE account_id = ?",
            (account_id,),
        )
    ]
    events.sort(key=lambda event: (event[0], event[1]))
    running = cash_cents - sum(delta for _, _, delta in events)
    history = []
    for created, _, delta in events:
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
        unrealized = 0
        for product_id, qty in conn.execute(
            "SELECT product_id, quantity FROM positions WHERE account_id = ?", (account_id,)
        ):
            if qty == 0:
                continue
            mark = conn.execute(
                "SELECT price_cents FROM trades WHERE product_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (product_id,),
            ).fetchone()
            entry = conn.execute(
                "SELECT SUM(t.quantity * t.price_cents), SUM(t.quantity) FROM trades t "
                "WHERE t.product_id = ? AND EXISTS (SELECT 1 FROM orders o "
                "WHERE (o.id = t.buy_order_id OR o.id = t.sell_order_id) "
                "AND o.account_id = ?)",
                (product_id, account_id),
            ).fetchone()
            if mark and entry[1]:
                unrealized += qty * (mark[0] - entry[0] / entry[1])
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
