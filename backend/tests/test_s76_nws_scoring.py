"""S76 red tests: NWS horizons and alerts (R1-06, R1-13), predictions join
missing-not-zero with a bounded congestion window (R1-09, R1-10)."""

import asyncio
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gridmarket_server import ercot, nws, scoring

ZONE = "LZ_HOUSTON"
SENT = "2026-09-26T15:12:00-05:00"
TOP_UPDATED = "2026-09-26T20:47:32+00:00"


@pytest.fixture(autouse=True)
def _poller_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    nws._next_zone = 0
    nws._forecasts.clear()
    ercot._last_polled.clear()
    ercot.signals.failed.clear()
    yield
    nws._next_zone = 0
    nws._forecasts.clear()
    ercot._last_polled.clear()
    ercot.signals.failed.clear()


def hourly(periods: list[tuple[str, float]]) -> dict:
    return {
        "properties": {
            "updateTime": "2026-09-26T18:22:06+00:00",
            "periods": [
                {"startTime": start, "temperature": temp, "temperatureUnit": "F"}
                for start, temp in periods
            ],
        }
    }


def fake_nws(hourly_payload: dict, alerts_payload: dict):
    async def fake_get(_client: object, url: str, _budget: object) -> dict:
        if url.startswith("/points/"):
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/X"}}
        if "alerts" in url:
            return alerts_payload
        return hourly_payload

    return fake_get


ALERTS = {
    "updated": TOP_UPDATED,
    "features": [
        {"properties": {"severity": "Severe", "event": "Flash Flood Warning", "sent": SENT}},
        {
            "properties": {
                "severity": "Unknown",
                "event": "Air Quality Alert",
                "sent": "2026-09-26T15:47:00-05:00",
            }
        },
    ],
}


def seed_db(db_path: Path, products: list[tuple], rows: list[tuple]) -> None:
    with sqlite3.connect(db_path) as db:
        db.executescript(Path(scoring.__file__).with_name("schema.sql").read_text())
        db.executemany(
            "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, ?, ?)",
            products,
        )
        db.executemany("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def detail(prediction, factor: str) -> str:
    return next(e for e in prediction.drivers if e["factor"] == factor)["detail"]


def contribution(prediction, factor: str) -> float:
    return next(e for e in prediction.drivers if e["factor"] == factor)["contribution"]


# R1-06: every hourly period reaches its delivery hour; alerts read latest per zone.
def test_s76_r1_06_forecast_hours_reach_product_hours(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        nws,
        "_get",
        fake_nws(
            hourly(
                [
                    ("2026-09-26T15:00:00-05:00", 89.0),  # 20:00Z, not a product hour.
                    ("2026-09-26T16:00:00-05:00", 95.0),  # 21:00Z, the product hour.
                    ("2026-09-26T17:00:00-05:00", 93.0),
                ]
            ),
            {"updated": TOP_UPDATED, "features": []},
        ),
    )
    asyncio.run(nws.poll())
    stored = {
        row.interval_start
        for row in ercot.signals.series("NWS-TEMP", ZONE, "2020-01-01", "2030-01-01")
    }
    assert stored == {
        "2026-09-26T20:00:00+00:00",
        "2026-09-26T21:00:00+00:00",
        "2026-09-26T22:00:00+00:00",
    }
    seed_db(tmp_path / "signals.db", [("p1", "S", ZONE, "2026-09-26T21:00:00+00:00")], [])
    (prediction,) = [p for p in scoring.predict() if p.zone == ZONE]
    assert "95" in detail(prediction, "heat-stress")
    assert "unavailable" not in detail(prediction, "heat-stress").lower()


def test_s76_r1_06_alerts_read_latest_per_zone_not_product_hour(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        nws, "_get", fake_nws(hourly([("2026-09-26T15:00:00-05:00", 89.0)]), ALERTS)
    )
    asyncio.run(nws.poll())
    hour = (datetime.now(UTC) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    seed_db(tmp_path / "signals.db", [("p1", "S", ZONE, hour.isoformat())], [])
    (prediction,) = [p for p in scoring.predict() if p.zone == ZONE]
    assert detail(prediction, "weather-alert") == "1 active Severe or Extreme weather alerts"


# R1-13: alert published_at comes from sent (or the collection updated), never "".
def test_s76_r1_13_alert_published_at_uses_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        nws, "_get", fake_nws(hourly([("2026-09-26T15:00:00-05:00", 89.0)]), ALERTS)
    )
    asyncio.run(nws.poll())
    assert ercot.signals.latest("NWS-ALERTS", ZONE).published_at == "2026-09-26T15:47:00-05:00"


def test_s76_r1_13_empty_alerts_fall_back_to_collection_updated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        nws,
        "_get",
        fake_nws(
            hourly([("2026-09-26T15:00:00-05:00", 89.0)]),
            {"updated": TOP_UPDATED, "features": []},
        ),
    )
    asyncio.run(nws.poll())
    published = ercot.signals.latest("NWS-ALERTS", ZONE).published_at
    assert published == TOP_UPDATED


