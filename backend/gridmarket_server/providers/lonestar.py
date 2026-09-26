"""LoneStar Storage: a simulated second battery company behind the provider seam."""

import os
import sqlite3
import uuid
from contextlib import closing
from typing import Any

from ..contracts import ProviderOffline

ASSET_FIELDS = (
    "id, account_id, provider_id, zone, capacity_kwh, soc_kwh, min_reserve_kwh, "
    "charge_kw, discharge_kw"
)
RESERVED = (
    "SELECT COALESCE(SUM(kwh), 0) FROM reservations "
    "WHERE asset_id=? AND delivery_hour=? AND status!='released'"
)


def _db() -> sqlite3.Connection:
    return sqlite3.connect(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"))


class LoneStar:
    provider_id = "lonestar"
    display_name = "LoneStar Storage"

    def _offline_asset(self, db: sqlite3.Connection) -> str | None:
        """One bot-owned battery reports offline so the provider page shows asset health."""
        row = db.execute(
            "SELECT a.id FROM assets a JOIN bots b ON b.account_id = a.account_id "
            "WHERE a.provider_id=? ORDER BY b.bot_index DESC, a.id DESC LIMIT 1",
            (self.provider_id,),
        ).fetchone()
        return row[0] if row else None

    def list_customers(self) -> list[dict[str, Any]]:
        with closing(_db()) as db:
            rows = db.execute(
                "SELECT DISTINCT c.id, c.display_name FROM accounts c "
                "JOIN assets a ON a.account_id = c.id WHERE a.provider_id=? ORDER BY c.id",
                (self.provider_id,),
            ).fetchall()
        return [
            {"id": account_id, "name": f"LSS-{n:04d} {name}"}
            for n, (account_id, name) in enumerate(rows, 1)
        ]

    def list_assets(self) -> list[dict[str, Any]]:
        with closing(_db()) as db:
            db.row_factory = sqlite3.Row
            offline = self._offline_asset(db)
            rows = db.execute(
                f"SELECT {ASSET_FIELDS} FROM assets WHERE provider_id=? ORDER BY id",
                (self.provider_id,),
            ).fetchall()
        assets = [dict(row) | {"online": row["id"] != offline} for row in rows]
        return sorted(assets, key=lambda asset: not asset["online"])

    def _capacity(self, db: sqlite3.Connection, asset_id: str, hour: str) -> float:
        row = db.execute(
            "SELECT soc_kwh - min_reserve_kwh FROM assets WHERE id=? AND provider_id=?",
            (asset_id, self.provider_id),
        ).fetchone()
        if row is None or asset_id == self._offline_asset(db):
            return 0.0
        return max(0.0, row[0] - db.execute(RESERVED, (asset_id, hour)).fetchone()[0])

    def available_capacity(self, asset_id: str, hour: str) -> float:
        with closing(_db()) as db:
            return self._capacity(db, asset_id, hour)

    def reserve_capacity(self, tx: Any, asset_id: str, hour: str, kwh: float) -> str:
        if asset_id == self._offline_asset(tx):
            raise ProviderOffline(f"{self.display_name} asset {asset_id} is offline")
        if kwh <= 0 or kwh > self._capacity(tx, asset_id, hour):
            raise ValueError("INSUFFICIENT_CAPACITY")
        # ponytail: the contract passes no order id; the caller inserts its order in tx first.
        order = tx.execute("SELECT id FROM orders ORDER BY rowid DESC LIMIT 1").fetchone()
        reservation_id = str(uuid.uuid4())
        tx.execute(
            "INSERT INTO reservations (id, order_id, asset_id, delivery_hour, kwh, status) "
            "VALUES (?, ?, ?, ?, ?, 'reserved')",
            (reservation_id, order[0] if order else "", asset_id, hour, kwh),
        )
        return reservation_id

    def release_capacity(self, tx: Any, reservation_id: str) -> None:
        tx.execute(
            "UPDATE reservations SET status='released' WHERE id=? AND asset_id IN "
            "(SELECT id FROM assets WHERE provider_id=?)",
            (reservation_id, self.provider_id),
        )

    def verify_delivery(self, reservation_id: str) -> bool:
        with closing(_db()) as db:
            row = db.execute(
                "SELECT r.asset_id FROM reservations r JOIN assets a ON a.id = r.asset_id "
                "WHERE r.id=? AND a.provider_id=? AND r.status!='released'",
                (reservation_id, self.provider_id),
            ).fetchone()
            return row is not None and row[0] != self._offline_asset(db)

    def asset_status(self, asset_id: str) -> dict[str, Any]:
        with closing(_db()) as db:
            return {"online": asset_id != self._offline_asset(db)}

    def heartbeat(self) -> None:
        """Liveness probe: the simulated company is always reachable; outages are set in health."""
