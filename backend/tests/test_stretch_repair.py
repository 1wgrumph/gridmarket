"""DEC-GM-147: Stretch assurance repair tests.

Covers:
- Review finding 1: halt/resume admin guard allows compose gateway peer with key, rejects tunnel header.
- Review finding 2: replay rate limit keys on client identity (CF-Connecting-IP), not socket peer.
- Test Engineer F2: malformed replay field types return 422 naming the field, not 500.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures.replay_test import synthetic as syn

from gridmarket_server import main

ADMIN = "gm_admin_test_key_stretch_repair_123"
GATEWAY = ("172.23.0.1", 50000)


@pytest.fixture
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "stretch_repair.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.setenv("GRIDMARKET_ADMIN_NETS", "172.23.0.0/16")
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "gm_bot_secret_stretch_repair_123")
    return db_path


# Review finding 1 (DEC-GM-147): gateway peer may halt and resume with key; tunnel is 403.
@pytest.mark.parametrize("path", ["/v1/admin/halt", "/v1/admin/resume"])
def test_dec_gm_147_gateway_peer_may_halt_and_resume(app_env, path: str):
    body = {"scope": "market", "reason": "stretch test"}
    headers = {"Authorization": f"Bearer {ADMIN}"}

    with TestClient(main.create_app(), client=GATEWAY) as client:
        # Gateway peer with valid admin key succeeds (200)
        res = client.post(path, json=body, headers=headers)
        assert res.status_code == 200, res.text

        # Tunnel header from gateway is rejected before key (403)
        res_tunnel = client.post(
            path, json=body, headers=headers | {"CF-Connecting-IP": "203.0.113.10"}
        )
        assert res_tunnel.status_code == 403, res_tunnel.text

        # Wrong key from gateway returns 401
        res_wrong = client.post(path, json=body, headers={"Authorization": "Bearer wrong_key"})
        assert res_wrong.status_code == 401, res_wrong.text


# Review finding 2 (DEC-GM-147): replay limiter honors CF-Connecting-IP.
def test_dec_gm_147_replay_limiter_keys_on_cf_connecting_ip(tmp_path, monkeypatch):
    day = "2026-06-15"
    from test_replay_api import catalog

    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        # Send 6 runs from client A through the tunnel
        for seed in range(6):
            res = api.post(
                "/v1/replay",
                json=syn.body(day, ["price_based"], [syn.asset()], seed=seed),
                headers={"CF-Connecting-IP": "198.51.100.10"},
            )
            assert res.status_code == 200, res.text

        # 7th run from client B (same TCP peer, different CF-Connecting-IP) must succeed
        res_b = api.post(
            "/v1/replay",
            json=syn.body(day, ["price_based"], [syn.asset()], seed=100),
            headers={"CF-Connecting-IP": "198.51.100.11"},
        )
        assert res_b.status_code == 200, res_b.text

        # 7th run from client A must be rate-limited (429)
        res_a_limited = api.post(
            "/v1/replay",
            json=syn.body(day, ["price_based"], [syn.asset()], seed=101),
            headers={"CF-Connecting-IP": "198.51.100.10"},
        )
        assert res_a_limited.status_code == 429
        assert res_a_limited.json()["error"]["code"] == "RATE_LIMITED"


# Test Engineer F2 (DEC-GM-147): malformed replay field types return 422, never 500.
@pytest.mark.parametrize(
    "mutation,field_name",
    [
        ({"strategies": [{}]}, "strategies"),
        (
            {
                "fleet": {
                    "assets": [
                        {
                            "asset_id": ["invalid"],
                            "provider_id": "p1",
                            "capacity_kwh": "13.5",
                            "initial_soc_kwh": "6.75",
                            "min_reserve_kwh": "2.7",
                            "max_charge_kw": "5",
                            "max_discharge_kw": "5",
                            "eta_round_trip": "0.9",
                        }
                    ]
                }
            },
            "asset_id",
        ),
        ({"fleet": {"household_load": {"intervals": None}}}, "intervals"),
    ],
)
def test_dec_gm_147_te_f2_malformed_replay_field_types(tmp_path, monkeypatch, mutation, field_name):
    day = "2026-06-15"
    from test_replay_api import catalog

    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        base = syn.body(day, ["price_based"], [syn.asset()], seed=42)
        # Apply nested mutation
        for k, v in mutation.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v

        res = syn.post(api, base)
        assert res.status_code == 422, f"Expected 422 but got {res.status_code}: {res.text}"
        data = res.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert field_name in data["error"]["message"]

