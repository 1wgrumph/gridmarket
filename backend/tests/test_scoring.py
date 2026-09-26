"""S03: explainable, bounded opportunity scores and the NERC peak calendar."""

import ast
import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from gridmarket_server import main, scoring
from gridmarket_server.contracts import Prediction

ZONE = "LZ_HOUSTON"
HOUR = "2027-09-14T19:00:00-05:00"
FACTORS = {
    "price-spread",
    "load-pressure",
    "outage-pressure",
    "congestion-pressure",
    "heat-stress",
    "peak-period",
    "weather-alert",
}


def factor_id(name: str) -> str:
    normalized = name.lower().replace("_", "-").replace(" ", "-")
    return "weather-alert" if normalized == "weather-alerts" else normalized


def score_hour(**kwargs: object) -> Prediction:
    assert callable(getattr(scoring, "score_hour", None))
    return scoring.score_hour(**kwargs)


def on_peak(hour: datetime) -> bool:
    assert callable(getattr(scoring, "on_peak", None))
    return scoring.on_peak(hour)


def inputs(**changes: object) -> dict:
    values = {
        "zone": ZONE,
        "delivery_hour": HOUR,
        "da_price": 80.0,
        "rt_price": 50.0,
        "hub_price": 45.0,
        "load_mw": 1100.0,
        "load_mean_mw": 1000.0,
        "outage_mw": 2000.0,
        "outage_median_mw": 1600.0,
        "shadow_prices": {"HOUSTON_NORTH_345KV": 25.0},
        "temperature_f": 90.0,
        "alerts": 2,
        "fresh": True,
        "market_price": None,
    }
    values.update(changes)
    return values


def test_seit_gm_score_01_seven_signed_explained_drivers_and_value() -> None:
    result = score_hour(**inputs())
    assert isinstance(result, Prediction)
    assert result.zone == ZONE and result.delivery_hour == HOUR
    assert 0 <= result.score <= 100
    assert 0 <= result.confidence <= 1
    assert result.expected_value == pytest.approx(0.08 * (1 + 0.5 * (result.score - 50) / 50))
    drivers = {factor_id(entry["factor"]): entry for entry in result.drivers}
    assert set(drivers) == FACTORS
    assert all(isinstance(entry["contribution"], (int, float)) for entry in drivers.values())
    assert all(entry["detail"] and "\n" not in entry["detail"] for entry in drivers.values())
    assert "HOUSTON_NORTH_345KV" in drivers["congestion-pressure"]["detail"]
    assert result.score == pytest.approx(
        min(100, max(0, 50 + sum(entry["contribution"] for entry in drivers.values())))
    )


@pytest.mark.parametrize(
    ("score", "expected"), [(39.99, "LOW"), (40, "MEDIUM"), (69.99, "MEDIUM"), (70, "HIGH")]
)
def test_seit_gm_score_01_level_boundaries(score: float, expected: str) -> None:
    assert callable(getattr(scoring, "level_for_score", None))
    assert scoring.level_for_score(score) == expected


def test_seit_gm_score_01_stale_input_reduces_confidence() -> None:
    fresh = score_hour(**inputs())
    stale = score_hour(**inputs(fresh=False))
    assert 0 < fresh.confidence <= 1
    assert stale.confidence == pytest.approx(0.6 * fresh.confidence)
    assert fresh.score == stale.score


def test_seit_gm_score_02_outage_and_cited_shadow_price_are_monotone() -> None:
    for factor in ("outage_mw", "shadow_prices"):
        for step in range(20):
            low, high = 100 + 100 * step, 200 + 100 * step
            if factor == "outage_mw":
                before = inputs(outage_mw=low)
                after = inputs(outage_mw=high)
            else:
                before = inputs(shadow_prices={"HOUSTON_NORTH_345KV": low})
                after = inputs(shadow_prices={"HOUSTON_NORTH_345KV": high})
            first = score_hour(**before)
            second = score_hour(**after)
            assert second.score >= first.score, (factor, low, high)


def test_seit_gm_score_05_temperature_and_alerts_are_monotone() -> None:
    for lower, higher in ((80, 85), (84, 86), (85, 95), (95, 110)):
        assert (
            score_hour(**inputs(temperature_f=higher)).score
            >= score_hour(**inputs(temperature_f=lower)).score
        )
    for count in range(6):
        assert (
            score_hour(**inputs(alerts=count + 1)).score >= score_hour(**inputs(alerts=count)).score
        )


