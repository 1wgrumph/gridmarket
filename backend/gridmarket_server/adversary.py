"""Adversarial scenario driver, halt check, and rejection observer (stretch)."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import os
import sqlite3
import sys
import uuid
from collections import deque
from typing import Any

import httpx

# In-memory anomaly records. observe() is called inside the market write
# transaction, so it must never do its own DB I/O (same-thread lock wait).
SEEN: deque[dict[str, Any]] = deque(maxlen=1000)

REJECTION_ENTRY_TYPES = frozenset({"reject"})
CODE_KINDS = {
    "INSUFFICIENT_CAPACITY": "over_capacity",
    "IDEMPOTENCY_CONFLICT": "idempotent_replay",
    "IDEMPOTENCY_KEY_REQUIRED": "idempotent_replay",
    "RATE_LIMITED": "rate_limited",
}


def halted(tx: Any, account_id: str) -> str | None:
    """Return the active halt scope for an account, or None when trading."""
    if tx is None:
        return None
    row = tx.execute(
        "SELECT account_id FROM halts WHERE ended_at IS NULL"
        " AND (account_id IS NULL OR account_id=?) LIMIT 1",
        (account_id,),
    ).fetchone()
    if row is None:
        return None
    scope = row[0] if not hasattr(row, "keys") else row["account_id"]
    return "market" if scope is None else f"account:{scope}"


def observe(event: Any) -> dict[str, Any] | None:
    """Classify one market event; keep rejection anomalies in memory."""
    if not isinstance(event, dict):
        return None
    if event.get("entry_type") not in REJECTION_ENTRY_TYPES:
        return None
    code = str(event.get("code", ""))
    record = {
        "kind": CODE_KINDS.get(code, "rejection"),
        "account_id": event.get("account_id"),
        "subject_id": event.get("subject_id"),
        "detail": f"{code} {event.get('message', '')}".strip(),
    }
    SEEN.append(record)
    return record


def record_anomaly(kind: str, subject_id: str | None, detail: str) -> str:
    """Persist one anomaly row; used by the scenario CLI process only."""
    db = sqlite3.connect(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"), timeout=30)
    try:
        row_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO anomalies(id,kind,subject_id,detail) VALUES (?,?,?,?)",
            (row_id, kind, subject_id, detail),
        )
        db.commit()
        return row_id
    finally:
        db.close()


def _fail(message: str) -> int:
    print(f"adversary: {message}", file=sys.stderr)
    return 1


def _order_payload(product_id: str, side: str, quantity: int) -> dict[str, Any]:
    return {"product_id": product_id, "side": side, "quantity": quantity, "price_cents": 1}


def _pick_spot_product(client: httpx.Client) -> str:
    response = client.get("/v1/market")
    if response.status_code != 200:
        raise RuntimeError(f"GET /v1/market -> {response.status_code}")
    products = response.json()
    if not products:
        raise RuntimeError("no open products")
    for item in products:
        if str(item.get("symbol", "")).startswith("SPOT-"):
            return str(item["id"])
    return str(products[0]["id"])


def _error_code(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return ""


async def _burst(base_url: str, key: str, product_id: str, count: int = 50) -> list[httpx.Response]:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as sender:
        return list(
            await asyncio.gather(
                *(
                    sender.post(
                        "/v1/orders",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Idempotency-Key": f"scenario-burst-{n}",
                        },
                        json=_order_payload(product_id, "buy", 1),
                    )
                    for n in range(count)
                )
            )
        )


def run(base_url: str, key: str) -> int:
    """Drive the three AC-GM-ADV-01 attacks; 0 only if all behave."""
    with httpx.Client(base_url=base_url, timeout=5) as client:
        try:
            product_id = _pick_spot_product(client)
        except RuntimeError as exc:
            return _fail(str(exc))
        headers = {"Authorization": f"Bearer {key}"}

        over = client.post(
            "/v1/orders",
            headers={**headers, "Idempotency-Key": "scenario-over-capacity"},
            json=_order_payload(product_id, "sell", 20),
        )
        if over.status_code != 422 or not hmac.compare_digest(
            _error_code(over), "INSUFFICIENT_CAPACITY"
        ):
            return _fail(f"over-capacity sell -> {over.status_code} {_error_code(over)}")
        record_anomaly(
            "over_capacity", product_id, "over-capacity spot sell rejected, no balance change"
        )
        print("attack capacity: over-capacity sell rejected with INSUFFICIENT_CAPACITY")

        first = client.post(
            "/v1/orders",
            headers={**headers, "Idempotency-Key": "scenario-same-order"},
            json=_order_payload(product_id, "buy", 1),
        )
        replay = client.post(
            "/v1/orders",
            headers={**headers, "Idempotency-Key": "scenario-same-order"},
            json=_order_payload(product_id, "buy", 1),
        )
        if (
            first.status_code not in (200, 201)
            or replay.status_code not in (200, 201)
            or replay.json().get("id") != first.json().get("id")
        ):
            return _fail("idempotent replay created a second order or failed")
        record_anomaly(
            "idempotent_replay",
            str(first.json().get("id")),
            "idempotent replay reused one Idempotency-Key, no second order",
        )
        print("attack idempotency: replay returned the same order id, no duplicate")

        responses = asyncio.run(_burst(base_url, key, product_id))
        limited = [r for r in responses if r.status_code == 429]
        if not limited or any(_error_code(r) != "RATE_LIMITED" for r in limited):
            return _fail(f"burst of 50 produced {len(limited)} HTTP 429 responses")
        record_anomaly(
            "rate_limited", None, f"burst exceeded 20 req/s: {len(limited)} x 429 rate-limited"
        )
        print(f"attack rate: burst of 50 produced {len(limited)} x 429 RATE_LIMITED")

    print("adversary scenario: capacity, idempotency, and rate anomalies recorded")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive the GridMarket adversarial scenario")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--key-env", default="GRIDMARKET_ADV_KEY")
    args = parser.parse_args(argv)
    key = os.getenv(args.key_env, "")
    if not key:
        return _fail(f"{args.key_env} is not set")
    try:
        return run(args.base_url.rstrip("/"), key)
    except httpx.HTTPError as exc:
        return _fail(f"HTTP error: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
