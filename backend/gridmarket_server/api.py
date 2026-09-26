"""REST account boundary, shared guards and sandbox onboarding."""

import asyncio
import hashlib
import hmac
import json
import math
import os
import re
import time
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictInt
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


def address(request: Request) -> str:
    return request.headers.get(
        "CF-Connecting-IP", request.client.host if request.client else "unknown"
    )


def admin_guard(request: Request) -> None:
    configured = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    authorization = request.headers.get("Authorization", "")
    if not configured or not hmac.compare_digest(authorization, "Bearer " + configured):
        market.reject("UNAUTHENTICATED", 401)
    if "CF-Connecting-IP" in request.headers:
        market.reject("FORBIDDEN", 403)
    if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
        market.reject("FORBIDDEN", 403)


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
    return error_response(422, "VALIDATION_ERROR")


class Boundary:
    def __init__(self, app):
        self.app = app
        # ponytail: one-process token buckets; use a shared store for multiple API workers.
        self.buckets: dict[str, tuple[float, float]] = {}
        self.pruned_at = time.monotonic()

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
            rate = burst = 0
            identity = ""
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
                identity = "key:" + digest
            elif public:
                rate, burst = 10, 20
                identity = "ip:" + address(request)
            if rate:
                now = time.monotonic()
                if now - self.pruned_at > 60:
                    self.buckets = {
                        key: value for key, value in self.buckets.items() if now - value[1] < 60
                    }
                    self.pruned_at = now
                tokens, prior = self.buckets.get(identity, (float(burst), now))
                tokens = min(burst, tokens + (now - prior) * rate)
                headers = {
                    "X-RateLimit-Limit": str(rate),
                    "X-RateLimit-Remaining": str(max(0, int(tokens - 1))),
                }
                if tokens < 1:
                    headers["Retry-After"] = str(max(1, math.ceil((1 - tokens) / rate)))
                    market.reject("RATE_LIMITED", 429)
                self.buckets[identity] = (tokens - 1, now)
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
    quantity: StrictInt
    price_cents: StrictInt


@router.post("/v1/orders")
def place_order(request: Request, body: OrderRequest) -> dict:
    key = request.headers.get("Idempotency-Key")
    if not key:
        market.reject("IDEMPOTENCY_KEY_REQUIRED", 400)
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
            "SELECT p.*,x.zone,x.delivery_hour FROM positions p JOIN products x ON x.id=p.product_id WHERE p.account_id=? AND p.quantity!=0 AND x.symbol LIKE 'FLEX-%'",
            (account_id,),
        ):
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


@router.get("/v1/providers")
def providers() -> list[dict]:
    from . import health

    with market.connection() as db:
        counts = dict(
            db.execute("SELECT provider_id, COUNT(*) FROM bots GROUP BY provider_id").fetchall()
        )
    return [
        {
            "id": name,
            "display_name": cls.display_name,
            "participants": counts.get(name, 0),
            "online": health.is_online(name),
        }
        for name, cls in enabled().items()
    ]


@router.post("/v1/sandbox/keys")
def sandbox(request: Request, body: dict) -> dict:
    label = body.get("label", "Sandbox")
    if not isinstance(label, str) or re.fullmatch(r"[A-Za-z0-9 _-]{1,24}", label) is None:
        market.reject("VALIDATION_ERROR")
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
