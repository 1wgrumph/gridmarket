"""Keyless NWS forecast and severe alert polling."""

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from .ercot import FAIL_FAST, RequestBudget, _acquire, _store, backoff_seconds, signals

logger = logging.getLogger(__name__)

FORECAST_HOURS = 48  # Store the next 48 hourly periods so delivery hours can join.

BASE_URL = "https://api.weather.gov"
USER_AGENT = "gridmarket-hackathon (github.com/1wgrumph/gridmarket)"
POINTS = {
    "LZ_HOUSTON": (29.76, -95.37),
    "LZ_NORTH": (32.78, -96.80),
    "LZ_SOUTH": (29.42, -98.49),
    "LZ_WEST": (31.99, -102.08),
}
_forecasts: dict[str, str] = {}
_next_zone = 0


async def _get(client: httpx.AsyncClient, url: str, budget: RequestBudget) -> dict:
    for attempt in range(7):
        _acquire(budget)
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in FAIL_FAST or attempt == 6:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
        except (httpx.HTTPError, ValueError):
            if attempt == 6:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
    raise RuntimeError("unreachable")


async def poll() -> None:
    try:
        await _poll()
    except Exception:
        logger.warning("nws poll failed", exc_info=True)


async def _poll() -> None:
    global _next_zone
    budget = RequestBudget(limit=6)
    zones = list(POINTS)
    async with httpx.AsyncClient(
        base_url=BASE_URL, headers={"User-Agent": USER_AGENT}, timeout=20
    ) as client:
        # ponytail: two zones per tick fit the six-request budget; rotate until all zones refresh.
        for _ in range(2):
            zone = zones[_next_zone % len(zones)]
            _next_zone += 1
            lat, lon = POINTS[zone]
            signals.mark_failed("NWS-TEMP")
            signals.mark_failed("NWS-ALERTS")
            try:
                if zone not in _forecasts or not _forecasts[zone].startswith(BASE_URL):
                    point = await _get(client, f"/points/{lat},{lon}", budget)
                    _forecasts[zone] = point["properties"]["forecastHourly"]
                hourly = await _get(client, _forecasts[zone], budget)
                alerts = await _get(client, f"/alerts/active?point={lat},{lon}", budget)
                props = hourly.get("properties", {})
                updated = (
                    hourly.get("updated")
                    or props.get("updated")
                    or props.get("updateTime")
                    or props.get("generatedAt")
                    or datetime.now(UTC).isoformat()
                )
                for forecast in (props.get("periods") or [])[:FORECAST_HOURS]:
                    if forecast.get("startTime") is None or forecast.get("temperature") is None:
                        continue
                    start = (
                        datetime.fromisoformat(forecast["startTime"]).astimezone(UTC).isoformat()
                    )
                    _store(
                        "NWS-TEMP",
                        zone,
                        start,
                        60,
                        forecast["temperature"],
                        forecast["temperatureUnit"],
                        updated,
                    )
                features = alerts.get("features") or []
                count = sum(
                    feature.get("properties", {}).get("severity") in {"Severe", "Extreme"}
                    for feature in features
                )
                sents = [
                    sent
                    for feature in features
                    if (sent := feature.get("properties", {}).get("sent"))
                ]
                published = (
                    max(sents) if sents else alerts.get("updated") or datetime.now(UTC).isoformat()
                )
                _store(
                    "NWS-ALERTS", zone, datetime.now(UTC).isoformat(), 5, count, "count", published
                )
                signals.clear_failed("NWS-TEMP")
                signals.clear_failed("NWS-ALERTS")
            except Exception:
                logger.warning("nws poll for zone %s failed", zone, exc_info=True)
                continue
