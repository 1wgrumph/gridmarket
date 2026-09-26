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
import json
import logging
import os
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ORDERS_PER_WINDOW = 6
WINDOW_S = 60.0
POLL_S = 10.0
BACKOFF_S = 60.0
PRICE_CAP = 500
PEAK_HOURS = frozenset(range(12, 23))  # delivery-hour UTC covering US afternoon/evening peaks
PASS_FILE = "/tmp/gridmarket-bots-pass"  # rewritten after each pass that places an order

_limits: dict[tuple[str, int], list[float]] = {}
_warns: dict[tuple[int, int], float] = {}
_roster: list[dict[str, Any]] = []
_roster_at: float | None = None
_roster_url: str | None = None
_profiles: dict[str, dict[str, Any]] = {}
_products: list[dict[str, Any]] = []
_predictions: list[dict[str, Any]] = []
_checks: list[dict[str, Any]] = []
_signals: list[dict[str, Any]] = []
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


def _warn_rejection(index: int, status: int, code: str, now: float) -> None:
    """Log a rejection once per bot per status per window; silence hid dead bots."""
    if now - _warns.get((index, status), float("-inf")) < WINDOW_S:
        return
    _warns[(index, status)] = now
    logger.warning("bot %d order rejected: %d %s", index, status, code)


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
        _warn_rejection(index, exc.response.status_code, "", now)
        return None
    except httpx.HTTPError as exc:
        logger.warning("bot %d order failed: %s", index, exc)
        return None
    except Exception as exc:
        status = _sdk_status(exc)
        if status is None:
            raise
        _note_status(index, status, now)
        if status != 423:
            _warn_rejection(index, status, str(getattr(exc, "code", "")), now)
        return None
    if isinstance(placed, dict) and placed.get("status") == 423:
        _note_status(index, 423, now)
        return None
    return placed


def _get(base_url: str, path: str) -> Any:
    return httpx.get(f"{base_url}{path}", timeout=5).json()


def _fetch_products(base_url: str) -> list[dict[str, Any]]:
    import gridmarket

    try:
        products = gridmarket.Client(base_url).market()
    except (httpx.HTTPError, ValueError):
        return []
    except Exception as exc:
        if _sdk_status(exc) is None:
            raise
        return []
    if not isinstance(products, list):
        return []
    return [p for p in products if isinstance(p, dict) and p.get("status") == "open"]


def _roster_now(base_url: str, now: float) -> list[dict[str, Any]]:
    global _roster, _roster_at, _roster_url
    global _profiles, _products, _predictions, _checks, _signals
    if (
        _roster_url != base_url
        or _roster_at is None
        or now < _roster_at
        or now - _roster_at >= POLL_S
    ):
        _roster = _get(base_url, "/v1/bots")
        if not isinstance(_roster, list):
            raise httpx.HTTPError("roster is not a list")
        _profiles = {row["id"]: row for row in _roster if isinstance(row, dict) and "id" in row}
        _products = _fetch_products(base_url)
        try:
            predictions = _get(base_url, "/v1/predictions")
            _predictions = predictions if isinstance(predictions, list) else []
        except (httpx.HTTPError, ValueError):
            _predictions = []
        try:
            signals = _get(base_url, "/v1/signals")
            _signals = signals if isinstance(signals, list) else []
        except (httpx.HTTPError, ValueError):
            _signals = []
        try:
            router = _get(base_url, "/v1/router")
            _checks = router.get("checks", []) if isinstance(router, dict) else []
        except (httpx.HTTPError, ValueError):
            _checks = []
        _roster_at, _roster_url = now, base_url
    return _roster


def _ev_cents(pred: dict[str, Any] | None, bias: float = 0.0) -> int:
    ev = float((pred or {}).get("expected_value") or 0.0)
    return min(PRICE_CAP, max(1, round(ev * 100 * (1 + bias))))


def _pred_for(predictions: list[dict[str, Any]], zone: str, hour: str) -> dict[str, Any] | None:
    return next(
        (p for p in predictions if p.get("zone") == zone and p.get("delivery_hour") == hour),
        None,
    )


def _hour_of(product: dict[str, Any]) -> int:
    try:
        return datetime.fromisoformat(str(product.get("delivery_hour"))).hour
    except ValueError:
        return -1


