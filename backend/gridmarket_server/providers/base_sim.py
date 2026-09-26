"""SQLite-backed simulated battery fleet; reservations use the caller's transaction."""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .. import health
from ..contracts import ProviderOffline


class BaseSim:
    provider_id = "base_sim"
    display_name = "Base Simulation"

    def __init__(self, tx: sqlite3.Connection | None = None, order_id: str | None = None):
        self.tx = tx
        self.order_id = order_id

    @contextmanager
    def _read(self):
        from ..market import connection

        if self.tx is not None:
            yield self.tx
        else:
            with connection() as db:
                yield db

    def list_customers(self) -> list[dict[str, Any]]:
        with self._read() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT DISTINCT a.* FROM accounts a JOIN assets s ON s.account_id=a.id "
                    "WHERE s.provider_id=?",
                    (self.provider_id,),
                )
            ]

    def list_assets(self) -> list[dict[str, Any]]:
        with self._read() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM assets WHERE provider_id=? ORDER BY id", (self.provider_id,)
                )
            ]

    def available_capacity(self, asset_id: str, hour: str) -> float:
        with self._read() as db:
            row = db.execute(
                "SELECT soc_kwh-min_reserve_kwh-(SELECT COALESCE(SUM(kwh),0) "
                "FROM reservations WHERE asset_id=assets.id AND delivery_hour=? "
                "AND status IN ('reserved','committed')) FROM assets "
                "WHERE id=? AND provider_id=?",
                (hour, asset_id, self.provider_id),
            ).fetchone()
            return max(0.0, row[0]) if row else 0.0

    def reserve_capacity(self, tx: Any, asset_id: str, hour: str, kwh: float) -> str:
        # Bind reads to this same transaction, including reservations made earlier in it.
        adapter = type(self)(tx, self.order_id)
        if not adapter.asset_status(asset_id)["online"]:
            raise ProviderOffline(self.provider_id)
        if kwh <= 0 or kwh > adapter.available_capacity(asset_id, hour):
            raise ValueError("INSUFFICIENT_CAPACITY")
        if self.order_id is None:
            raise ValueError("An order_id is required for a capacity reservation")
        reservation_id = uuid.uuid4().hex
        tx.execute(
            "INSERT INTO reservations VALUES (?,?,?,?,?,'reserved')",
            (reservation_id, self.order_id, asset_id, hour, kwh),
        )
        return reservation_id

    def release_capacity(self, tx: Any, reservation_id: str) -> None:
        tx.execute(
            "UPDATE reservations SET status='released' WHERE id=? AND asset_id IN "
            "(SELECT id FROM assets WHERE provider_id=?)",
            (reservation_id, self.provider_id),
        )

    def verify_delivery(self, reservation_id: str) -> bool:
        with self._read() as db:
            row = db.execute(
                "SELECT asset_id FROM reservations WHERE id=? AND status='committed'",
                (reservation_id,),
            ).fetchone()
            return bool(row and self.asset_status(row[0])["online"])

    def asset_status(self, asset_id: str) -> dict[str, Any]:
        with self._read() as db:
            row = db.execute(
                "SELECT a.id,COALESCE(h.online,1) FROM assets a LEFT JOIN provider_health h "
                "ON h.provider_id=a.provider_id WHERE a.id=? AND a.provider_id=?",
                (asset_id, self.provider_id),
            ).fetchone()
            return {"online": bool(row and row[1] and health.is_online(self.provider_id))}

    def heartbeat(self) -> None:
        health.heartbeat(self.provider_id)


def commit_capacity(db, order_id: str, quantity: int) -> None:
    from ..market import rows

    for reservation in rows(
        db,
        "SELECT * FROM reservations WHERE order_id=? AND status='reserved' ORDER BY rowid",
        (order_id,),
    ):
        used = min(quantity, reservation["kwh"])
        if not used:
            break
        if used < reservation["kwh"]:
            db.execute("UPDATE reservations SET kwh=kwh-? WHERE id=?", (used, reservation["id"]))
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?,?,?,'committed')",
                (
                    uuid.uuid4().hex,
                    order_id,
                    reservation["asset_id"],
                    reservation["delivery_hour"],
                    used,
                ),
            )
        else:
            db.execute(
                "UPDATE reservations SET status='committed' WHERE id=?", (reservation["id"],)
            )
        quantity -= used


def reserved_capacity(db, order_id: str) -> list[dict[str, Any]]:
    from ..market import rows

    return rows(
        db,
        "SELECT r.id,a.provider_id FROM reservations r JOIN assets a ON a.id=r.asset_id WHERE r.order_id=? AND r.status='reserved'",
        (order_id,),
    )


def due_capacity(db, now: datetime) -> list[dict[str, Any]]:
    from ..market import rows

    return rows(
        db,
        "SELECT r.*,a.provider_id FROM reservations r JOIN assets a ON a.id=r.asset_id WHERE r.status='committed' AND julianday(r.delivery_hour)+1.0/24<=julianday(?)",
        (now.isoformat(),),
    )


def set_delivery_status(db, reservation_id: str, delivered: bool) -> None:
    db.execute(
        "UPDATE reservations SET status=? WHERE id=?",
        ("delivered" if delivered else "defaulted", reservation_id),
    )
