"""S66: ERCOT responses carry fields as objects; ESR stamps come from the source only."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from gridmarket_server import ercot, main

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 26, 14, 0, 10, tzinfo=UTC)
H13, H14 = "2026-09-26T13:00:00+00:00", "2026-09-26T14:00:00+00:00"


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ercot, "datetime", FrozenDatetime)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def signals_api(report: str) -> dict[str, dict]:
    async def read() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.create_app()), base_url="http://test"
        ) as client:
            return await client.get("/v1/signals")

    response = asyncio.run(read())
    assert response.status_code == 200
    return {row["zone"]: row for row in response.json() if row["report_id"] == report}


def stored(report: str) -> dict[str, tuple]:
    return {
        zone: (row["value"], row["interval_start"], row["interval_minutes"], row["unit"])
        for zone, row in signals_api(report).items()
    }


def weather(value: int) -> tuple:
    return (value, H14, 60, "MW")


@pytest.mark.parametrize(
    ("report", "fixture", "expected"),
    [
        (
            "NP6-905-CD",
            "ercot/np6-905-cd.json",
            {"LZ_HOUSTON": (48.5, H13, 15, "$/MWh"), "HB_HUBAVG": (47.25, H13, 15, "$/MWh")},
        ),
        ("NP4-190-CD", "ercot/np4-190-cd.json", {"LZ_HOUSTON": (60.75, H14, 60, "$/MWh")}),
        (
            "NP3-565-CD",
            "ercot/np3-565-cd.json",
            {
                "Coast": weather(1001),
                "North": weather(1002),
                "North Central": weather(1003),
                "East": weather(1004),
                "South Central": weather(1005),
                "Southern": weather(1006),
                "West": weather(1007),
                "Far West": weather(1008),
                "LZ_HOUSTON": weather(1001),
                "LZ_NORTH": weather(3009),
                "LZ_SOUTH": weather(2011),
                "LZ_WEST": weather(2015),
            },
        ),
        (
            "NP3-233-CD",
            "ercot/np3-233-cd.json",
            {
                "LZ_HOUSTON": (2310, H14, 60, "MW"),
                "LZ_SOUTH": (3000, H14, 60, "MW"),
                "LZ_NORTH": (4000, H14, 60, "MW"),
                "LZ_WEST": (1500, H14, 60, "MW"),
            },
        ),
        (
            "NP6-86-CD",
            "ercot/np6-86-cd.json",
            {"HOUSTON_NORTH_345KV": (125.5, "2026-09-26T14:05:13+00:00", 5, "$/MWh")},
        ),
    ],
)
def test_s66_report_fixture_with_object_fields_stores_signals(
    report: str, fixture: str, expected: dict[str, tuple]
) -> None:
    payload = load(fixture)
    assert all(isinstance(field, dict) and field["name"] for field in payload["fields"])
    ercot.parse_report(report, payload)
    assert stored(report) == expected


def test_s66_esr_fixture_stores_latest_source_stamp_and_is_fresh() -> None:
    ercot.parse_report("ESR", load("esr_charging.json"))
    row = signals_api("ESR")["ERCOT"]
    assert (row["value"], row["interval_start"]) == (-120.75, "2026-09-26T14:00:08+00:00")
    assert row["published_at"] == "2026-09-26T14:00:12Z"
    assert row["stale"] is False
    assert len(ercot.signals.series("ESR", "ERCOT", "2020-01-01", "2030-01-01")) == 1


def test_s66_esr_old_measurement_is_stale_and_unstamped_row_is_skipped() -> None:
    payload = load("esr_charging.json")
    payload["data"] = [row for row in payload["data"] if row[1] in (640.0, 999.0)]
    ercot.parse_report("ESR", payload)
    row = signals_api("ESR")["ERCOT"]
    assert (row["value"], row["interval_start"]) == (640.0, "2026-09-26T11:00:10+00:00")
    assert row["stale"] is True  # Measured 3 h before now; limit is 2 x 5 min.


def test_s66_esr_row_without_source_stamp_is_never_stored() -> None:
    payload = load("esr_charging.json")
    payload["data"] = [row for row in payload["data"] if row[0] is None]
    ercot.parse_report("ESR", payload)
    assert signals_api("ESR") == {}


def test_s66_esr_real_ercot_shape_uses_utc_exec_time() -> None:
    ercot.parse_report("ESR", load("ercot/esr-4-sec-charging-mw.json"))
    row = signals_api("ESR")["ERCOT"]
    assert (row["value"], row["interval_start"]) == (557.368765108933, "2026-09-26T14:00:06+00:00")
    assert row["stale"] is False
