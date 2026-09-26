"""Public bot population routes and the admin spawn endpoint."""

import hashlib
import hmac
import ipaddress
import json
import logging
import math
import os
import secrets
import sqlite3
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import stdev

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import economy, keys, population
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
    conn = sqlite3.connect(Path(os.getenv("GRIDMARKET_DB") or "/data/gridmarket.db"))
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


def _insert_bot(conn: sqlite3.Connection, spec: BotSpec, seed: str | None = None) -> str:
    bot_id = f"bot-{spec.index}"
    account_id = f"acct-bot-{spec.index}"
    conn.execute(
        "INSERT OR IGNORE INTO accounts (id, display_name, cash_cents) VALUES (?, ?, ?)",
        (account_id, bot_id, round(spec.start_cash * 100)),
    )
    # Without a configured secret, seed random keys like seed.py; never derive from "".
    secret = os.getenv("GRIDMARKET_BOT_SECRET")
    key = bot_key(spec.index, secret) if secret else keys.sandbox_key()
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (id, account_id, key_hash, label) VALUES (?, ?, ?, 'bot')",
        (
            f"key-bot-{spec.index}",
            account_id,
            hashlib.sha256(key.encode()).hexdigest(),
        ),
    )
    reserve_pct = float(spec.household.get("reserve_pct", 0.2))
    for position, capacity in enumerate(spec.household.get("batteries", [])):
        limit = round(min(10.0, max(2.0, float(capacity) * 0.37)), 2)
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
    profile = asdict(spec) | {"cohort_seed": seed}
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
            json.dumps(profile),
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
        settled: dict[str, list[int]] = {}
        for account_id, pnl in conn.execute(
            "SELECT account_id, pnl_cents FROM settled_positions"
        ).fetchall():
            settled.setdefault(account_id, []).append(pnl)
        rows = []
        for bot_id, account_id, index, bot_type, provider_id, dormant, raw in conn.execute(
            "SELECT id, account_id, bot_index, bot_type, provider_id, dormant, profile_json "
            "FROM bots ORDER BY bot_index"
        ).fetchall():
            profile = json.loads(raw)
            pnls = settled.get(account_id, [])
            losses = sum(1 for pnl in pnls if pnl < 0)
            rows.append(
                {
                    "id": bot_id,
                    "bot_index": index,
                    "bot_type": bot_type,
                    "provider_id": provider_id,
                    "dormant": bool(dormant),
                    "blend": profile.get("blend", {bot_type: 1.0}),
                    "traits": profile.get("traits", {}),
                    "household": profile.get("household", {}),
                    "info": profile.get("info", {}),
                    "employed": profile.get("employed", False),
                    "losses": losses,
                    "loss_share": losses / len(pnls) if pnls else 0.0,
                }
            )
        return rows


@router.get("/v1/bots/diversity")
def bot_diversity() -> dict[str, object]:
    with _db() as conn:
        _ensure_seeded(conn)
        rows = conn.execute("SELECT bot_type, profile_json FROM bots ORDER BY bot_index").fetchall()
    bot_types = [row[0] for row in rows]
    traits = [json.loads(row[1])["traits"] for row in rows]
    names = list(traits[0])
    columns = ([trait[name] for trait in traits] for name in names)
    coverage = sum(stdev(column) >= 0.05 for column in columns) / 7
    counts = Counter(bot_types)
    total = len(bot_types)
    entropy = -sum(count / total * math.log2(count / total) for count in counts.values())
    points = [
        {"risk_appetite": trait["risk appetite"], "patience": trait["patience"]} for trait in traits
    ]
    return {"coverage": coverage, "entropy": entropy, "points": points}


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
        "info": profile.get("info", {}),
        "employed": profile.get("employed", False),
        "pay": profile.get("pay", 0.0),
    }
    body.update(report)
    return JSONResponse(content=body)


_ADMIN_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fd00::/8"),
)


def _admin_local(request: Request) -> bool:
    """Same rule as api.admin_local: loopback or a compose-subnet peer, never the tunnel."""
    if "CF-Connecting-IP" in request.headers:
        return False
    host = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or any(address in net for net in _ADMIN_NETS)


@router.post("/v1/admin/bots")
def spawn_bots(request: Request, spawn: SpawnRequest) -> JSONResponse:
    if not _admin_local(request):
        return _error(403, "FORBIDDEN", "admin requests must come from the host loopback")
    admin = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    given = request.headers.get("Authorization", "")
    if not admin or not hmac.compare_digest(
        given.encode("utf-8", "ignore"), f"Bearer {admin}".encode()
    ):
        return _error(401, "UNAUTHENTICATED", "admin key required")
    if not os.getenv("GRIDMARKET_BOT_SECRET"):
        return _error(503, "BOT_SECRET_UNSET", "set GRIDMARKET_BOT_SECRET before spawning bots")
    with _db() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0])
        if total + spawn.count > BOT_CAP:
            return _error(409, "BOT_CAP", f"bot population capped at {BOT_CAP}")
        master = _master_seed(conn)
        specs = population.sample(master, _next_index(conn), spawn.count, seed=spawn.seed)
        for spec in specs:
            _insert_bot(conn, spec, seed=spawn.seed)
        conn.commit()
    used = spawn.seed if spawn.seed is not None else master
    logger.info("spawned %d bots with seed %s", spawn.count, used)
    return JSONResponse(content={"spawned": spawn.count, "seed": used})
