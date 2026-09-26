"""Public bot population routes and the admin spawn endpoint."""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import economy, population
from .bots import bot_key
from .contracts import BotSpec

logger = logging.getLogger(__name__)
router = APIRouter()

BOT_CAP = 200
SEEDED_COUNT = 60


class SpawnRequest(BaseModel):
    count: int = Field(ge=1, le=10)
    seed: str | None = None


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(Path(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db")))
    conn.execute(
        "INSERT OR IGNORE INTO providers (id, display_name) VALUES ('base_sim', 'Base Simulation')"
    )
    return conn


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _master_seed(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM bot_meta WHERE key = 'master_seed'").fetchone()
    if row:
        return str(row[0])
    env = os.getenv("GRIDMARKET_BOT_MASTER_SEED")
    if env:
        return env
    drawn = secrets.token_hex(8)
    conn.execute("INSERT OR IGNORE INTO bot_meta (key, value) VALUES ('master_seed', ?)", (drawn,))
    conn.commit()
    return drawn


def _insert_bot(conn: sqlite3.Connection, spec: BotSpec) -> str:
    bot_id = f"bot-{spec.index}"
    account_id = f"acct-bot-{spec.index}"
    conn.execute(
        "INSERT OR IGNORE INTO accounts (id, display_name, cash_cents) VALUES (?, ?, ?)",
        (account_id, bot_id, round(spec.start_cash * 100)),
    )
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (id, account_id, key_hash, label) VALUES (?, ?, ?, 'bot')",
        (
            f"key-bot-{spec.index}",
            account_id,
            hashlib.sha256(bot_key(spec.index).encode()).hexdigest(),
        ),
    )
    reserve_pct = float(spec.household.get("reserve_pct", 0.2))
    for position, capacity in enumerate(spec.household.get("batteries", [])):
        limit = round(min(10.0, max(2.0, float(capacity) / 4)), 2)
        conn.execute(
            """
            INSERT OR IGNORE INTO assets (
                id, account_id, provider_id, zone, capacity_kwh, soc_kwh,
                min_reserve_kwh, charge_kw, discharge_kw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"asset-{spec.index}-{position}",
                account_id,
                spec.provider_id,
                spec.household.get("zone", "LZ_HOUSTON"),
                float(capacity),
                float(capacity),
                round(float(capacity) * reserve_pct, 2),
                limit,
                limit,
            ),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO bots (
            id, account_id, bot_index, bot_type, provider_id, profile_json, dormant
        ) VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (
            bot_id,
            account_id,
            spec.index,
            spec.bot_type,
            spec.provider_id,
            json.dumps(asdict(spec)),
        ),
    )
    return bot_id


def _ensure_seeded(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0]:
        return
    for spec in population.sample(_master_seed(conn), 0, SEEDED_COUNT):
        _insert_bot(conn, spec)
    conn.commit()


def _next_index(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(bot_index), -1) FROM bots").fetchone()
    return int(row[0]) + 1


@router.get("/v1/bots")
def list_bots() -> list[dict[str, object]]:
    with _db() as conn:
        _ensure_seeded(conn)
        return [
            {
                "id": bot_id,
                "bot_index": index,
                "bot_type": bot_type,
                "provider_id": provider_id,
                "dormant": bool(dormant),
            }
            for bot_id, index, bot_type, provider_id, dormant in conn.execute(
                "SELECT id, bot_index, bot_type, provider_id, dormant FROM bots ORDER BY bot_index"
            ).fetchall()
        ]


@router.get("/v1/bots/{id}")
def bot_profile(id: str) -> JSONResponse:
    with _db() as conn:
        row = conn.execute(
            "SELECT account_id, bot_type, provider_id, profile_json FROM bots WHERE id = ?",
            (id,),
        ).fetchone()
        if row is None:
            return _error(404, "NOT_FOUND", f"unknown bot {id}")
        account_id, bot_type, provider_id, raw = row
    profile = json.loads(raw)
    try:
        report = economy.stats(account_id)
    except KeyError:
        return _error(404, "NOT_FOUND", f"unknown bot {id}")
    body = {
        "id": id,
        "bot_type": bot_type,
        "blend": profile.get("blend", {bot_type: 1.0}),
        "provider_id": provider_id,
        "traits": profile.get("traits", {}),
        "household": profile.get("household", {}),
        "employed": profile.get("employed", False),
        "pay": profile.get("pay", 0.0),
    }
    body.update(report)
    return JSONResponse(content=body)


@router.post("/v1/admin/bots")
def spawn_bots(request: Request, spawn: SpawnRequest) -> JSONResponse:
    if "CF-Connecting-IP" in request.headers:
        return _error(403, "FORBIDDEN", "admin requests must come from the host loopback")
    admin = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    if not admin or request.headers.get("Authorization") != f"Bearer {admin}":
        return _error(401, "UNAUTHENTICATED", "admin key required")
    with _db() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0])
        if total + spawn.count > BOT_CAP:
            return _error(409, "BOT_CAP", f"bot population capped at {BOT_CAP}")
        master = _master_seed(conn)
        specs = population.sample(master, _next_index(conn), spawn.count, seed=spawn.seed)
        for spec in specs:
            _insert_bot(conn, spec)
        conn.commit()
    used = spawn.seed if spawn.seed is not None else master
    logger.info("spawned %d bots with seed %s", spawn.count, used)
    return JSONResponse(content={"spawned": spawn.count, "seed": used})
