"""GridMarket Python SDK: standard library only, so judges need nothing but Python 3."""

import json
import uuid
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

__all__ = ["Client", "GridMarketError"]


def _path(base: str, segment: str | None) -> str:
    return f"{base}/{quote(segment, safe='')}" if segment else base


class GridMarketError(Exception):
    """Non-2xx API response carrying the `{"error": {"code", "message"}}` envelope."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


class Client:
    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", api_key: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json", **(headers or {})}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=10) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            try:
                error = json.loads(raw)["error"]
                code, message = error["code"], error["message"]
            except (ValueError, KeyError, TypeError):
                code, message = "HTTP_ERROR", raw.decode(errors="replace") or exc.reason
            raise GridMarketError(exc.code, code, message) from None
        return json.loads(raw) if raw else None

    def market(self, symbol: str | None = None) -> Any:
        return self.request("GET", _path("/v1/market", symbol))

    def predictions(self, zone: str | None = None) -> Any:
        return self.request("GET", _path("/v1/predictions", zone))

    def account(self) -> Any:
        return self.request("GET", "/v1/account")

    def portfolio(self) -> Any:
        return self.request("GET", "/v1/portfolio")

    def orders(self) -> Any:
        return self.request("GET", "/v1/orders")

    def place_order(
        self, order: dict[str, Any], idempotency_key: str | None = None
    ) -> Any:
        key = idempotency_key or str(uuid.uuid4())
        return self.request("POST", "/v1/orders", order, {"Idempotency-Key": key})

    def buy(self, product_id: str, quantity: int, price_cents: int) -> Any:
        """`product_id` may be a product id or the `FLEX-<zone>-<HH>` alias."""
        order = {"product_id": product_id, "side": "buy", "quantity": quantity}
        return self.place_order({**order, "price_cents": price_cents})

    def sell(self, product_id: str, quantity: int, price_cents: int) -> Any:
        order = {"product_id": product_id, "side": "sell", "quantity": quantity}
        return self.place_order({**order, "price_cents": price_cents})

    def cancel_order(self, order_id: str) -> Any:
        return self.request("DELETE", _path("/v1/orders", order_id))

    cancel = cancel_order
