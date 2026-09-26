"""Explainable seven-factor opportunity estimates."""

import math
import os
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean, median

from .contracts import Prediction
from .ercot import CENTRAL, POLL_MINUTES, signals

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
    """NERC 5x16: hour endings HE7-HE22 on Mon-Fri Central, excluding holidays."""
    if hour.tzinfo is None:
        hour = hour.replace(tzinfo=UTC)
    local = hour.astimezone(CENTRAL)
    day = local.date()
    return (
        local.weekday() < 5
        and 7 <= local.hour + 1 <= 22
        and day not in (_holidays(day.year) | _holidays(day.year - 1))
    )


def level_for_score(score: float) -> str:
    return "LOW" if score < 40 else "MEDIUM" if score < 70 else "HIGH"


def score_hour(
    *,
    zone: str,
    delivery_hour: str,
    da_price: float | None,
    rt_price: float | None,
    hub_price: float | None,
    load_mw: float | None,
    load_mean_mw: float | None,
    outage_mw: float | None,
    outage_median_mw: float | None,
    shadow_prices: dict[str, float],
    temperature_f: float | None,
    alerts: int | None,
    fresh: bool,
    market_price: float | None,
) -> Prediction:
    hour = datetime.fromisoformat(delivery_hour)
    shadow = sum(shadow_prices.values())
    have = {
        "price-spread": da_price is not None and rt_price is not None,
        "load-pressure": load_mw is not None and load_mean_mw is not None,
        "outage-pressure": outage_mw is not None and outage_median_mw is not None,
        "congestion-pressure": rt_price is not None and hub_price is not None,
        "heat-stress": temperature_f is not None,
        "peak-period": True,
        "weather-alert": alerts is not None,
    }
    raw = {
        "price-spread": (da_price - rt_price) / PRICE_SCALE if have["price-spread"] else 0,
        "load-pressure": (load_mw - load_mean_mw) / max(0.1 * load_mean_mw, 1)
        if have["load-pressure"]
        else 0,
        "outage-pressure": (outage_mw - outage_median_mw) / (0.1 * outage_median_mw + 100)
        if have["outage-pressure"]
        else 0,
        "congestion-pressure": (rt_price - hub_price + 0.1 * shadow) / CONGESTION_SCALE
        if have["congestion-pressure"]
        else 0,
        "heat-stress": 0 if temperature_f is None else max(temperature_f - 85, 0) / HEAT_SCALE,
        "peak-period": 1 if on_peak(hour) else -1,
        "weather-alert": alerts if alerts is not None else 0,
    }

    def shown(value: float | None) -> str:
        return f"{value:g}" if value is not None else "unavailable"

    cited = ", ".join(f"{name} {value:g}" for name, value in shadow_prices.items()) or "none"
    details = {
        "price-spread": f"Day-ahead {shown(da_price)} vs real-time {shown(rt_price)} $/MWh",
        "load-pressure": f"Load {shown(load_mw)} MW vs {shown(load_mean_mw)} MW 24-hour mean",
        "outage-pressure": (
            f"Outage capacity {shown(outage_mw)} MW vs {shown(outage_median_mw)} MW median"
        ),
        "congestion-pressure": (
            f"RT vs hub spread plus constraints {cited}"
            if have["congestion-pressure"]
            else f"RT/hub prices unavailable; constraints {cited}"
        ),
        "heat-stress": (
            "Temperature reading unavailable (no NWS-TEMP signal)"
            if temperature_f is None
            else f"Temperature {temperature_f:g} F above 85 F threshold"
            if temperature_f > 85
            else f"Temperature {round(temperature_f)} F at or below 85 F threshold"
        ),
        "peak-period": "NERC 5x16 on-peak hour" if on_peak(hour) else "NERC off-peak hour",
        "weather-alert": (
            f"{alerts} active Severe or Extreme weather alerts"
            if alerts is not None
            else "Alert feed unavailable (no NWS-ALERTS signal)"
        ),
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
    available = sum(weight for name, weight in WEIGHTS.items() if have[name])
    confidence = (1 if fresh else 0.6) * agreement * available
    if any(v is None for v in (da_price, rt_price, hub_price, load_mw, outage_mw)):
        level = "UNAVAILABLE"
    else:
        level = level_for_score(score)
    expected_value = max(da_price or 0, 0) / 1000 * (1 + 0.5 * (score - 50) / 50)
    return Prediction(
        zone,
        delivery_hour,
        score,
        level,
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
        "AND julianday(interval_start)>=julianday(?) AND julianday(interval_start)<julianday(?)",
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

            def value(
                report: str, zone: str, default: float | None = None, hour: str = hour
            ) -> float | None:
                if report == "NWS-ALERTS":  # Alerts are current, not per delivery hour.
                    row = db.execute(
                        "SELECT value FROM signals WHERE report_id='NWS-ALERTS' AND zone=? "
                        "ORDER BY fetched_at DESC, rowid DESC LIMIT 1",
                        (zone,),
                    ).fetchone()
                    return row[0] if row else default
                row = db.execute(
                    "SELECT value FROM signals WHERE report_id=? AND zone=? "
                    "AND julianday(interval_start)=julianday(?) "
                    "ORDER BY fetched_at DESC, rowid DESC LIMIT 1",
                    (report, zone, hour),
                ).fetchone()
                return row[0] if row else default

            shadows = {
                name: price
                for name, price in db.execute(
                    "SELECT zone,value FROM signals WHERE report_id='NP6-86-CD' "
                    "AND julianday(interval_start)=(SELECT max(julianday(interval_start)) "
                    "FROM signals WHERE report_id='NP6-86-CD' "
                    "AND julianday(interval_start)<=julianday(?)) ORDER BY rowid ASC",
                    (hour,),
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
            load = value("NP3-565-CD", zone)
            if load is None:
                load = value("NP3-565-CD", weather_zone)
            load_mean = (
                mean(_window(db, "NP3-565-CD", zone, hour, 24, load)) if load is not None else None
            )
            outage = value("NP3-233-CD", zone)
            outage_median = (
                median(_window(db, "NP3-233-CD", zone, hour, 168, outage))
                if outage is not None
                else None
            )
            alert_count = value("NWS-ALERTS", zone)
            alerts_value = None if alert_count is None else int(alert_count)

            reports = (
                "NP6-905-CD",
                "NP4-190-CD",
                "NP3-565-CD",
                "NP3-233-CD",
                "NP6-86-CD",
                "NWS-TEMP",
                "NWS-ALERTS",
            )
            if os.getenv("GRIDMARKET_NWS") == "off":
                reports = reports[:5]  # A disabled source is absent, not stale.
            fresh = all(
                (age := signals.staleness(report)) is not None
                and age <= 2 * POLL_MINUTES[report] * 60
                for report in reports
            )
            predictions.append(
                score_hour(
                    zone=zone,
                    delivery_hour=hour,
                    da_price=value("NP4-190-CD", zone),
                    rt_price=value("NP6-905-CD", zone),
                    hub_price=value("NP6-905-CD", "HB_HUBAVG"),
                    load_mw=load,
                    load_mean_mw=load_mean,
                    outage_mw=outage,
                    outage_median_mw=outage_median,
                    shadow_prices=shadows,
                    temperature_f=value("NWS-TEMP", zone),
                    alerts=alerts_value,
                    fresh=fresh,
                    market_price=market_price,
                )
            )
    return predictions
