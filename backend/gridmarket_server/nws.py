"""Keyless NWS forecast and severe alert polling."""

import asyncio
from datetime import UTC, datetime

import httpx

from .ercot import RequestBudget, _store, backoff_seconds, signals

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
        while not budget.try_acquire():
            await asyncio.sleep(1)
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            if attempt == 6:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
    raise RuntimeError("unreachable")


async def poll() -> None:
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
                forecast = hourly["properties"]["periods"][0]
                updated = hourly["properties"]["updated"]
                _store(
                    "NWS-TEMP",
                    zone,
                    forecast["startTime"],
                    60,
                    forecast["temperature"],
                    forecast["temperatureUnit"],
                    updated,
                )
                count = sum(
                    feature["properties"].get("severity") in {"Severe", "Extreme"}
                    for feature in alerts["features"]
                )
                published = max(
                    (feature["properties"].get("updated", "") for feature in alerts["features"]),
                    default=datetime.now(UTC).isoformat(),
                )
                _store(
                    "NWS-ALERTS", zone, datetime.now(UTC).isoformat(), 5, count, "count", published
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
                continue
