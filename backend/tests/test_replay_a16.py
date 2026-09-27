"""DEC-GM-127 A16: hand-reconciled internal simulations, not ERCOT fixtures."""

from decimal import Decimal as D

from test_replay_engine import catalog, syn, zulu

DAY = "2026-06-15"
STRATEGIES = ["fixed_schedule", "price_based", "esr_informed"]
# Q25=10, Q75=50; top four hours 12, 13, 14, 15, earlier tie first.
DAM = [D(10)] * 6 + [D(50)] * 6 + [D(100)] * 5 + [D(50)] * 7


def post(api, assets=None, **kwargs):
    payload = syn.body(DAY, STRATEGIES, assets or [syn.asset()], **kwargs)
    response = syn.post(api, payload)
    assert response.status_code == 200, response.text
    return response


def test_a16_dam_window(tmp_path, monkeypatch):
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": DAM}}) as api:
        body = post(api).json()
    assert body["procurement_hours"] == [zulu(DAY, h) for h in (12, 13, 14, 15)]
    for row in body["fleet_timeline"]["fixed_schedule"]:
        if D(row["accepted_kwh"]):
            assert zulu(DAY, 11, 45) <= row["interval_start"] < zulu(DAY, 15, 45)


def test_a16_self_supply_load_and_reserve(tmp_path, monkeypatch):
    asset = syn.asset(
        initial_soc_kwh="2",
        capacity_kwh="2",
        min_reserve_kwh="1",
        max_charge_kw="0",
        max_discharge_kw="4",
    )
    # Disable remote dispatch through procurement, preserving energy for 17:00.
    outage = {
        "type": "provider_offline",
        "provider_id": "base_sim",
        "start": zulu(DAY, 0),
        "end": zulu(DAY, 17),
    }
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": DAM, "rt": D(100)}}) as api:
        body = post(api, [asset], load_kw="2", disruptions=[outage]).json()
    row = syn.score(body, "fixed_schedule")
    assert D(row["self_supply_kwh"]) == 1
    assert row["energy_value_cents"] == 10  # 1 kWh * $100/MWh / 10
    assert D(row["end_soc_kwh"]) == 1
    decisions = [
        r
        for r in syn.flat(body, "decisions")
        if r["strategy"] == "fixed_schedule" and r["action"] == "self_supply"
    ]
    assert [D(r["kw"]) for r in decisions[:2]] == [D(2), D(2)]


def test_a16_commitments_first(tmp_path, monkeypatch):
    dam = [D(10)] * 17 + [D(100)] * 4 + [D(50)] * 3
    asset = syn.asset(initial_soc_kwh="6", capacity_kwh="6", min_reserve_kwh="1", max_charge_kw="0")
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": dam, "rt": D(100)}}) as api:
        body = post(api, [asset], load_kw="4").json()
    row = syn.score(body, "fixed_schedule")
    # 16 quarters * 25% of 4 kW * 0.25 h = 4 kWh; 1 kWh remains above reserve.
    assert D(row["delivered_kwh"]) == 4
    assert D(row["self_supply_kwh"]) == 0
    assert D(row["end_soc_kwh"]) == 2
    assert row["failed_commitments"] == 0
    assert row["energy_value_cents"] == 40
    last = next(
        r
        for r in syn.flat(body, "decisions")
        if r["strategy"] == "fixed_schedule" and r["decision_time"] == zulu(DAY, 20, 45)
    )
    assert last["action"] == "hold"  # Self-supply schedule still active; delivery has priority.
    assert D(last["config"]["current_commitment_kw"]) == 1