def strategy_order(
    row: dict[str, Any],
    profile: dict[str, Any],
    products: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    observed: dict[str, float],
    seq: int,
) -> dict[str, Any] | None:
    """One bot's order from its dominant blend type (spec Table 11), or None to skip."""
    index = int(row["bot_index"])
    blend = profile.get("blend") or {profile.get("bot_type", "noise trader"): 1.0}
    kind = max(blend, key=lambda name: blend[name])
    traits = profile.get("traits") or {}
    household = profile.get("household") or {}
    zone = str(household.get("zone", "LZ_HOUSTON"))
    bias = float((profile.get("info") or {}).get("ev_bias", 0.0))
    risk = float(traits.get("risk appetite", 0.5))
    thresholds = profile.get("thresholds") or {}
    buy_value = float((thresholds.get("buy") or {}).get("value", 0.5))
    sell_value = float((thresholds.get("sell") or {}).get("value", 0.5))
    if int(profile.get("losses", 0)) >= 3 and float(profile.get("loss_share", 0.0)) > 0.6:
        return None  # learned caution from settled losses
    zoned = [p for p in products if p.get("zone") == zone] or products
    if not zoned:
        return None
    flex = [p for p in zoned if str(p.get("symbol", "")).startswith("FLEX-")]
    spot = [p for p in zoned if str(p.get("symbol", "")).startswith("SPOT-")]
    pick = (seq + index) % len(zoned)

    def order(product: dict[str, Any], side: str, quantity: int, price_cents: int) -> dict:
        return {
            "product_id": str(product.get("id")),
            "side": side,
            "quantity": max(1, quantity),
            "price_cents": min(PRICE_CAP, max(1, price_cents)),
        }

    if kind == "market maker":
        product = (spot or zoned)[pick % len(spot or zoned)]
        base = _ev_cents(_pred_for(predictions, zone, str(product.get("delivery_hour"))), bias)
        spread = max(1, round(base * 0.05 * (1 + risk)))
        if (seq + index) % 2:
            return order(product, "sell", 1 + int(risk * 2), base + spread)
        return order(product, "buy", 1 + int(risk * 2), base - spread)
    if kind == "score follower":
        for product in flex:
            pred = _pred_for(predictions, zone, str(product.get("delivery_hour")))
            if pred is None:
                continue
            market = pred.get("market_price") or 0.0
            if (
                pred.get("level") == "HIGH"
                and float(pred.get("confidence", 0)) > 0.75 + (0.5 - buy_value) * 0.4
                and float(pred.get("expected_value", 0)) > float(market) * 1.2
            ):
                return order(
                    product, "buy", 1 + int(float(pred["confidence"]) * 2), _ev_cents(pred)
                )
        return None
    if kind == "DART trader":
        if "DART" not in set((profile.get("info") or {}).get("families", ())):
            return None
        zoned_checks = [c for c in checks if str(c.get("subject", "")).startswith(zone + ":")]
        if not zoned_checks:
            return None
        check = zoned_checks[pick % len(zoned_checks)]
        probability = float(check.get("probability", 0.5))
        if abs(probability - 0.5) <= (0.5 - sell_value) * 0.2:
            return None
        hour = str(check.get("subject", "")).split(":", 1)[1]
        product = next((p for p in flex if p.get("delivery_hour") == hour), (flex or zoned)[0])
        side = "buy" if probability > 0.5 else "sell"
        return order(
            product,
            side,
            1 + int(abs(probability - 0.5) * 4),
            _ev_cents(_pred_for(predictions, zone, str(product.get("delivery_hour"))), bias),
        )
    if kind == "heat seller":
        peak = [p for p in spot if _hour_of(p) in PEAK_HOURS]
        if not peak:
            return None
        product = peak[pick % len(peak)]
        heat = observed.get("heat-stress", 0.0)
        return order(
            product,
            "sell",
            1 + int(risk * 2) + (1 if heat > 0 else 0),
            _ev_cents(_pred_for(predictions, zone, str(product.get("delivery_hour"))), bias),
        )
    if kind == "saver":
        if (seq + index) % 6:
            return None
        product = (spot or zoned)[pick % len(spot or zoned)]
        return order(
            product,
            "buy",
            1,
            _ev_cents(_pred_for(predictions, zone, str(product.get("delivery_hour"))), bias),
        )
    if kind == "alert reactor":
        alerted = observed.get("weather-alert", 0.0) > 0 or any(
            c.get("band") == "alert" and str(c.get("subject", "")).startswith(zone) for c in checks
        )
        if not alerted:
            return None
        product = (flex or zoned)[pick % len(flex or zoned)]
        pred = _pred_for(predictions, zone, str(product.get("delivery_hour")))
        side = "sell" if pred and float(pred.get("score", 50)) > 60 else "buy"
        return order(product, side, 1, _ev_cents(pred, bias))
    rng = random.Random(f"{index}:{seq}")
    product = rng.choice(zoned)
    base = _ev_cents(_pred_for(predictions, zone, str(product.get("delivery_hour"))), bias)
    jittered = round(base * (1 + rng.uniform(-0.2, 0.2))) if base > 1 else rng.randint(5, 15)
    return order(product, rng.choice(["buy", "sell"]), 1, jittered)