def test_seit_gm_score_04_five_weekdays_by_sixteen_peak_hours() -> None:
    # Mon 2026-09-28 through Fri 2026-10-02: all 5 × 16 hour endings.
    for day in range(5):
        date = datetime.fromisoformat("2026-09-28T00:00:00-05:00") + timedelta(days=day)
        for hour in range(7, 23):
            assert on_peak(date.replace(hour=hour))
            result = score_hour(**inputs(delivery_hour=date.replace(hour=hour).isoformat()))
            peak = next(d for d in result.drivers if factor_id(d["factor"]) == "peak-period")
            assert peak["contribution"] > 0
        for hour in (6, 23):
            assert not on_peak(date.replace(hour=hour))


@pytest.mark.parametrize(
    "day",
    [
        "2026-01-01",
        "2026-05-25",
        "2026-07-04",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
        "2027-01-01",
        "2027-05-31",
        "2027-07-05",
        "2027-09-06",
        "2027-11-25",
        "2027-12-25",
    ],
)
def test_seit_gm_score_04_holidays_are_off_peak(day: str) -> None:
    hour = datetime.fromisoformat(f"{day}T12:00:00-06:00")
    assert not on_peak(hour)
    result = score_hour(**inputs(delivery_hour=hour.isoformat()))
    peak = next(d for d in result.drivers if factor_id(d["factor"]) == "peak-period")
    assert peak["contribution"] < 0


def test_seit_gm_score_04_saturday_holiday_has_no_friday_observance() -> None:
    assert on_peak(datetime.fromisoformat("2026-07-03T12:00:00-05:00"))
    assert not on_peak(datetime.fromisoformat("2026-07-04T12:00:00-05:00"))
    assert not on_peak(datetime.fromisoformat("2026-10-03T12:00:00-05:00"))
    source = ast.parse(Path(scoring.__file__).read_text())
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(source)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "holidays" not in imports and "pandas" not in imports


def test_seit_gm_score_03_prediction_api_disclaimer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    with sqlite3.connect(db_path) as db:
        db.executescript(Path(scoring.__file__).with_name("schema.sql").read_text())
        hour = (datetime.now(UTC) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        db.execute(
            "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, ?, ?)",
            ("one", "HOUSTON-FLEX", ZONE, hour.isoformat()),
        )
        fetched = datetime.now(UTC).isoformat()
        for index, (report, zone, value, unit) in enumerate(
            (
                ("NP6-905-CD", ZONE, 50, "$/MWh"),
                ("NP6-905-CD", "HB_HUBAVG", 45, "$/MWh"),
                ("NP4-190-CD", ZONE, 80, "$/MWh"),
                ("NP3-565-CD", "Coast", 1100, "MW"),
                ("NP3-233-CD", ZONE, 2000, "MW"),
                ("NP6-86-CD", "HOUSTON_NORTH_345KV", 25, "$/MWh"),
                ("NWS-TEMP", ZONE, 90, "F"),
                ("NWS-ALERTS", ZONE, 2, "count"),
            )
        ):
            db.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(index), report, zone, hour.isoformat(), 60, value, unit, fetched, fetched),
            )
    predictions = scoring.predict()
    assert predictions
    assert all("simulation estimate" in p.disclaimer.lower() for p in predictions)
    assert all("not guaranteed profit" in p.disclaimer.lower() for p in predictions)

    async def read() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
        ) as client:
            return await client.get("/v1/predictions")

    response = asyncio.run(read())
    assert response.status_code == 200
    assert "simulation estimate" in response.text.lower()
    assert "not guaranteed profit" in response.text.lower()


def driver_detail(prediction: Prediction, factor: str) -> str:
    return next(entry for entry in prediction.drivers if factor_id(entry["factor"]) == factor)[
        "detail"
    ]