def test_a16_distinct_policies(tmp_path, monkeypatch):
    asset = syn.asset(
        initial_soc_kwh="3",
        capacity_kwh="3",
        min_reserve_kwh="1",
        max_charge_kw="0",
        max_discharge_kw="16",
    )
    with catalog(
        tmp_path, monkeypatch, **{DAY: {"dam": DAM, "rt": D(100), "include_esr": False}}
    ) as api:
        body = post(api, [asset], load_kw="0.1").json()
    decisions = syn.flat(body, "decisions")
    at = {r["strategy"]: r for r in decisions if r["decision_time"] == zulu(DAY, 11, 45)}
    assert D(at["fixed_schedule"]["kw"]) == 8
    # DEC-GM-136: no offers outside procurement; price self-supplies 0.1 kW
    # from 00:30 (first eligible RT) through 11:30: 45 * 0.025 = 1.125 kWh.
    # SoC 1.875, unreserved 0.875: price offers 3.5 kW. Battery-aware holds
    # its 2 kWh above reserve against the 16 kWh remaining budget (16 quarters
    # x 1.0 kWh share of the 16 kW rating): no self-supply, no 11:45 offer.
    assert D(at["price_based"]["kw"]) == D("3.5")
    assert at["esr_informed"]["action"] == "hold"
    assert D(at["esr_informed"]["kw"]) == D(0)
    assert "fallback" in at["esr_informed"]["reason"].lower()
    assert body["strategy_rules"]["esr_informed"]["display_name"] == "Battery-aware"


def test_a16_battery_aware_q50_actions(tmp_path, monkeypatch):
    # DEC-GM-127 (b): Q25=10, Q50=30, Q75=50; procurement hours 18-21.
    dam = [D(10)] * 6 + [D(30)] * 7 + [D(50)] * 5 + [D(100)] * 6
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": dam, "rt": D(40)}}) as api:
        body = post(api, [syn.asset()], load_kw="0.1").json()
    assert body["procurement_hours"] == [zulu(DAY, h) for h in (18, 19, 20, 21)]
    decisions = syn.flat(body, "decisions")
    # DEC-GM-136: RT 40 is below Q75 50, so no self-supply; overnight median
    # charging already filled the 10 kWh battery, so charge is infeasible too.
    at = {r["strategy"]: r for r in decisions if r["decision_time"] == zulu(DAY, 10, 0)}
    assert at["price_based"]["action"] == "hold"
    assert at["esr_informed"]["action"] == "hold"
    assert D(at["esr_informed"]["kw"]) == D(0)
    # RT 20 meets neither self trigger; current-hour DAM 30 meets only Q50.
    # Headroom 30 kWh keeps the 4 kW charge feasible after overnight charging.
    big = syn.asset(capacity_kwh="30", max_charge_kw="4", max_discharge_kw="4")
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": dam, "rt": D(20)}}) as api:
        body = post(api, [big], load_kw="0.1").json()
    decisions = syn.flat(body, "decisions")
    at = {r["strategy"]: r for r in decisions if r["decision_time"] == zulu(DAY, 6, 0)}
    assert at["price_based"]["action"] == "hold"
    assert at["esr_informed"]["action"] == "charge"
    assert D(at["esr_informed"]["kw"]) == D(4)


def test_a16_thousand_home_body_and_decisions(tmp_path, monkeypatch):
    assets = [syn.asset(asset_id=f"home-{i:04}") for i in range(1000)]
    with catalog(tmp_path, monkeypatch, **{DAY: {"dam": DAM}}) as api:
        response = post(api, assets)
        assert len(response.content) < 2_000_000
        body = response.json()
        assert {r["asset_id"] for r in syn.flat(body, "decisions")} == {"home-0000"}
        assert all(len(rows) == 96 for rows in body["fleet_timeline"].values())
        url = f"/v1/replay/{body['run_id']}/decisions"
        params = {
            "strategy": "price_based",
            "asset": "home-0999",
            "start": zulu(DAY, 12),
            "end": zulu(DAY, 13),
        }
        result = api.get(url, params=params)
        assert result.status_code == 200
        rows = result.json()["decisions"]
        assert len(rows) == 4
        assert len(rows) <= 500
        assert {r["asset_id"] for r in rows} == {"home-0999"}
        assert api.get(url, params={**params, "asset": "absent"}).status_code == 422
        assert api.get(url, params={**params, "end": params["start"]}).status_code == 422
        assert post(api, assets).content == response.content
