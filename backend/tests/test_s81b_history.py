"""S81b red tests: GET /v1/signals/history serves bounded signal history.

Contract (plan amendment A12): sorted, de-duplicated UTC observations
{interval_start, interval_end, value, unit, published_at, stale} for one
allowlisted report and zone; window at most 48 h; at most 10,000 rows;
outside those bounds 422 with the field named; public GET, no silent
truncation. Seeded rows are our own store writes, not external shapes.
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import ercot, main
from gridmarket_server.contracts import Signal

NOW = datetime(2026, 9, 26, 14, 0, 10, tzinfo=UTC)
REPORT, ZONE = "NP3-565-CD", "LZ_HOUSTON"


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ercot, "datetime", FrozenDatetime)
    db_path = tmp_path / "history.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app()) as client:
        yield client, db_path


def add(hour: datetime, value: float, fetched: datetime = NOW) -> None:
    ercot.signals.add(
        Signal(
            REPORT,
            ZONE,
            hour.isoformat(),
            60,
            value,
            "MW",
            hour.isoformat(),
            fetched.isoformat(),
        )
    )


def get(client, **params):
    return client.get("/v1/signals/history", params=params)


def test_s81b_history_returns_sorted_observations(history) -> None:
    client, _ = history
    base = NOW.replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    for hour in reversed(range(24)):  # Stored out of order; the API sorts.
        add(base + timedelta(hours=hour), 40000 + hour)
    response = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=base.isoformat(),
        end=(base + timedelta(hours=24)).isoformat(),
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 24
    assert [row["interval_start"] for row in rows] == sorted(row["interval_start"] for row in rows)
    assert set(rows[0]) == {
        "interval_start",
        "interval_end",
        "value",
        "unit",
        "published_at",
        "stale",
    }
    assert rows[0]["interval_start"] == base.isoformat()
    assert rows[0]["interval_end"] == (base + timedelta(hours=1)).isoformat()
    assert (rows[0]["value"], rows[0]["unit"]) == (40000, "MW")
    assert rows[0]["stale"] is True  # A day-old fetch is past twice the poll window.
    assert rows[-1]["stale"] is False  # The latest hour is still fresh.


def test_s81b_history_dedupes_interval_start(history) -> None:
    client, db_path = history
    hour = (NOW - timedelta(hours=2)).isoformat()
    with sqlite3.connect(db_path) as db:  # Two polls, same interval: keep the latest.
        for value, fetched in ((1000, NOW - timedelta(hours=3)), (1001, NOW)):
            db.execute(
                "INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    REPORT,
                    ZONE,
                    hour,
                    60,
                    value,
                    "MW",
                    hour,
                    fetched.isoformat(),
                ),
            )
    response = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=(NOW - timedelta(hours=3)).isoformat(),
        end=NOW.isoformat(),
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "interval_start": hour,
            "interval_end": (NOW - timedelta(hours=1)).isoformat(),
            "value": 1001,
            "unit": "MW",
            "published_at": hour,
            "stale": False,
        }
    ]


def test_s81b_history_stale_flags_old_fetches(history) -> None:
    client, _ = history
    add(NOW - timedelta(hours=3), 1000, fetched=NOW - timedelta(hours=3))
    add(NOW - timedelta(minutes=30), 1001)
    response = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=(NOW - timedelta(hours=4)).isoformat(),
        end=NOW.isoformat(),
    )
    assert response.status_code == 200
    assert [(row["value"], row["stale"]) for row in response.json()] == [
        (1000, True),
        (1001, False),
    ]


def test_s81b_history_rejects_non_allowlisted_report_and_zone(history) -> None:
    client, _ = history
    base = {"zone": ZONE, "start": NOW.isoformat(), "end": (NOW + timedelta(hours=1)).isoformat()}
    response = get(client, report_id="NP9-999-CD", **base)
    assert response.status_code == 422
    assert "report_id" in response.json()["error"]["message"]
    response = get(client, report_id=REPORT, zone="", start=base["start"], end=base["end"])
    assert response.status_code == 422
    assert "zone" in response.json()["error"]["message"]


def test_s81b_history_enforces_window_and_row_bounds(history) -> None:
    client, db_path = history
    start = NOW - timedelta(hours=48)
    response = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=start.isoformat(),
        end=(NOW + timedelta(hours=1)).isoformat(),
    )
    assert response.status_code == 422
    assert "end" in response.json()["error"]["message"]
    response = get(client, report_id=REPORT, zone=ZONE, start=NOW.isoformat(), end=NOW.isoformat())
    assert response.status_code == 422
    assert "end" in response.json()["error"]["message"]
    with sqlite3.connect(db_path) as db:  # 10,001 distinct starts inside 48 h.
        db.executemany(
            "INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    str(uuid4()),
                    REPORT,
                    ZONE,
                    (start + timedelta(seconds=17 * n)).isoformat(),
                    1,
                    1000,
                    "MW",
                    start.isoformat(),
                    NOW.isoformat(),
                )
                for n in range(10001)
            ],
        )
    over = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=start.isoformat(),
        end=(start + timedelta(hours=48)).isoformat(),
    )
    assert over.status_code == 422
    assert "end" in over.json()["error"]["message"]
    under = get(
        client,
        report_id=REPORT,
        zone=ZONE,
        start=start.isoformat(),
        end=(start + timedelta(seconds=17 * 10000)).isoformat(),
    )
    assert under.status_code == 200  # Exactly 10,000 rows is served, not truncated.
    assert len(under.json()) == 10000
