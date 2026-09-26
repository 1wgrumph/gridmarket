"""Public GridMarket SDK signatures; market lane supplies implementation."""

from typing import Any

import httpx


class Client:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        with httpx.Client(base_url=self.base_url, headers=headers) as client:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    def market(self) -> Any:
        return self.request("GET", "/v1/market")

    def predictions(self) -> Any:
        return self.request("GET", "/v1/predictions")

    def account(self) -> Any:
        return self.request("GET", "/v1/account")

    def orders(self) -> Any:
        return self.request("GET", "/v1/orders")

    def place_order(self, order: dict[str, Any], idempotency_key: str) -> Any:
        return self.request(
            "POST",
            "/v1/orders",
            json=order,
            headers={"Idempotency-Key": idempotency_key},
        )

    def cancel_order(self, order_id: str) -> Any:
        return self.request("DELETE", f"/v1/orders/{order_id}")
