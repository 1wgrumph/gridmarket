"""Explainable seven-factor opportunity estimates."""

import math
import os
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean, median

from .contracts import Prediction
from .ercot import signals

WEIGHTS = {
    "price-spread": 0.18,
    "load-pressure": 0.18,
    "outage-pressure": 0.18,
    "congestion-pressure": 0.18,
    "heat-stress": 0.12,
    "peak-period": 0.08,
    "weather-alert": 0.08,
}
PRICE_SCALE = 50
CONGESTION_SCALE = 25
HEAT_SCALE = 10
DISCLAIMER = "Simulation estimate, not guaranteed profit."


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last = next_month - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    return day + timedelta(days=1) if day.weekday() == 6 else day


def _holidays(year: int) -> set[date]:
    return {
        _observed(date(year, 1, 1)),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }


def on_peak(hour: datetime) -> bool:
    day = hour.date()
    return (
        hour.weekday() < 5
        and 7 <= hour.hour < 23
        and day not in (_holidays(day.year) | _holidays(day.year - 1))
    )


def level_for_score(score: float) -> str:
    return "LOW" if score < 40 else "MEDIUM" if score < 70 else "HIGH"


def score_hour(
    *,
    zone: str,
    delivery_hour: str,
    da_price: float,
    rt_price: float,
    hub_price: float,
    load_mw: float,
    load_mean_mw: float,
    outage_mw: float,
    outage_median_mw: float,
    shadow_prices: dict[str, float],
    temperature_f: float,
    alerts: int,
    fresh: bool,
    market_price: float | None,
) -> Prediction:
    hour = datetime.fromisoformat(delivery_hour)
    shadow = sum(shadow_prices.values())
    raw = {
        "price-spread": (da_price - rt_price) / PRICE_SCALE,
        "load-pressure": (load_mw - load_mean_mw) / max(0.1 * load_mean_mw, 1),
        "outage-pressure": (outage_mw - outage_median_mw) / (0.1 * outage_median_mw + 100),
        "congestion-pressure": (rt_price - hub_price + 0.1 * shadow) / CONGESTION_SCALE,
        "heat-stress": max(temperature_f - 85, 0) / HEAT_SCALE,
        "peak-period": 1 if on_peak(hour) else -1,
        "weather-alert": alerts,
    }
    details = {
        "price-spread": f"Day-ahead {da_price:g} vs real-time {rt_price:g} $/MWh",
        "load-pressure": f"Load {load_mw:g} MW vs {load_mean_mw:g} MW 24-hour mean",
        "outage-pressure": f"Outage capacity {outage_mw:g} MW vs {outage_median_mw:g} MW median",
        "congestion-pressure": f"RT vs hub spread plus constraints {', '.join(f'{name} {value:g}' for name, value in shadow_prices.items()) or 'none'}",
        "heat-stress": f"Temperature {temperature_f:g} F above 85 F threshold",
        "peak-period": "NERC 5x16 on-peak hour" if on_peak(hour) else "NERC off-peak hour",
        "weather-alert": f"{alerts} active Severe or Extreme weather alerts",
    }
    drivers = [
        {
            "factor": name,
            "contribution": 50
            * weight
            * (raw[name] if name == "peak-period" else math.tanh(raw[name])),
            "detail": details[name],
        }
        for name, weight in WEIGHTS.items()
    ]
    total = sum(item["contribution"] for item in drivers)
    score = min(100, max(0, 50 + total))
    direction = 1 if total >= 0 else -1
    agreement = sum(item["contribution"] * direction >= 0 for item in drivers) / len(drivers)
    confidence = (1 if fresh else 0.6) * agreement
    expected_value = max(da_price, 0) / 1000 * (1 + 0.5 * (score - 50) / 50)
    return Prediction(
        zone,
        delivery_hour,
        score,
        level_for_score(score),
        confidence,
        expected_value,
        market_price,
        drivers,
        DISCLAIMER,
        datetime.now(UTC).isoformat(),
    )


def _window(
    db: sqlite3.Connection, report: str, zone: str, hour: str, hours: int, fallback: float
) -> list[float]:
    start = datetime.fromisoformat(hour).astimezone(UTC)
    end = (start + timedelta(hours=hours)).isoformat()
    rows = db.execute(
        "SELECT value FROM signals WHERE report_id=? AND zone=? "
        "AND interval_start>=? AND interval_start<?",
        (report, zone, start.isoformat(), end),
    ).fetchall()
    return [row[0] for row in rows] or [fallback]


def predict() -> list[Prediction]:
    path = Path(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"))
    if not path.exists():
        return []
    with sqlite3.connect(path) as db:
        products = db.execute(
            "SELECT id, zone, delivery_hour FROM products WHERE status='open'"
        ).fetchall()
        predictions = []
        for product_id, zone, hour in products:

            def value(report: str, at: str, default: float = 0) -> float:
                signal = signals.latest(report, at)
                return signal.value if signal else default

            shadows = {
                name: price
                for name, price in db.execute(
                    "SELECT zone,value FROM signals WHERE report_id='NP6-86-CD' ORDER BY rowid DESC"
                ).fetchall()
            }
            trade = db.execute(
                "SELECT price_cents FROM trades WHERE product_id=? ORDER BY created_at DESC LIMIT 1",
                (product_id,),
            ).fetchone()
            bids = db.execute(
                "SELECT max(price_cents) FROM orders WHERE product_id=? AND side='buy' AND remaining_qty>0",
                (product_id,),
            ).fetchone()[0]
            asks = db.execute(
                "SELECT min(price_cents) FROM orders WHERE product_id=? AND side='sell' AND remaining_qty>0",
                (product_id,),
            ).fetchone()[0]
            market_price = (
                trade[0] / 100
                if trade
                else (bids + asks) / 200
                if bids is not None and asks is not None
                else None
            )
            weather_zone = {
                "LZ_HOUSTON": "Coast",
                "LZ_NORTH": "North Central",
                "LZ_SOUTH": "South Central",
                "LZ_WEST": "West",
            }.get(zone, zone)
            load = value("NP3-565-CD", zone, value("NP3-565-CD", weather_zone))
            outage = value("NP3-233-CD", zone)

            reports = (
                "NP6-905-CD",
                "NP4-190-CD",
                "NP3-565-CD",
                "NP3-233-CD",
                "NP6-86-CD",
                "NWS-TEMP",
                "NWS-ALERTS",
            )
            fresh = all(
                (age := signals.staleness(report)) is not None and age <= 7200 for report in reports
            )
            predictions.append(
                score_hour(
                    zone=zone,
                    delivery_hour=hour,
                    da_price=value("NP4-190-CD", zone),
                    rt_price=value("NP6-905-CD", zone),
                    hub_price=value("NP6-905-CD", "HB_HUBAVG"),
                    load_mw=load,
                    load_mean_mw=mean(_window(db, "NP3-565-CD", zone, hour, 24, load)),
                    outage_mw=outage,
                    outage_median_mw=median(_window(db, "NP3-233-CD", zone, hour, 168, outage)),
                    shadow_prices=shadows,
                    temperature_f=value("NWS-TEMP", zone),
                    alerts=int(value("NWS-ALERTS", zone)),
                    fresh=fresh,
                    market_price=market_price,
                )
            )
    return predictions