def seed_predictions_db(
    db_path: Path, products: list[tuple[str, str, str, str]], rows: list[tuple]
) -> None:
    with sqlite3.connect(db_path) as db:
        db.executescript(Path(scoring.__file__).with_name("schema.sql").read_text())
        db.executemany(
            "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES (?, ?, ?, ?)",
            products,
        )
        db.executemany("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


@pytest.fixture
def seeded_prediction_market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> datetime:
    db_path = tmp_path / "signals.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    now = datetime.now(UTC)
    hour = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    seed_predictions_db(
        db_path,
        [("product", "HOUSTON-FC", ZONE, hour.isoformat())],
        [
            (
                "da",
                "NP4-190-CD",
                ZONE,
                hour.isoformat(),
                60,
                50.0,
                "$/MWh",
                now.isoformat(),
                now.isoformat(),
            ),
        ],
    )
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executemany(
            "INSERT INTO accounts (id, display_name) VALUES (?, ?)",
            (("buyer", "Buyer"), ("seller", "Seller")),
        )
        db.executemany(
            "INSERT INTO orders (id, account_id, product_id, side, quantity, remaining_qty, "
            "price_cents, status) VALUES (?, ?, 'product', ?, 1, 0, 5, 'filled')",
            (("buy", "buyer", "buy"), ("sell", "seller", "sell")),
        )
        db.execute(
            "INSERT INTO trades (id, product_id, buy_order_id, sell_order_id, quantity, price_cents) "
            "VALUES ('trade', 'product', 'buy', 'sell', 1, 5)"
        )
    return hour


def test_ate_p1b_01_prediction_value_and_market_price_share_dollar_units(
    seeded_prediction_market: datetime,
) -> None:
    """A 50 $/MWh DA signal and 5-cent FC trade both yield dollars per kWh/FC."""
    (result,) = scoring.predict()
    assert result.zone == ZONE
    assert result.delivery_hour == seeded_prediction_market.isoformat()
    assert isinstance(result.expected_value, float)
    assert isinstance(result.market_price, float)
    assert 0.025 <= result.expected_value <= 0.075
    assert result.market_price == 0.05


def test_heat_stress_detail_states_threshold_position() -> None:
    above = driver_detail(score_hour(**inputs(temperature_f=90.0)), "heat-stress")
    assert above == "Temperature 90 F above 85 F threshold"
    for temperature in (85.0, 80.0):
        detail = driver_detail(score_hour(**inputs(temperature_f=temperature)), "heat-stress")
        assert detail == f"Temperature {round(temperature)} F at or below 85 F threshold"


def test_predict_shadow_prices_keep_newest_per_constraint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    seed_predictions_db(
        db_path,
        [("p1", "HOUSTON-FLEX", ZONE, HOUR)],
        [
            ("s1", "NP6-86-CD", "C1", HOUR, 5, 10, "$/MWh", HOUR, HOUR),
            ("s2", "NP6-86-CD", "C1", HOUR, 5, 125.5, "$/MWh", HOUR, HOUR),
        ],
    )
    (prediction,) = scoring.predict()
    assert driver_detail(prediction, "congestion-pressure").endswith("C1 125.5")


def test_predict_selects_signal_for_delivery_hour(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    other = "2027-09-14T20:00:00-05:00"
    unmatched = "2027-09-14T21:00:00-05:00"
    seed_predictions_db(
        db_path,
        [("p1", "HOUSTON-FLEX", ZONE, HOUR), ("p2", "HOUSTON-FLEX-2", ZONE, unmatched)],
        [
            ("s1", "NP4-190-CD", ZONE, HOUR, 60, 100, "$/MWh", HOUR, HOUR),
            ("s2", "NP4-190-CD", ZONE, other, 60, 1, "$/MWh", other, other),
        ],
    )
    predictions = {item.delivery_hour: item for item in scoring.predict()}
    assert driver_detail(predictions[HOUR], "price-spread").startswith("Day-ahead 100 vs")
    assert "unavailable" in driver_detail(predictions[unmatched], "price-spread").lower()
    assert predictions[unmatched].level == "UNAVAILABLE"


def test_predict_missing_temperature_marked_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "signals.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    seed_predictions_db(
        db_path,
        [("p1", "HOUSTON-FLEX", ZONE, HOUR)],
        [
            ("s1", "NP4-190-CD", ZONE, HOUR, 60, 80, "$/MWh", HOUR, HOUR),
        ],
    )
    (prediction,) = scoring.predict()
    heat = next(
        entry for entry in prediction.drivers if factor_id(entry["factor"]) == "heat-stress"
    )
    assert heat["contribution"] == pytest.approx(0)
    assert "0 F" not in heat["detail"]
    assert "unavailable" in heat["detail"].lower() or "missing" in heat["detail"].lower()
