"""X3 red tests: GET /v1/router/history lists resolved forecast outcomes over time."""

import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import main

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql"


def insert(db, check_id, subject, probability, resolves_at, outcome, created_at):
    db.execute(
        "INSERT INTO router_results (id, check_id, family, subject, horizon_s, probability,"
        " band, baseline, jev_probability, created_at, resolves_at, outcome)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            uuid.uuid4().hex,
            check_id,
            "market",
            subject,
            3600,
            probability,
            "review",
            1,
            None,
            created_at,
            resolves_at,
            outcome,
        ),
    )


@pytest.fixture
def history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "x3.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        insert(
            db,
            "market:LZ_HOUSTON:2026-09-20T14:00:00+00:00",
            "LZ_HOUSTON:2026-09-20T14:00:00+00:00",
            0.8,
            "2026-09-20T15:00:00+00:00",
            1,
            "2026-09-20T13:00:00+00:00",
        )
        # Same event, later forecast wins.
        insert(
            db,
            "market:LZ_HOUSTON:2026-09-20T14:00:00+00:00",
            "LZ_HOUSTON:2026-09-20T14:00:00+00:00",
            0.6,
            "2026-09-20T15:00:00+00:00",
            1,
            "2026-09-20T13:30:00+00:00",
        )
        insert(
            db,
            "market:LZ_NORTH:2026-09-21T14:00:00+00:00",
            "LZ_NORTH:2026-09-21T14:00:00+00:00",
            0.2,
            "2026-09-21T15:00:00+00:00",
            0,
            "2026-09-21T13:00:00+00:00",
        )
        # Unresolved: never listed.
        insert(
            db,
            "market:LZ_WEST:2026-09-27T14:00:00+00:00",
            "LZ_WEST:2026-09-27T14:00:00+00:00",
            0.9,
            "2026-09-27T15:00:00+00:00",
            None,
            "2026-09-26T13:00:00+00:00",
        )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        yield path, client


def test_history_is_public_and_shaped(history) -> None:
    _, client = history
    response = client.get("/v1/router/history")
    assert response.status_code == 200
    events = response.json()["events"]
    assert events == [
        {
            "subject": "LZ_HOUSTON:2026-09-20T14:00:00+00:00",
            "zone": "LZ_HOUSTON",
            "delivery_hour": "2026-09-20T14:00:00+00:00",
            "probability": pytest.approx(0.6),
            "outcome": True,
            "brier": pytest.approx(0.16),
            "resolves_at": "2026-09-20T15:00:00+00:00",
        },
        {
            "subject": "LZ_NORTH:2026-09-21T14:00:00+00:00",
            "zone": "LZ_NORTH",
            "delivery_hour": "2026-09-21T14:00:00+00:00",
            "probability": pytest.approx(0.2),
            "outcome": False,
            "brier": pytest.approx(0.04),
            "resolves_at": "2026-09-21T15:00:00+00:00",
        },
    ]


def test_history_excludes_unresolved(history) -> None:
    _, client = history
    subjects = [e["subject"] for e in client.get("/v1/router/history").json()["events"]]
    assert "LZ_WEST:2026-09-27T14:00:00+00:00" not in subjects


def test_history_default_limit_is_50(history) -> None:
    _, client = history
    payload = client.get("/v1/router/history").json()
    assert payload["limit"] == 50
    assert payload["count"] == 2


def test_history_limit_is_bounded(history) -> None:
    _, client = history
    assert len(client.get("/v1/router/history?limit=1").json()["events"]) == 1
    assert client.get("/v1/router/history?limit=0").status_code == 422
    assert client.get("/v1/router/history?limit=201").status_code == 422
    assert client.get("/v1/router/history?limit=200").status_code == 200


def test_history_empty_db_is_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "x3empty.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        response = client.get("/v1/router/history")
    assert response.status_code == 200
    assert response.json() == {"events": [], "count": 0, "limit": 50}
