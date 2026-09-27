"""DEC-GM-152: snapshot series are readable through GET /v1/signals/history.

Review 1 (backend), review 2, UX F2, ORC-9: the poll stores SNAPSHOT-HUBS,
SNAPSHOT-SCED and SNAPSHOT-DEMAND via parse_snapshot, so the history route
must serve them with the same bounds as the polled reports. Stored here via
the real parser, read back through the real HTTP route.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import ercot, main

NOW = datetime(2026, 9, 26, 14, 0, 10, tzinfo=UTC)
HUBS = ["HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"]


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def snapshot_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ercot, "datetime", FrozenDatetime)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "snapshot.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app()) as client:
        yield client


def store_two_snapshots() -> None:
    for hour, price in ((2, 48.5), (1, 51.25)):
        at = (NOW - timedelta(hours=hour)).isoformat()
        ercot.parse_snapshot(
            {
                "asOf": at,
                "demand": {"mw": 70000.0 + hour},
                "hubs": [{"hub": hub, "price": price + i} for i, hub in enumerate(HUBS)],
                "dam": {"hub": "HB_NORTH", "price": 60.75},
                "sced": {"systemLambda": 36.5 + hour},
            }
        )


def get(client, report_id, zone, start, end):
    return client.get(
        "/v1/signals/history",
        params={"report_id": report_id, "zone": zone, "start": start, "end": end},
    )


def test_snapshot_series_read_back_through_history(snapshot_history) -> None:
    client = snapshot_history
    store_two_snapshots()
    start = (NOW - timedelta(hours=3)).isoformat()
    end = NOW.isoformat()
    cases = [
        ("SNAPSHOT-HUBS", "HB_HOUSTON", [48.5, 51.25], "$/MWh"),
        ("SNAPSHOT-HUBS", "HB_NORTH", [49.5, 52.25], "$/MWh"),
        ("SNAPSHOT-HUBS", "HB_SOUTH", [50.5, 53.25], "$/MWh"),
        ("SNAPSHOT-HUBS", "HB_WEST", [51.5, 54.25], "$/MWh"),
        ("SNAPSHOT-SCED", "lambda", [38.5, 37.5], "$/MWh"),
        ("SNAPSHOT-DEMAND", "ERCOT", [70002.0, 70001.0], "MW"),
    ]
    for report_id, zone, values, unit in cases:
        response = get(client, report_id, zone, start, end)
        assert response.status_code == 200, (report_id, zone, response.text)
        rows = response.json()
        assert [row["value"] for row in rows] == values
        assert [row["interval_start"] for row in rows] == sorted(
            row["interval_start"] for row in rows
        )
        assert set(rows[0]) == {
            "interval_start",
            "interval_end",
            "value",
            "unit",
            "published_at",
            "stale",
        }
        assert all(row["unit"] == unit for row in rows)


def test_snapshot_history_keeps_today_bounds(snapshot_history) -> None:
    client = snapshot_history
    store_two_snapshots()
    response = get(
        client,
        "SNAPSHOT-HUBS",
        "HB_HOUSTON",
        (NOW - timedelta(hours=48)).isoformat(),
        (NOW + timedelta(hours=1)).isoformat(),
    )
    assert response.status_code == 422
    assert "end" in response.json()["error"]["message"]
    response = get(
        client, "NP9-999-CD", "HB_HOUSTON", (NOW - timedelta(hours=1)).isoformat(), NOW.isoformat()
    )
    assert response.status_code == 422
    assert "report_id" in response.json()["error"]["message"]
