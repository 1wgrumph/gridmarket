"""Transactional exchange, pure price/time matcher and delivery settlement."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from . import adversary, health
from .contracts import ProviderOffline
from .providers import commit_capacity as _commit_capacity
from .providers import due_capacity, enabled, reserved_capacity, set_delivery_status

router = APIRouter()
ZONES = ("LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST")
MAX_ORDER_QUANTITY = 50
MAX_POSITION = 200
Order = RestingOrder = dict[str, Any]


def reject(code: str, status: int = 422) -> None:
    raise HTTPException(status, {"code": code, "message": code.replace("_", " ").capitalize()})


def observe_rejection(exc: Exception, account_id: str | None, code: str) -> None:
    # The same exception can cross both the market and HTTP boundaries.
    if not getattr(exc, "adversary_observed", False):
        adversary.observe({"entry_type": "rejection", "account_id": account_id, "code": code})
        exc.adversary_observed = True


@contextmanager
def connection(write: bool = False):
    db = sqlite3.connect(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def rows(db, sql: str, params=()) -> list[dict[str, Any]]:
    cursor = db.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor]


def event(db, kind: str, account: str | None, subject: str, payload: dict) -> None:
    db.execute(
        "INSERT INTO events(id,entry_type,account_id,subject_id,payload_json) VALUES (?,?,?,?,?)",
        (uuid.uuid4().hex, kind, account, subject, json.dumps(payload)),
    )
    adversary.observe({"entry_type": kind, "account_id": account, "subject_id": subject, **payload})


@dataclass(frozen=True)
class Fill:
    resting_order_id: str
    quantity: int
    price_cents: int


@dataclass(frozen=True)
class MatchResult:
    fills: list[Fill]
    remaining_qty: int


class MatchingEngine:
    def match(self, resting: list[RestingOrder], incoming: Order) -> MatchResult:
        buy = incoming["side"] == "buy"
        remaining = incoming["quantity"]
        fills = []
        ordered = sorted(
            resting,
            key=lambda order: (
                order["price_cents"] if buy else -order["price_cents"],
                order.get("sequence", 0),
            ),
        )
        for order in ordered:
            if not remaining:
                break
            if order["side"] == incoming["side"] or order["product_id"] != incoming["product_id"]:
                continue
            price = order["price_cents"]
            if (buy and price > incoming["price_cents"]) or (
                not buy and price < incoming["price_cents"]
            ):
                continue
            quantity = min(remaining, order["remaining_qty"])
            if quantity > 0:
                fills.append(Fill(order["id"], quantity, price))
                remaining -= quantity
        return MatchResult(fills, remaining)


registry = {"python": MatchingEngine()}


def product(db, name: str) -> dict:
    found = rows(db, "SELECT * FROM products WHERE id=? OR symbol=?", (name, name))
    if not found and name.startswith("FLEX-"):
        parts = name.rsplit("-", 1)
        if len(parts[-1]) == 2 and parts[-1].isdigit():
            found = rows(
                db,
                "SELECT * FROM products WHERE zone=? AND symbol LIKE 'FLEX-%' "
                "AND strftime('%H',delivery_hour)=? AND status='open' ORDER BY delivery_hour LIMIT 1",
                (parts[0][5:], parts[-1]),
            )
    if not found:
        reject("UNKNOWN_PRODUCT")
    return found[0]


def list_products(db, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    expired = rows(
        db,
        "SELECT id FROM products WHERE status='open' AND julianday(delivery_hour)<=julianday(?)",
        (now.isoformat(),),
    )
    for item in expired:
        for order in rows(
            db,
            "SELECT id,account_id FROM orders WHERE product_id=? AND status='open'",
            (item["id"],),
        ):
            cancel(db, order["account_id"], order["id"])
        db.execute("UPDATE products SET status='closed' WHERE id=?", (item["id"],))
    for zone in ZONES:
        for offset in range(1, 25):
            delivery = hour + timedelta(hours=offset)
            kind = "SPOT" if offset <= 2 else "FLEX"
            symbol = f"{kind}-{zone}-{delivery:%Y%m%d%H}"
            # Existing futures retain their kind; the approaching hour also gets spot supply.
            if not db.execute(
                "SELECT 1 FROM products WHERE zone=? AND delivery_hour=? AND symbol LIKE ?",
                (zone, delivery.isoformat(), kind + "-%"),
            ).fetchone():
                db.execute(
                    "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES (?,?,?,?)",
                    (symbol, symbol, zone, delivery.isoformat()),
                )


def cash_held(db, account_id: str) -> int:
    return db.execute(
        "SELECT COALESCE(SUM(o.remaining_qty*o.price_cents),0) FROM orders o "
        "JOIN products p ON p.id=o.product_id WHERE o.account_id=? AND o.status='open' "
        "AND (o.side='buy' OR p.symbol LIKE 'FLEX-%')",
        (account_id,),
    ).fetchone()[0]


def _adapters(db, order_id=None):
    return {name: cls(db, order_id) for name, cls in enabled().items()}


def place_order(db, account_id: str, incoming: Order) -> dict:
    try:
        return _place_order(db, account_id, incoming)
    except HTTPException as exc:
        observe_rejection(exc, account_id, exc.detail["code"])
        raise


def _place_order(db, account_id: str, incoming: Order) -> dict:
    if adversary.halted(db, account_id):
        reject("MARKET_HALTED", 423)
    item = product(db, incoming["product_id"])
    if item["status"] != "open" or datetime.fromisoformat(item["delivery_hour"]) <= datetime.now(
        UTC
    ):
        reject("PRODUCT_CLOSED")
    quantity, price, side = incoming["quantity"], incoming["price_cents"], incoming["side"]
    if quantity > MAX_ORDER_QUANTITY:
        reject("ORDER_TOO_LARGE")
    if (
        quantity < 1
        or not 0 <= price <= (2**63 - 1) // MAX_ORDER_QUANTITY
        or side not in ("buy", "sell")
    ):
        reject("VALIDATION_ERROR")
    order_id = uuid.uuid4().hex
    adapters = _adapters(db, order_id)
    assets = [
        (adapter, asset)
        for adapter in adapters.values()
        for asset in adapter.list_assets()
        if asset["account_id"] == account_id
    ]
    if side == "sell":
        for adapter, asset in assets:
            if (
                not health.is_online(adapter.provider_id)
                or not adapter.asset_status(asset["id"])["online"]
            ):
                reject("PROVIDER_OFFLINE")
    position = db.execute(
        "SELECT quantity FROM positions WHERE account_id=? AND product_id=?",
        (account_id, item["id"]),
    ).fetchone()
    current = position[0] if position else 0
    outstanding = db.execute(
        "SELECT COALESCE(SUM(remaining_qty),0) FROM orders WHERE account_id=? AND product_id=? AND side=? AND status='open'",
        (account_id, item["id"], side),
    ).fetchone()[0]
    if abs(current + (1 if side == "buy" else -1) * (quantity + outstanding)) > MAX_POSITION:
        reject("POSITION_LIMIT")
    spot = item["symbol"].startswith("SPOT-")
    if side == "buy" or not spot:
        cash = db.execute("SELECT cash_cents FROM accounts WHERE id=?", (account_id,)).fetchone()[0]
        if price * quantity > cash - cash_held(db, account_id):
            reject("INSUFFICIENT_FUNDS")
    allocations = []
    if side == "sell" and spot:
        remaining = quantity
        for adapter, asset in assets:
            if asset["zone"] != item["zone"]:
                continue
            amount = min(remaining, adapter.available_capacity(asset["id"], item["delivery_hour"]))
            if amount > 0:
                allocations.append((adapter, asset["id"], amount))
                remaining -= amount
        if remaining > 1e-9:
            reject("INSUFFICIENT_CAPACITY")
    db.execute(
        "INSERT INTO orders(id,account_id,product_id,side,quantity,remaining_qty,price_cents,status) VALUES (?,?,?,?,?,?,?,'open')",
        (order_id, account_id, item["id"], side, quantity, quantity, price),
    )
    try:
        for adapter, asset_id, amount in allocations:
            adapter.reserve_capacity(db, asset_id, item["delivery_hour"], amount)
    except ProviderOffline:
        reject("PROVIDER_OFFLINE")
    resting = rows(
        db,
        "SELECT rowid AS sequence,* FROM orders WHERE product_id=? AND side!=? AND status='open' ORDER BY rowid",
        (item["id"], side),
    )
    incoming = {**incoming, "id": order_id, "product_id": item["id"]}
    result = registry["python"].match(resting, incoming)
    for fill in result.fills:
        other = next(order for order in resting if order["id"] == fill.resting_order_id)
        buy_id, sell_id = (order_id, other["id"]) if side == "buy" else (other["id"], order_id)
        buyer, seller = (
            (account_id, other["account_id"])
            if side == "buy"
            else (other["account_id"], account_id)
        )
        trade_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO trades(id,product_id,buy_order_id,sell_order_id,quantity,price_cents) VALUES (?,?,?,?,?,?)",
            (trade_id, item["id"], buy_id, sell_id, fill.quantity, fill.price_cents),
        )
        for account, signed in ((buyer, fill.quantity), (seller, -fill.quantity)):
            db.execute(
                "INSERT INTO positions VALUES (?,?,?) ON CONFLICT(account_id,product_id) DO UPDATE SET quantity=quantity+excluded.quantity",
                (account, item["id"], signed),
            )
        if spot:
            db.execute(
                "UPDATE accounts SET cash_cents=cash_cents-?,flex_credits=flex_credits+? WHERE id=?",
                (fill.quantity * fill.price_cents, fill.quantity, buyer),
            )
            db.execute(
                "UPDATE accounts SET cash_cents=cash_cents+? WHERE id=?",
                (fill.quantity * fill.price_cents, seller),
            )
            _commit_capacity(db, sell_id, fill.quantity)
        for changed in (order_id, other["id"]):
            db.execute(
                "UPDATE orders SET remaining_qty=remaining_qty-?,status=CASE WHEN remaining_qty=? THEN 'filled' ELSE 'open' END WHERE id=?",
                (fill.quantity, fill.quantity, changed),
            )
        for account in {buyer, seller}:
            balance = db.execute(
                "SELECT cash_cents FROM accounts WHERE id=?", (account,)
            ).fetchone()[0]
            event(
                db,
                "fill",
                account,
                trade_id,
                {
                    "product_id": item["id"],
                    "quantity": fill.quantity,
                    "price_cents": fill.price_cents,
                    "cash_cents": balance,
                },
            )
            position = db.execute(
                "SELECT quantity FROM positions WHERE account_id=? AND product_id=?",
                (account, item["id"]),
            ).fetchone()[0]
            if position == 0:
                _record_position(db, item, account, 0, fill.price_cents, spot)
    return rows(db, "SELECT * FROM orders WHERE id=?", (order_id,))[0]


def cancel(db, account_id: str, order_id: str) -> dict:
    found = rows(db, "SELECT * FROM orders WHERE id=? AND account_id=?", (order_id, account_id))
    if not found:
        reject("NOT_FOUND", 404)
    if found[0]["status"] == "open":
        db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
        adapters = _adapters(db)
        for reservation in reserved_capacity(db, order_id):
            adapters[reservation["provider_id"]].release_capacity(db, reservation["id"])
    return rows(db, "SELECT * FROM orders WHERE id=?", (order_id,))[0]


def trade_value(db, account_id: str, product_id: str) -> int:
    return db.execute(
        "SELECT COALESCE(SUM(t.quantity*t.price_cents*((s.account_id=?)-(b.account_id=?))),0) "
        "FROM trades t JOIN orders b ON b.id=t.buy_order_id JOIN orders s ON s.id=t.sell_order_id "
        "WHERE t.product_id=?",
        (account_id, account_id, product_id),
    ).fetchone()[0]


def _record_position(
    db,
    item: dict,
    account: str,
    quantity: int,
    price: int,
    spot: bool,
    settlement_id: str | None = None,
) -> None:
    prior = db.execute(
        "SELECT COALESCE(SUM(pnl_cents),0) FROM settled_positions WHERE account_id=? AND product_id=?",
        (account, item["id"]),
    ).fetchone()[0]
    pnl = trade_value(db, account, item["id"]) + quantity * price - prior
    if settlement_id is None:
        settlement_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO settlements(id,product_id,price_cents) VALUES (?,?,?)",
            (settlement_id, item["id"], price),
        )
    db.execute(
        "INSERT INTO settled_positions(id,settlement_id,account_id,product_id,quantity,pnl_cents) VALUES (?,?,?,?,?,?)",
        (uuid.uuid4().hex, settlement_id, account, item["id"], quantity, pnl),
    )
    if not spot:
        db.execute("UPDATE accounts SET cash_cents=cash_cents+? WHERE id=?", (pnl, account))
    event(db, "settled_position", account, item["id"], {"quantity": quantity, "pnl_cents": pnl})


def settle(db, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    for item in rows(db, "SELECT * FROM products WHERE status!='settled'"):
        hour = datetime.fromisoformat(item["delivery_hour"])
        if hour + timedelta(hours=1) > now:
            continue
        prices = []
        for offset in range(4):
            interval = (hour + timedelta(minutes=15 * offset)).isoformat()
            price = db.execute(
                "SELECT value FROM signals WHERE report_id='NP6-905-CD' AND zone=? AND julianday(interval_start)=julianday(?) AND interval_minutes=15 AND unit='$/MWh' ORDER BY fetched_at DESC,rowid DESC LIMIT 1",
                (item["zone"], interval),
            ).fetchone()
            if price is None:
                break
            prices.append(price[0])
        if len(prices) != 4:
            continue
        reference = round(sum(prices) / 40)
        settlement_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO settlements(id,product_id,price_cents) VALUES (?,?,?)",
            (settlement_id, item["id"], reference),
        )
        spot = item["symbol"].startswith("SPOT-")
        for position in rows(
            db, "SELECT * FROM positions WHERE product_id=? AND quantity!=0", (item["id"],)
        ):
            _record_position(
                db,
                item,
                position["account_id"],
                position["quantity"],
                reference,
                spot,
                settlement_id,
            )
        for order in rows(
            db,
            "SELECT id,account_id FROM orders WHERE product_id=? AND status='open'",
            (item["id"],),
        ):
            cancel(db, order["account_id"], order["id"])
        db.execute("UPDATE positions SET quantity=0 WHERE product_id=?", (item["id"],))
        db.execute("UPDATE products SET status='settled' WHERE id=?", (item["id"],))
        event(db, "settlement", None, item["id"], {"price_cents": reference})
    _deliver(db, now)


def _deliver(db, now: datetime) -> None:
    adapters = _adapters(db)
    for reservation in due_capacity(db, now):
        adapter = adapters.get(reservation["provider_id"])
        delivered = adapter is not None and adapter.verify_delivery(reservation["id"])
        if not delivered:
            fills = rows(
                db,
                "SELECT t.*,b.account_id AS buyer,s.account_id AS seller FROM trades t JOIN orders b ON b.id=t.buy_order_id JOIN orders s ON s.id=t.sell_order_id WHERE t.sell_order_id=?",
                (reservation["order_id"],),
            )
            total = sum(fill["quantity"] for fill in fills)
            for fill in fills:
                refund = round(fill["price_cents"] * fill["quantity"] * reservation["kwh"] / total)
                db.execute(
                    "UPDATE accounts SET cash_cents=cash_cents+? WHERE id=?",
                    (refund, fill["buyer"]),
                )
                db.execute(
                    "UPDATE accounts SET cash_cents=cash_cents-? WHERE id=?",
                    (refund, fill["seller"]),
                )
        if adapter is not None:
            adapter.release_capacity(db, reservation["id"])
        set_delivery_status(db, reservation["id"], delivered)
        event(
            db,
            "settlement",
            None,
            reservation["id"],
            {"delivery": "delivered" if delivered else "defaulted"},
        )


def tick() -> None:
    with connection(write=True) as db:
        list_products(db)
        settle(db)


@router.get("/v1/market/status")
def status() -> dict[str, Any]:
    with connection() as db:
        halted = db.execute(
            "SELECT 1 FROM halts WHERE account_id IS NULL AND ended_at IS NULL"
        ).fetchone()
        anomalies = rows(
            db,
            "SELECT id,kind,subject_id,detail,created_at FROM anomalies "
            "ORDER BY created_at DESC,rowid DESC LIMIT 50",
        )
    return {"status": "halted" if halted else "open", "anomalies": anomalies}


@router.get("/v1/market")
def market_list() -> list[dict]:
    with connection() as db:
        return rows(db, "SELECT * FROM products WHERE status='open' ORDER BY delivery_hour,zone")


@router.get("/v1/market/history")
def history(product_id: str | None = None) -> list[dict]:
    with connection() as db:
        return rows(
            db,
            "SELECT * FROM trades WHERE (? IS NULL OR product_id=?) ORDER BY rowid DESC LIMIT 100",
            (product_id, product_id),
        )


@router.get("/v1/market/activity")
def activity() -> list[dict]:
    with connection() as db:
        return rows(
            db,
            "SELECT e.id,e.entry_type AS type,COALESCE(a.display_name,e.entry_type) AS label,"
            "p.symbol,COALESCE(json_extract(e.payload_json,'$.side'),"
            "CASE WHEN t.id IS NOT NULL THEN CASE WHEN b.account_id=e.account_id "
            "THEN 'buy' ELSE 'sell' END END) AS side,"
            "json_extract(e.payload_json,'$.quantity') AS quantity,"
            "json_extract(e.payload_json,'$.price_cents') AS price_cents,"
            "COALESCE(json_extract(e.payload_json,'$.reason'),"
            "json_extract(e.payload_json,'$.delivery')) AS reason,"
            "e.created_at AS created_at,e.entry_type,e.subject_id FROM events e "
            "LEFT JOIN accounts a ON a.id=e.account_id "
            "LEFT JOIN products p ON p.id=COALESCE("
            "json_extract(e.payload_json,'$.product_id'),e.subject_id) "
            "LEFT JOIN trades t ON e.entry_type='fill' AND t.id=e.subject_id "
            "LEFT JOIN orders b ON b.id=t.buy_order_id UNION ALL "
            "SELECT o.id,'order',a.display_name,p.symbol,o.side,o.quantity,o.price_cents,"
            "NULL,o.created_at,'order',o.product_id FROM orders o "
            "JOIN accounts a ON a.id=o.account_id JOIN products p ON p.id=o.product_id "
            "ORDER BY created_at DESC LIMIT 100",
        )


@router.get("/v1/market/{symbol}")
def detail(symbol: str) -> dict:
    with connection() as db:
        item = product(db, symbol)
        item["orders"] = rows(
            db,
            "SELECT side,price_cents,SUM(remaining_qty) AS quantity FROM orders WHERE product_id=? AND status='open' GROUP BY side,price_cents ORDER BY price_cents",
            (item["id"],),
        )
        return item
