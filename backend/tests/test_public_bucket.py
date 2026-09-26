"""S59 public read bucket: 40 rapid GETs from one address all succeed (DEC-GM-098)."""

import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import main

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "bucket.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        db.execute("INSERT INTO accounts(id,display_name) VALUES ('member','member')")
        db.execute(
            "INSERT INTO api_keys(id,account_id,key_hash,label) VALUES (?,?,?,?)",
            ("member", "member", hashlib.sha256(b"member").hexdigest(), "member"),
        )
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) "
            "VALUES ('future','FLEX-LZ_HOUSTON-test','LZ_HOUSTON','2099-01-01T18:00:00+00:00')"
        )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s59-bucket")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s59-local-test-secret")
    with TestClient(main.create_app()) as client:
        yield client


def test_public_bucket_allows_40_rapid_reads(client):
    for _ in range(40):
        response = client.get("/v1/market/status", headers={"CF-Connecting-IP": "198.51.100.20"})
        assert response.status_code == 200
