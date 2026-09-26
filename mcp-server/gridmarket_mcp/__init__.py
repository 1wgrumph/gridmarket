"""Local stdio MCP tools over the public GridMarket REST API.

Import-safe: reading configuration and opening the server happen in
``gridmarket_mcp.server.main``, never at import time.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

__all__ = ["GridMarketError", "request", "run_tool", "scrub"]

SCRUBBED_KEYS = frozenset({"display_name", "label"})
_TIMEOUT_S = 10.0


def scrub(value: Any) -> Any:
    """Drop every other-user free-text field (RISK-GM-15).

    Display names and key labels are the only user-entered strings the
    public API returns; everything else is numbers, ids, and enums.
    """
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if key not in SCRUBBED_KEYS}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


class GridMarketError(Exception):
    """A failed call to the public API, carrying the error envelope."""

    def __init__(self, status: int | None, body: Any) -> None:
        super().__init__(json.dumps(body))
        self.status = status
        self.body = body


def request(
    base_url: str,
    method: str,
    path: str,
    *,
    key: str | None = None,
    body: Any = None,
    idempotency_key: str | None = None,
) -> Any:
    """One synchronous call to the public API; raises GridMarketError."""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    data = json.dumps(body).encode() if body is not None else None
    req = Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=_TIMEOUT_S) as response:
            raw = response.read().decode()
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode())
        except ValueError:
            payload = {"error": {"code": "UPSTREAM_ERROR", "message": f"HTTP {error.code}"}}
        raise GridMarketError(error.code, payload) from None
    except URLError as error:
        raise GridMarketError(
            None, {"error": {"code": "UPSTREAM_ERROR", "message": str(error.reason)}}
        ) from None
    return json.loads(raw) if raw else None


def _missing(arguments: dict[str, Any], *names: str) -> str | None:
    for name in names:
        if arguments.get(name) is None:
            return name
    return None


def _filter_list(payload: Any, field: str, want: Any) -> Any:
    if isinstance(payload, list):
        rows, wrap = payload, None
    elif isinstance(payload, dict):
        wrap = next(
            (key for key in ("checks", "bots", "items") if isinstance(payload.get(key), list)),
            None,
        )
        rows = payload[wrap] if wrap else []
        if not wrap:
            return payload
    else:
        return payload
    kept = [row for row in rows if not isinstance(row, dict) or row.get(field) == want]
    if wrap is None:
        return kept
    return {**payload, wrap: kept}


def run_tool(
    name: str, arguments: dict[str, Any], *, base_url: str, api_key: str
) -> tuple[bool, Any]:
    """Run one tool; returns ``(is_error, scrubbed_payload)``."""
    try:
        return False, scrub(_dispatch(name, arguments, base_url, api_key))
    except GridMarketError as error:
        return True, scrub(error.body)


def _dispatch(name: str, arguments: dict[str, Any], base_url: str, key: str) -> Any:
    if name == "market":
        return request(base_url, "GET", "/v1/market")
    if name == "order_book":
        if (field := _missing(arguments, "symbol")) is not None:
            raise GridMarketError(400, _bad_request(field))
        return request(base_url, "GET", f"/v1/market/{quote(str(arguments['symbol']), safe='')}")
    if name == "predictions":
        if arguments.get("zone") is not None:
            return request(
                base_url, "GET", f"/v1/predictions/{quote(str(arguments['zone']), safe='')}"
            )
        return request(base_url, "GET", "/v1/predictions")
    if name == "router_checks":
        payload = request(base_url, "GET", "/v1/router")
        if arguments.get("family") is not None:
            return _filter_list(payload, "family", arguments["family"])
        return payload
    if name == "provider_health":
        return request(base_url, "GET", "/v1/providers/health")
    if name == "bot_population":
        payload = request(base_url, "GET", "/v1/bots")
        if arguments.get("bot_type") is not None:
            return _filter_list(payload, "bot_type", arguments["bot_type"])
        return payload
    if name == "my_orders":
        return request(base_url, "GET", "/v1/orders", key=key)
    if name == "my_positions":
        return request(base_url, "GET", "/v1/positions", key=key)
    if name == "my_pnl":
        return request(base_url, "GET", "/v1/portfolio", key=key)
    if name == "my_losses":
        return request(base_url, "GET", "/v1/losses", key=key)
    if name in ("buy", "sell"):
        if (field := _missing(arguments, "product_id", "quantity", "price_cents")) is not None:
            raise GridMarketError(400, _bad_request(field))
        if (field := _missing(arguments, "idempotency_key")) is not None:
            raise GridMarketError(400, _bad_request(field))
        return request(
            base_url,
            "POST",
            "/v1/orders",
            key=key,
            body={
                "product_id": arguments["product_id"],
                "side": name,
                "quantity": arguments["quantity"],
                "price_cents": arguments["price_cents"],
            },
            idempotency_key=str(arguments["idempotency_key"]),
        )
    if name == "cancel":
        if (field := _missing(arguments, "order_id")) is not None:
            raise GridMarketError(400, _bad_request(field))
        return request(
            base_url, "DELETE", f"/v1/orders/{quote(str(arguments['order_id']), safe='')}", key=key
        )
    raise GridMarketError(400, _bad_request(f"unknown tool {name}"))


def _bad_request(field: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": "BAD_REQUEST", "message": f"missing or invalid {field}"}}
