"""SEIT-GM-CONTRACT-01: frozen names and runnable skeleton."""

import importlib
import importlib.util
import re
import sqlite3
from collections import Counter
from dataclasses import fields
from pathlib import Path

import pytest

from gridmarket_server import contracts, main, population

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = (ROOT / "CONTRACTS.md").read_text()
KINDS = (
    "Modules and files",
    "Python types and dataclasses",
    "API routes",
    "Request and response fields",
    "HTTP headers",
    "Ledger and event entry types",
    "Bot profile fields and schema",
    "Check and router fields and schema",
    "gridmarket-mcp tool names and arguments",
    "ERCOT Worker snapshot fields",
    "Dashboard page routes and data hooks",
    "Error codes",
)
ROUTES = (
    "GET /v1/market",
    "GET /v1/market/{symbol}",
    "GET /v1/market/history",
    "GET /v1/market/activity",
    "GET /v1/market/status",
    "GET /v1/predictions",
    "GET /v1/predictions/{zone}",
    "GET /v1/signals",
    "GET /v1/providers",
    "GET /v1/providers/health",
    "GET /v1/router",
    "GET /v1/bots",
    "GET /v1/bots/{id}",
    "GET /v1/bots/diversity",
    "POST /v1/sandbox/keys",
    "GET /v1/account",
    "GET /v1/portfolio",
    "GET /v1/positions",
    "GET /v1/trades",
    "GET /v1/losses",
    "GET /v1/assets",
    "GET /v1/assets/{id}",
    "POST /v1/orders",
    "GET /v1/orders",
    "GET /v1/orders/{id}",
    "DELETE /v1/orders/{id}",
    "POST /v1/admin/bots",
    "POST /v1/admin/providers/{id}/outage",
    "POST /v1/admin/halt",
    "POST /v1/admin/resume",
)
ERRORS = (
    "UNAUTHENTICATED",
    "RATE_LIMITED",
    "IDEMPOTENCY_KEY_REQUIRED",
    "IDEMPOTENCY_CONFLICT",
    "MARKET_HALTED",
    "ORDER_TOO_LARGE",
    "POSITION_LIMIT",
    "INSUFFICIENT_FUNDS",
    "INSUFFICIENT_CAPACITY",
    "UNKNOWN_PRODUCT",
    "PRODUCT_CLOSED",
    "PROVIDER_OFFLINE",
    "FORBIDDEN",
    "NOT_FOUND",
    "BAD_REQUEST",
    "INTERNAL_ERROR",
    "VALIDATION_ERROR",
    "SANDBOX_CAP",
    "BOT_CAP",
)
TOOLS = (
    "market",
    "order_book",
    "predictions",
    "router_checks",
    "provider_health",
    "bot_population",
    "my_orders",
    "my_positions",
    "my_pnl",
    "my_losses",
    "buy",
    "sell",
    "cancel",
)
TABLES = (
    "accounts",
    "api_keys",
    "providers",
    "assets",
    "products",
    "orders",
    "trades",
    "positions",
    "reservations",
    "idempotency",
    "events",
    "anomalies",
    "halts",
    "signals",
    "settlements",
    "settled_positions",
    "deposits",
    "bots",
    "bot_meta",
    "router_results",
    "provider_health",
    "sandbox_issuance",
)
MODULES = (
    "market",
    "api",
    "ercot",
    "nws",
    "scoring",
    "seed",
    "providers",
    "providers.base_sim",
    "providers.lonestar",
    "population",
    "economy",
    "bots_api",
    "decision_router",
    "health",
    "jev",
    "keys",
    "bots",
    "adversary",
    "adversary_api",
)


def section(name: str) -> str:
    match = re.search(
        rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", DOCUMENT, re.MULTILINE | re.DOTALL
    )
    assert match, name
    return match.group(1)


def test_seit_gm_contract_01_index() -> None:
    for name in KINDS:
        rows = [line for line in section(name).splitlines() if line.startswith("| `")]
        assert rows, name
        assert all(len(row.split("|")) >= 4 and row.split("|")[2].strip() for row in rows), name
    for name in (*ROUTES, *ERRORS):
        assert name in DOCUMENT, name
    for name in TOOLS:
        assert f"`{name}(" in section("gridmarket-mcp tool names and arguments"), name
    for cls in (contracts.CheckResult, contracts.BotSpec, contracts.WorkerStats):
        for field in fields(cls):
            assert field.name in DOCUMENT, (cls.__name__, field.name)


def test_seit_gm_contract_01_live_names() -> None:
    for path in main.app.openapi()["paths"]:
        assert path in DOCUMENT, path
    app = (ROOT / "dashboard/src/App.tsx").read_text()
    hooks = (ROOT / "dashboard/src/hooks.ts").read_text()
    for route in re.findall(r"'#(/[^']*)'", app):
        assert f"#{route}" in DOCUMENT, route
    for name in re.findall(r"export (?:const|function) (\w+)", hooks):
        assert name in DOCUMENT, name
    for name in MODULES:
        importlib.import_module(f"gridmarket_server.{name}")
    # SDK Client behaviour (market, predictions, account, orders, place_order,
    # cancel_order) is exercised live in test_sdk.py; existence alone proves nothing.
    assert main.app is not None
    assert main.app.openapi()["paths"]["/v1/market/status"]["get"]
    assert importlib.import_module("gridmarket_server.scoring").predict() == []
    assert importlib.import_module("gridmarket_server.health").is_online("base_sim")
    assert not importlib.import_module("gridmarket_server.jev").enabled()
    assert importlib.import_module("gridmarket_server.adversary").halted(None, "a") is None
    assert not importlib.import_module("gridmarket_server.providers").enabled().get("lonestar")
    assert (
        importlib.import_module("gridmarket_server.ercot").signals.latest("report", "zone") is None
    )
    assert len(population.sample("seed")) == 60
    assert Counter(bot.bot_type for bot in population.sample("seed")) == population.DEFAULT_COUNTS


def test_seit_gm_contract_01_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "contract.db"
    with sqlite3.connect(db_path) as db:
        db.executescript((ROOT / "backend/gridmarket_server/schema.sql").read_text())
        actual = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(TABLES) <= actual
        db.execute("PRAGMA foreign_keys=OFF")
        inserts = {
            "trades": "INSERT INTO trades VALUES ('x','p','b','s',1,1,CURRENT_TIMESTAMP)",
            "events": "INSERT INTO events VALUES ('x','fill',NULL,NULL,'{}',CURRENT_TIMESTAMP)",
            "deposits": "INSERT INTO deposits VALUES ('x','a',1,'test',CURRENT_TIMESTAMP)",
            "settled_positions": "INSERT INTO settled_positions VALUES ('x','s','a','p',1,1,CURRENT_TIMESTAMP)",
        }
        for table, insert in inserts.items():
            db.execute(insert)
            for action in (
                f"UPDATE {table} SET id=id WHERE id='x'",
                f"DELETE FROM {table} WHERE id='x'",
            ):
                with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                    db.execute(action)