# R1-09: missing inputs are missing, not zero; level unavailable without inputs.
def signal_row(i: int, report: str, zone: str, hour: str, value: float, unit: str) -> tuple:
    now = datetime.now(UTC).isoformat()
    return (f"s{i}", report, zone, hour, 60, value, unit, now, now)


def test_s76_r1_09_no_data_level_unavailable_details_say_so(tmp_path: Path) -> None:
    hour = (datetime.now(UTC) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    seed_db(tmp_path / "signals.db", [("p1", "S", ZONE, hour.isoformat())], [])
    (prediction,) = scoring.predict()
    assert prediction.level == "UNAVAILABLE"
    for factor in ("price-spread", "load-pressure", "outage-pressure", "congestion-pressure"):
        assert "unavailable" in detail(prediction, factor).lower(), factor
        assert contribution(prediction, factor) == pytest.approx(0)
    assert "Day-ahead 0 vs real-time 0" not in detail(prediction, "price-spread")


def test_s76_r1_09_full_data_outranks_missing_data_confidence(tmp_path: Path) -> None:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    missing_hour = (base + timedelta(hours=2)).isoformat()
    full_hour = (base + timedelta(hours=3)).isoformat()
    now = datetime.now(UTC).isoformat()
    seed_db(
        tmp_path / "signals.db",
        [("p1", "S", ZONE, missing_hour), ("p2", "S2", ZONE, full_hour)],
        [
            signal_row(1, "NP4-190-CD", ZONE, full_hour, 80, "$/MWh"),
            signal_row(2, "NP6-905-CD", ZONE, full_hour, 50, "$/MWh"),
            signal_row(3, "NP6-905-CD", "HB_HUBAVG", full_hour, 45, "$/MWh"),
            signal_row(4, "NP3-565-CD", ZONE, full_hour, 1100, "MW"),
            signal_row(5, "NP3-233-CD", ZONE, full_hour, 2000, "MW"),
            ("s6", "NP6-86-CD", "C1", full_hour, 5, 25, "$/MWh", now, now),
            signal_row(7, "NWS-TEMP", ZONE, full_hour, 90, "F"),
            ("s8", "NWS-ALERTS", ZONE, now, 5, 0, "count", now, now),
        ],
    )
    by_hour = {p.delivery_hour: p for p in scoring.predict()}
    assert by_hour[missing_hour].level == "UNAVAILABLE"
    assert by_hour[full_hour].level in {"LOW", "MEDIUM", "HIGH"}
    assert by_hour[full_hour].confidence > by_hour[missing_hour].confidence


def test_s76_r1_09_partial_data_stays_unavailable(tmp_path: Path) -> None:
    hour = (datetime.now(UTC) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    seed_db(
        tmp_path / "signals.db",
        [("p1", "S", ZONE, hour.isoformat())],
        [signal_row(1, "NP4-190-CD", ZONE, hour.isoformat(), 80, "$/MWh")],
    )
    (prediction,) = scoring.predict()
    assert prediction.level == "UNAVAILABLE"
    assert "unavailable" in detail(prediction, "price-spread").lower()


# R1-10: congestion cites the latest SCED interval before the product hour only.
def test_s76_r1_10_congestion_bounded_to_latest_sced_interval(tmp_path: Path) -> None:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    hour = (base + timedelta(hours=2)).isoformat()
    now = datetime.now(UTC).isoformat()
    seed_db(
        tmp_path / "signals.db",
        [("p1", "S", ZONE, hour)],
        [
            ("s1", "NP6-86-CD", "OLD_X", base.isoformat(), 5, 1, "$/MWh", now, now),
            (
                "s2",
                "NP6-86-CD",
                "NEW_Y",
                (base + timedelta(hours=1)).isoformat(),
                5,
                5,
                "$/MWh",
                now,
                now,
            ),
        ],
    )
    (prediction,) = scoring.predict()
    text = detail(prediction, "congestion-pressure")
    assert "NEW_Y" in text and "OLD_X" not in text
