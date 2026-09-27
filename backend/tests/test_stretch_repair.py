"""DEC-GM-147: Stretch assurance repair tests.

Covers:
- Review finding 1: halt/resume admin guard allows compose gateway peer with key, rejects tunnel header.
- Review finding 2: replay rate limit keys on client identity (CF-Connecting-IP), not socket peer.
- Test Engineer F2: malformed replay field types return 422 naming the field, not 500.
"""

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures.replay_test import synthetic as syn

from gridmarket_server import ercot, main

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


# ORC-2 (DEC-GM-148): parse_hour_ending accepts int, H:MM and HH:MM; rejects other shapes.
def test_dec_gm_148_orc_2_hour_ending_root_parsing():
    # Valid ints (1..25)
    assert ercot.parse_hour_ending(1) == 1
    assert ercot.parse_hour_ending(12) == 12
    assert ercot.parse_hour_ending(24) == 24
    assert ercot.parse_hour_ending(25) == 25

    # Valid strings H:MM and HH:MM
    assert ercot.parse_hour_ending("1:00") == 1
    assert ercot.parse_hour_ending("01:00") == 1
    assert ercot.parse_hour_ending("9:00") == 9
    assert ercot.parse_hour_ending("09:00") == 9
    assert ercot.parse_hour_ending("24:00") == 24
    assert ercot.parse_hour_ending("25:00") == 25

    # Rejection of booleans
    with pytest.raises(TypeError, match="hourEnding"):
        ercot.parse_hour_ending(True)
    with pytest.raises(TypeError, match="hourEnding"):
        ercot.parse_hour_ending(False)

    # Rejection of invalid strings
    for bad in ["1:", "01", "24", "1:0", "1:000", "abc", "26:00", "0:00", ""]:
        with pytest.raises(ValueError, match="hourEnding"):
            ercot.parse_hour_ending(bad)

    # Rejection of out of range ints
    for bad_int in [0, 26, -1]:
        with pytest.raises(ValueError, match="hourEnding"):
            ercot.parse_hour_ending(bad_int)

    # Rejection of other types
    for bad_type in [None, [1], {"hour": 1}]:
        with pytest.raises(TypeError, match="hourEnding"):
            ercot.parse_hour_ending(bad_type)


def _find_fixture(filename: str) -> Path:
    fixture = Path(__file__).parent / "fixtures/ercot/captured" / filename
    if fixture.exists():
        return fixture
    raise FileNotFoundError(f"Fixture {filename} not found")


# ORC-2 (DEC-GM-148): captured NP3-565 page with "1:00" parses without raising ValueError.
def test_dec_gm_148_orc_2_np3_565_captured_page_parses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "test_565.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))

    fixture_path = _find_fixture("NP3-565-CD__q0__p1.json")
    payload = json.loads(fixture_path.read_text())

    # This previously raised ValueError: invalid literal for int() with base 10: '1:'
    pages = ercot.parse_report("NP3-565-CD", payload)
    assert pages >= 1

    with sqlite3.connect(db_path) as db:
        count = db.execute("SELECT COUNT(*) FROM signals WHERE report_id='NP3-565-CD'").fetchone()[
            0
        ]
        assert count > 0, "Expected stored signals from captured NP3-565-CD page"


# ORC-3 (DEC-GM-148): parse_report batches pages; NP3-233-CD finishes in under 3s with identical semantics.
def test_dec_gm_148_orc_3_parse_report_batching_speed_and_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "test_233.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))

    fixture_path = _find_fixture("NP3-233-CD__q0__p1.json")
    payload = json.loads(fixture_path.read_text())

    start_time = time.perf_counter()
    pages = ercot.parse_report("NP3-233-CD", payload)
    elapsed = time.perf_counter() - start_time

    assert pages >= 1
    # Target under 3s on this machine (unbatched was ~42s)
    assert elapsed < 3.0, f"NP3-233-CD took {elapsed:.2f}s, expected < 3.0s"

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT report_id, zone, interval_start, interval_minutes, unit FROM signals "
            "WHERE report_id='NP3-233-CD' ORDER BY interval_start, zone"
        ).fetchall()
        assert len(rows) > 0
        # All rows should have report_id NP3-233-CD, 60 minutes, unit MW
        for r in rows:
            assert r["report_id"] == "NP3-233-CD"
            assert r["interval_minutes"] == 60
            assert r["unit"] == "MW"
            assert r["zone"] in ("LZ_SOUTH", "LZ_NORTH", "LZ_WEST", "LZ_HOUSTON")