def step_all(base_url: str, clock: Any) -> int:
    """One loop pass: poll the roster, submit one strategy order per active bot."""
    import gridmarket

    now = clock.now()
    if now < _backoff_until:
        return 0
    try:
        rows = _roster_now(base_url, now)
    except httpx.HTTPError as exc:
        logger.warning("bot roster poll failed: %s", exc)
        return 0
    moment = datetime.fromtimestamp(now, UTC)
    signal_objs = [
        SimpleNamespace(
            report_id=row.get("report_id"),
            published_at=row.get("published_at", moment.isoformat()),
            value=row.get("value", 0.0),
        )
        for row in _signals
        if isinstance(row, dict)
    ]
    placed = 0
    seq = int(now // POLL_S)
    for row in rows:
        if row.get("dormant"):
            continue
        profile = _profiles.get(row.get("id", ""))
        if profile is None:
            continue
        index = int(row["bot_index"])
        bot = SimpleNamespace(index=index, info=profile.get("info") or {})
        try:
            observed = observe_signals(bot, signal_objs, moment)
        except (ValueError, TypeError):
            observed = {}
        order = strategy_order(row, profile, _products, _predictions, _checks, observed, seq)
        if order is None:
            continue
        if submit(index, gridmarket.Client(base_url, bot_key(index)), clock, order) is not None:
            placed += 1
    return placed


THRESHOLDS = (("buy", 0.0, 1.0), ("sell", 0.0, 1.0))

# Each signal family reads these stored report ids (AC-GM-BOT-05). Families do
# not equal report ids: a row labelled with the family name itself also matches.
FAMILY_REPORTS = {
    "price-spread": ("NP6-905-CD", "NP4-190-CD"),
    "load-pressure": ("NP3-565-CD",),
    "outage-pressure": ("NP3-233-CD",),
    "congestion-pressure": ("NP6-86-CD", "NP6-905-CD"),
    "heat-stress": ("NWS-TEMP",),
    "peak-period": (),
    "weather-alert": ("NWS-ALERTS",),
    "DART": ("NP4-190-CD", "NP6-905-CD"),
}


def _stamp_key(stamp: str) -> tuple[float, str]:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return (float("-inf"), stamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (moment.timestamp(), "")


def observe_signals(bot: Any, signals: list[Any], now: datetime) -> dict[str, float]:
    """Signal values visible to a bot after its family filter, delay, bias and noise."""
    families = set(bot.info.get("families", ()))
    delay = float(bot.info.get("delay_s", 0))
    bias = float(bot.info.get("ev_bias", 0.0))
    noise = float(bot.info.get("noise", 0.0))
    observed: dict[str, float] = {}
    seen: dict[str, tuple[float, str]] = {}
    for signal in signals:
        matched = sorted(
            family
            for family in families
            if signal.report_id == family or signal.report_id in FAMILY_REPORTS.get(family, ())
        )
        if not matched:
            continue
        age = (now - datetime.fromisoformat(signal.published_at)).total_seconds()
        if age < delay:
            continue
        jitter = random.Random(f"{bot.index}:{signal.report_id}:{signal.published_at}").uniform(
            -noise, noise
        )
        value = float(signal.value) * (1 + bias) * (1 + jitter)
        key = _stamp_key(signal.published_at)
        for family in matched:
            if seen.get(family) is None or key > seen[family]:
                seen[family] = key
                observed[family] = value
    return observed


def thresholds_from_ledger(db: Any, master: str, index: int) -> dict[str, dict[str, float]]:
    """Replay a bot's settled positions from the ledger; identical after restart."""
    row = db.execute(
        "SELECT account_id, profile_json FROM bots WHERE bot_index = ?", (index,)
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown bot index {index} for master {master}")
    account_id, raw = row
    rate = float(json.loads(raw).get("learning_rate", 0.0))
    states = {
        name: {"min": low, "value": (low + high) / 2, "max": high} for name, low, high in THRESHOLDS
    }
    positions = db.execute(
        "SELECT pnl_cents FROM settled_positions WHERE account_id = ? ORDER BY rowid",
        (account_id,),
    ).fetchall()
    for (pnl,) in positions:
        direction = (pnl > 0) - (pnl < 0)
        for state in states.values():
            span = state["max"] - state["min"]
            state["value"] = min(
                state["max"], max(state["min"], state["value"] + rate * span * direction)
            )
    return states


class _SystemClock:
    def now(self) -> float:
        return time.time()


def main() -> None:  # pragma: no cover - service entry point
    for name, value in list(os.environ.items()):
        if name.startswith("GRIDMARKET_") and value == "":
            del os.environ[name]
    base_url = os.getenv("GRIDMARKET_URL", "http://127.0.0.1:8000").rstrip("/")
    logger.info("bot service starting with master seed %s", os.getenv("GRIDMARKET_BOT_MASTER_SEED"))
    clock = _SystemClock()
    while True:
        try:
            if step_all(base_url, clock) > 0:
                Path(PASS_FILE).write_text(f"{time.time():.0f}")
        except Exception:
            logger.exception("bot loop pass failed")
        time.sleep(30)


if __name__ == "__main__":  # pragma: no cover - service entry point
    main()
