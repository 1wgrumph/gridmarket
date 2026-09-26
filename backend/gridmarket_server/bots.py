"""Bot loop container: polls the public bots API, trades through the SDK only.

The loop never touches the database or the market engine directly; every
order goes through ``gridmarket.Client`` with the bot's own derived key
(DES-GM-RISK). The per-bot limiter caps each bot at 6 orders per rolling 60
seconds (AC-GM-BOT-03).
"""

import base64
import hashlib
import hmac
import itertools
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ORDERS_PER_WINDOW = 6
WINDOW_S = 60.0
POLL_S = 10.0
BACKOFF_S = 60.0
FALLBACK_PRODUCT_ID = "p1"
SELL_TYPES = frozenset({"market maker", "heat seller"})

_limits: dict[tuple[str, int], list[float]] = {}
_roster: list[dict[str, Any]] = []
_roster_at: float | None = None
_roster_url: str | None = None
_product = FALLBACK_PRODUCT_ID
_backoff_until: float = 0.0
_nonce = itertools.count()


def bot_key(index: int, secret: str | None = None) -> str:
    """Derive ``gm_<32>`` from ``GRIDMARKET_BOT_SECRET`` and the bot index."""
    raw = (secret if secret is not None else os.getenv("GRIDMARKET_BOT_SECRET", "")).encode()
    digest = hmac.new(raw, f"bot:{index}".encode(), hashlib.sha256).digest()
    return "gm_" + base64.urlsafe_b64encode(digest).decode("ascii")[:32]


def _sdk_status(exc: BaseException) -> int | None:
    """HTTP status of a ``gridmarket.GridMarketError``, else None.

    The SDK is imported lazily: this module is also imported by the server
    process, where the SDK package is not installed.
    """
    try:
        import gridmarket
    except ImportError:
        return None
    error = getattr(gridmarket, "GridMarketError", None)
    if isinstance(error, type) and isinstance(exc, error):
        return int(exc.status)
    return None


def _note_status(index: int, status: int, now: float) -> None:
    global _backoff_until
    if status == 423:
        logger.warning("bot %d saw MARKET_HALTED; backing off", index)
        _backoff_until = now + BACKOFF_S


def submit(index: int, client: Any, clock: Any, order: dict[str, Any]) -> Any | None:
    """Place one order through the SDK unless the per-bot limiter blocks it."""
    now = clock.now()
    stamps = [s for s in _limits.get((client.base_url, index), []) if now - WINDOW_S < s <= now]
    if len(stamps) >= ORDERS_PER_WINDOW:
        return None
    stamps.append(now)
    _limits[(client.base_url, index)] = stamps
    try:
        placed = client.place_order(order, f"bot-{index}-{now:.3f}-{next(_nonce)}")
    except httpx.HTTPStatusError as exc:
        _note_status(index, exc.response.status_code, now)
        return None
    except httpx.HTTPError as exc:
        logger.warning("bot %d order failed: %s", index, exc)
        return None
    except Exception as exc:
        status = _sdk_status(exc)
        if status is None:
            raise
        _note_status(index, status, now)
        return None
    if isinstance(placed, dict) and placed.get("status") == 423:
        _note_status(index, 423, now)
        return None
    return placed


def _fetch_product_id(base_url: str) -> str:
    import gridmarket

    try:
        products = gridmarket.Client(base_url).market()
    except (httpx.HTTPError, ValueError):
        return FALLBACK_PRODUCT_ID
    except Exception as exc:
        if _sdk_status(exc) is None:
            raise
        return FALLBACK_PRODUCT_ID
    if isinstance(products, list) and products and isinstance(products[0], dict):
        return str(products[0].get("id", FALLBACK_PRODUCT_ID))
    return FALLBACK_PRODUCT_ID


def _roster_now(base_url: str, now: float) -> list[dict[str, Any]]:
    global _roster, _roster_at, _roster_url, _product
    if (
        _roster_url != base_url
        or _roster_at is None
        or now < _roster_at
        or now - _roster_at >= POLL_S
    ):
        _roster = httpx.get(f"{base_url}/v1/bots", timeout=5).json()
        _product = _fetch_product_id(base_url)
        _roster_at, _roster_url = now, base_url
    return _roster


def step_all(base_url: str, clock: Any) -> int:
    """One loop pass: poll the roster, submit one order per active bot."""
    import gridmarket

    now = clock.now()
    if now < _backoff_until:
        return 0
    try:
        rows = _roster_now(base_url, now)
    except httpx.HTTPError as exc:
        logger.warning("bot roster poll failed: %s", exc)
        return 0
    placed = 0
    for row in rows:
        if row.get("dormant"):
            continue
        index = int(row["bot_index"])
        side = "sell" if row.get("bot_type") in SELL_TYPES else "buy"
        order = {"product_id": _product, "side": side, "quantity": 1, "price_cents": 10}
        if submit(index, gridmarket.Client(base_url, bot_key(index)), clock, order) is not None:
            placed += 1
    return placed


class _SystemClock:
    def now(self) -> float:
        return time.time()


def main() -> None:  # pragma: no cover - service entry point
    base_url = os.getenv("GRIDMARKET_URL", "http://127.0.0.1:8000").rstrip("/")
    logger.info("bot service starting with master seed %s", os.getenv("GRIDMARKET_BOT_MASTER_SEED"))
    clock = _SystemClock()
    while True:
        try:
            step_all(base_url, clock)
        except Exception:
            logger.exception("bot loop pass failed")
        time.sleep(30)


if __name__ == "__main__":  # pragma: no cover - service entry point
    main()
