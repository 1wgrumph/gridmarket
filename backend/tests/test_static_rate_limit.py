"""DEC-GM-152 (finding XR-B-OBS-1): static dashboard files use an independent rate-limit bucket.

Verifies:
1. 40 static file requests from one IP leave the API bucket untouched (20 API calls succeed).
2. The static bucket returns 429 past its own burst (200 requests).
3. Static bucket is isolated per IP.
4. API docs (/openapi.json, /docs, /redoc) remain on the API rate-limit side.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import api as api_module
from gridmarket_server import main


@pytest.fixture
def static_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_file))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "static-test")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "static-secret")

    # Freeze limiter clock for deterministic token accounting (no wall clock dependence)
    clock = Mock(wraps=api_module.time)
    clock.monotonic.return_value = 1000.0
    monkeypatch.setattr(api_module, "time", clock)

    # Ensure dashboard/dist exists so static requests return 200
    dist = main.ROOT / "dashboard/dist"
    if not dist.is_dir():
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<!doctype html><html><body>GridMarket</body></html>")

    app = main.create_app()
    with TestClient(app) as client:
        yield client, clock


def test_dec_gm_152_static_requests_leave_api_bucket_untouched(static_client) -> None:
    client, _ = static_client
    ip_headers = {"CF-Connecting-IP": "198.51.100.50"}

    # 40 static file requests from one IP
    for _ in range(40):
        response = client.get("/", headers=ip_headers)
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Limit") == "60"

    # API bucket for this IP remains completely untouched (burst of 20 intact).
    # Next 20 non-public API calls (/openapi.json) succeed.
    for _ in range(20):
        response = client.get("/openapi.json", headers=ip_headers)
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Limit") == "10"

    # The 21st non-public API call is rate limited
    response = client.get("/openapi.json", headers=ip_headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in response.headers


def test_dec_gm_152_static_bucket_returns_429_past_burst(static_client) -> None:
    client, clock = static_client
    ip_headers = {"CF-Connecting-IP": "198.51.100.51"}

    # Static burst capacity is 200
    for i in range(200):
        response = client.get("/", headers=ip_headers)
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Limit") == "60"
        assert response.headers.get("X-RateLimit-Remaining") == str(199 - i)

    # 201st static request exceeds burst capacity
    response = client.get("/", headers=ip_headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in response.headers
    assert response.headers.get("X-RateLimit-Remaining") == "0"

    # Drive the limiter clock forward by 1 second (+60 tokens)
    clock.monotonic.return_value += 1.0

    # Next static request succeeds
    response = client.get("/", headers=ip_headers)
    assert response.status_code == 200


def test_dec_gm_152_static_bucket_isolated_per_ip(static_client) -> None:
    client, _ = static_client
    ip_a = {"CF-Connecting-IP": "198.51.100.60"}
    ip_b = {"CF-Connecting-IP": "198.51.100.61"}

    # Exhaust burst for IP A
    for _ in range(200):
        assert client.get("/", headers=ip_a).status_code == 200
    assert client.get("/", headers=ip_a).status_code == 429

    # IP B is unaffected
    assert client.get("/", headers=ip_b).status_code == 200


def test_dec_gm_152_api_docs_stay_in_api_bucket(static_client) -> None:
    client, _ = static_client
    ip_headers = {"CF-Connecting-IP": "198.51.100.70"}

    # /openapi.json has limit 10, burst 20
    for _ in range(20):
        res = client.get("/openapi.json", headers=ip_headers)
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Limit") == "10"

    res = client.get("/openapi.json", headers=ip_headers)
    assert res.status_code == 429
