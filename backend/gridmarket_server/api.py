"""REST account boundary, shared guards and sandbox onboarding."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import os
import re
import time
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware

from . import keys, market
from .providers import enabled

PUBLIC = ("/v1/market", "/v1/predictions", "/v1/signals", "/v1/providers", "/v1/router", "/v1/bots")
PRIVATE = (
    "/v1/account",
    "/v1/portfolio",
    "/v1/positions",
    "/v1/trades",
    "/v1/losses",
    "/v1/assets",
    "/v1/orders",
)


def within(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


API_DOC_PREFIXES = ("/docs", "/openapi.json", "/redoc")


def is_api_path(path: str) -> bool:
    return path == "/v1" or path.startswith("/v1/") or within(path, API_DOC_PREFIXES)


def address(request: Request) -> str:
    host = request.headers.get(
        "CF-Connecting-IP", request.client.host if request.client else "unknown"
    )
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def _parse_admin_nets(
    raw: str | None = None,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    text = os.getenv("GRIDMARKET_ADMIN_NETS", "") if raw is None else raw
    if not text.strip():
        return ()
    nets = []
    for part in text.split(","):
        part = part.strip()
        if part:
            nets.append(ipaddress.ip_network(part, strict=False))
    return tuple(nets)


# Loopback only by default; compose deployment configures GRIDMARKET_ADMIN_NETS.
ADMIN_NETS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()


def admin_local(host: str | None) -> bool:
    """Loopback or a compose-subnet peer (the bridge gateway) with no tunnel header.

    The published port binds 127.0.0.1 only, so such a peer is the host owner
    or another compose service; tunnel traffic always carries CF-Connecting-IP.
    """
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address in (ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")):
        return True
    trusted = _parse_admin_nets() or ADMIN_NETS
    return any(address in net for net in trusted)


def admin_guard(request: Request) -> None:
    # Reject remote peers before touching the secret: no key oracle remotely.
    if "CF-Connecting-IP" in request.headers or not admin_local(
        request.client.host if request.client else None
    ):
        market.reject("FORBIDDEN", 403)
    configured = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    authorization = request.headers.get("Authorization", "")
    if not configured or not hmac.compare_digest(
        authorization.encode(), ("Bearer " + configured).encode()
    ):
        market.reject("UNAUTHENTICATED", 401)


def error_response(status: int, code: str, message: str | None = None, headers=None):
    return JSONResponse(
        {"error": {"code": code, "message": message or code.replace("_", " ").capitalize()}},
        status_code=status,
        headers=headers,
    )


async def http_error(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        code, message = exc.detail["code"], exc.detail["message"]
    else:
        code = {404: "NOT_FOUND", 401: "UNAUTHENTICATED", 403: "FORBIDDEN"}.get(
            exc.status_code, "BAD_REQUEST"
        )
        message = str(exc.detail)
    if request.method == "POST" and request.url.path == "/v1/orders":
        market.observe_rejection(exc, getattr(request.state, "account_id", None), code)
    return error_response(exc.status_code, code, message, exc.headers)


async def validation_error(request: Request, exc: RequestValidationError):
    if request.method == "POST" and request.url.path == "/v1/orders":
        market.observe_rejection(
            exc, getattr(request.state, "account_id", None), "VALIDATION_ERROR"
        )
    problem = exc.errors()[0]
    field = ".".join(str(part) for part in problem["loc"])
    return error_response(422, "VALIDATION_ERROR", f"{field}: {problem['msg']}")


async def unhandled_error(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("unhandled %s %s", request.method, request.url.path)
    return error_response(500, "INTERNAL_ERROR", "Internal error")


class Boundary:
    def __init__(self, app):
        self.app = app
        # ponytail: one-process token buckets; use a shared store for multiple API workers.
        self.buckets: dict[str, tuple[float, float]] = {}
        self.pruned_at = time.monotonic()

    def limit(self, identity, rate, burst, headers):
        now = time.monotonic()
        if now - self.pruned_at > 60:
            self.buckets = {
                key: value for key, value in self.buckets.items() if now - value[1] < 60
            }
            self.pruned_at = now
        tokens, prior = self.buckets.get(identity, (float(burst), now))
        tokens = min(burst, tokens + (now - prior) * rate)
        headers.update(
            {
                "X-RateLimit-Limit": str(rate),
                "X-RateLimit-Remaining": str(max(0, int(tokens - 1))),
            }
        )
        if tokens < 1:
            headers["Retry-After"] = str(max(1, math.ceil((1 - tokens) / rate)))
            market.reject("RATE_LIMITED", 429)
        self.buckets[identity] = (tokens - 1, now)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = request.url.path
        public = request.method == "GET" and within(path, PUBLIC)
        origin = request.headers.get("Origin")
        cors = public and bool(origin) and origin == os.getenv("GRIDMARKET_CORS_ORIGIN")
        headers = {}
        try:
            if not is_api_path(path):
                # Static page and asset requests use an independent per-IP bucket
                # (DEC-GM-152) so cold dashboard loads never exhaust API rate limits.
                static_identity = "static:" + address(request)
                self.limit(static_identity, 60, 200, headers)
            else:
                # Check before any credential lookup. Valid account keys refund this
                # token and use their own bucket; anonymous traffic shares the IP cap.
                ip_identity = "ip:" + address(request)
                rate, burst = (30, 60) if public else (10, 20)
                self.limit(ip_identity, rate, burst, headers)
                if path.startswith("/v1/admin/"):
                    admin_guard(request)
                elif within(path, PRIVATE):
                    authorization = request.headers.get("Authorization", "")
                    if not authorization.startswith("Bearer "):
                        market.reject("UNAUTHENTICATED", 401)
                    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
                    with market.connection() as db:
                        key = db.execute(
                            "SELECT account_id FROM api_keys WHERE key_hash=?", (digest,)
                        ).fetchone()
                        if key is None:
                            market.reject("UNAUTHENTICATED", 401)
                        account_id = key[0]
                        sandbox = db.execute(
                            "SELECT 1 FROM sandbox_issuance WHERE account_id=?", (account_id,)
                        ).fetchone()
                    request.state.account_id = account_id
                    rate, burst = (5, 10) if sandbox else (20, 40)
                    tokens, prior = self.buckets[ip_identity]
                    self.buckets[ip_identity] = (tokens + 1, prior)
                    self.limit("key:" + digest, rate, burst, headers)
        except HTTPException as exc:
            response = await http_error(request, exc)
            response.headers.update(headers)
            if cors:
                response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
                response.headers["Vary"] = "Origin"
            return await response(scope, receive, send)

        async def send_headers(message):
            if message["type"] == "http.response.start":
                from starlette.datastructures import MutableHeaders

                response_headers = MutableHeaders(scope=message)
                response_headers.update(headers)
                if cors:
                    response_headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
                    response_headers.append("Vary", "Origin")
            await send(message)

        await self.app(scope, receive, send_headers)


@asynccontextmanager
async def lifespan(app):
    # The composition root includes this router; install the shared boundary once,
    # including guards on admin routes owned by other lanes.
    middleware = Middleware(Boundary)
    app.user_middleware.insert(0, middleware)
    app.exception_handlers[HTTPException] = http_error
    app.exception_handlers[RequestValidationError] = validation_error
    app.exception_handlers[Exception] = unhandled_error
    app.middleware_stack = app.build_middleware_stack()

    async def repeat():
        while True:
            try:
                await asyncio.to_thread(market.tick)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("Market tick failed; retrying next tick")
            await asyncio.sleep(60)

    task = asyncio.create_task(repeat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        app.user_middleware.remove(middleware)
        app.middleware_stack = app.build_middleware_stack()


router = APIRouter(lifespan=lifespan)


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str
    side: Literal["buy", "sell"]
    quantity: StrictInt = Field(ge=1)
    price_cents: StrictInt


@router.post("/v1/orders")
def place_order(request: Request, body: OrderRequest) -> dict:
    key = request.headers.get("Idempotency-Key")
    if not key:
        market.reject("IDEMPOTENCY_KEY_REQUIRED", 400)
    if len(key) > 128:
        market.reject("VALIDATION_ERROR", 422, "Idempotency-Key must be at most 128 characters")
    account_id = request.state.account_id
    payload = body.model_dump()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with market.connection(write=True) as db:
        previous = db.execute(
            "SELECT request_hash,response_json FROM idempotency WHERE account_id=? AND key=?",
            (account_id, key),
        ).fetchone()
        if previous:
            if previous[0] != digest:
                market.reject("IDEMPOTENCY_CONFLICT", 409)
            return json.loads(previous[1])
        response = market.place_order(db, account_id, payload)
        db.execute(
            "INSERT INTO idempotency VALUES (?,?,?,?)",
            (account_id, key, digest, json.dumps(response)),
        )
    return response


@router.get("/v1/orders")
def orders(request: Request) -> list[dict]:
    with market.connection() as db:
        return market.rows(
            db,
            "SELECT * FROM orders WHERE account_id=? ORDER BY rowid DESC",
            (request.state.account_id,),
        )


@router.get("/v1/orders/{id}")
def order(request: Request, id: str) -> dict:
    with market.connection() as db:
        found = market.rows(
            db, "SELECT * FROM orders WHERE id=? AND account_id=?", (id, request.state.account_id)
        )
    if not found:
        market.reject("NOT_FOUND", 404)
    return found[0]


@router.delete("/v1/orders/{id}")
def cancel_order(request: Request, id: str) -> dict:
    with market.connection(write=True) as db:
        return market.cancel(db, request.state.account_id, id)


@router.get("/v1/account")
def account(request: Request) -> dict:
    from . import scoring

    with market.connection() as db:
        account_id = request.state.account_id
        result = market.rows(db, "SELECT * FROM accounts WHERE id=?", (account_id,))[0]
        result["cash_held_cents"] = market.cash_held(db, account_id)
        result["realized_pnl_cents"] = db.execute(
            "SELECT COALESCE(SUM(pnl_cents),0) FROM settled_positions WHERE account_id=?",
            (account_id,),
        ).fetchone()[0]
        result["unrealized_pnl_cents"] = 0
        for position in market.rows(
            db,
            "SELECT p.*,x.zone,x.delivery_hour FROM positions p JOIN products x ON x.id=p.product_id WHERE p.account_id=? AND x.status!='settled' AND x.symbol NOT LIKE 'SPOT-%'",
            (account_id,),
        ):
            if position["quantity"] == 0:
                mark = 0
            else:
                last = db.execute(
                    "SELECT price_cents FROM trades WHERE product_id=? ORDER BY rowid DESC LIMIT 1",
                    (position["product_id"],),
                ).fetchone()
                if last:
                    mark = last[0]
                else:
                    book = db.execute(
                        "SELECT MAX(CASE WHEN side='buy' THEN price_cents END),MIN(CASE WHEN side='sell' THEN price_cents END) FROM orders WHERE product_id=? AND status='open'",
                        (position["product_id"],),
                    ).fetchone()
                    if all(price is not None for price in book):
                        mark = sum(book) / 2
                    else:
                        prediction = next(
                            (
                                p
                                for p in scoring.predict()
                                if p.zone == position["zone"]
                                and p.delivery_hour == position["delivery_hour"]
                            ),
                            None,
                        )
                        if prediction is None:
                            continue
                        mark = prediction.expected_value * 100
            prior = db.execute(
                "SELECT COALESCE(SUM(pnl_cents),0) FROM settled_positions WHERE account_id=? AND product_id=?",
                (account_id, position["product_id"]),
            ).fetchone()[0]
            result["unrealized_pnl_cents"] += round(
                market.trade_value(db, account_id, position["product_id"])
                + position["quantity"] * mark
                - prior
            )
    return result


@router.get("/v1/portfolio")
def portfolio(request: Request) -> dict:
    return {**account(request), "positions": positions(request)}


@router.get("/v1/positions")
def positions(request: Request) -> list[dict]:
    with market.connection() as db:
        return market.rows(
            db,
            "SELECT * FROM positions WHERE account_id=? AND quantity!=0",
            (request.state.account_id,),
        )


@router.get("/v1/trades")
def trades(request: Request) -> list[dict]:
    with market.connection() as db:
        return market.rows(
            db,
            "SELECT t.* FROM trades t JOIN orders b ON b.id=t.buy_order_id JOIN orders s ON s.id=t.sell_order_id WHERE b.account_id=? OR s.account_id=? ORDER BY t.rowid",
            (request.state.account_id, request.state.account_id),
        )


@router.get("/v1/losses")
def losses(request: Request) -> list[dict]:
    with market.connection() as db:
        return market.rows(
            db,
            "SELECT * FROM settled_positions WHERE account_id=? AND pnl_cents<0 ORDER BY rowid",
            (request.state.account_id,),
        )


@router.get("/v1/assets")
def assets(request: Request) -> list[dict]:
    return [
        asset
        for cls in enabled().values()
        for asset in cls().list_assets()
        if asset["account_id"] == request.state.account_id
    ]


@router.get("/v1/assets/{id}")
def asset(request: Request, id: str) -> dict:
    found = next((asset for asset in assets(request) if asset["id"] == id), None)
    if found is None:
        market.reject("NOT_FOUND", 404)
    return found


@router.get("/v1/signals/history")
def signals_history(report_id: str, zone: str, start: str, end: str) -> list[dict]:
    from . import ercot

    if report_id not in ercot.POLL_MINUTES:
        market.reject("VALIDATION_ERROR", 422, f"report_id: unknown report {report_id!r}")
    if not zone:
        market.reject("VALIDATION_ERROR", 422, "zone: zone is required")
    try:
        since = datetime.fromisoformat(start)
    except ValueError:
        market.reject("VALIDATION_ERROR", 422, "start: invalid timestamp")
        raise
    try:
        until = datetime.fromisoformat(end)
    except ValueError:
        market.reject("VALIDATION_ERROR", 422, "end: invalid timestamp")
        raise
    for field, stamp in (("start", since), ("end", until)):
        if stamp.tzinfo is None:
            market.reject("VALIDATION_ERROR", 422, f"{field}: timestamp requires a UTC offset")
    if until <= since:
        market.reject("VALIDATION_ERROR", 422, "end: end must be after start")
    if until - since > timedelta(hours=48):
        market.reject("VALIDATION_ERROR", 422, "end: window exceeds 48 hours")
    rows = ercot.signals.history(
        report_id, zone, since.astimezone(UTC).isoformat(), until.astimezone(UTC).isoformat()
    )
    if len(rows) > 10000:
        market.reject(
            "VALIDATION_ERROR", 422, "end: window holds more than 10000 rows; narrow start/end"
        )
    return rows


@router.get("/v1/providers")
def providers() -> list[dict]:
    from . import health

    with market.connection() as db:
        participants = market.rows(db, "SELECT provider_id, account_id FROM bots")
    return [
        {
            "id": name,
            "display_name": cls.display_name,
            "participants": len(
                {p["account_id"] for p in participants if p["provider_id"] == name}
                | {customer["id"] for customer in cls().list_customers()}
            ),
            "online": health.is_online(name),
        }
        for name, cls in enabled().items()
    ]


@router.post("/v1/sandbox/keys")
def sandbox(request: Request, body: dict) -> dict:
    label = body.get("label", "Sandbox")
    if not isinstance(label, str) or re.fullmatch(r"[A-Za-z0-9 _-]{1,24}", label) is None:
        market.reject("VALIDATION_ERROR", 422, "label must be 1–24 letters, digits, spaces, _ or -")
    client_address = address(request)
    hashed = hashlib.sha256(client_address.encode()).hexdigest()
    with market.connection(write=True) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM sandbox_issuance WHERE address_hash=? AND datetime(issued_at)>datetime('now','-60 minutes')",
            (hashed,),
        ).fetchone()[0]
        if count >= 3:
            raise HTTPException(
                429,
                {"code": "RATE_LIMITED", "message": "Three sandbox keys per hour"},
                headers={"Retry-After": "3600"},
            )
        if db.execute("SELECT COUNT(*) FROM sandbox_issuance").fetchone()[0] >= 300:
            market.reject("SANDBOX_CAP", 503)
        return keys.issue(db, label, client_address)
