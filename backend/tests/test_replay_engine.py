"""C3 red tests through POST /v1/replay. Synthetic days; no external observation."""

import importlib.util
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent / "fixtures/replay_test/synthetic.py"
_SPEC = importlib.util.spec_from_file_location("replay_synthetic", _PATH)
syn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(syn)

SCORE = (
    "strategy",
    "net_value_cents",
    "cash_net_cents",
    "energy_value_cents",
    "charging_cost_cents",
    "flexibility_bonus_cents",
    "shortfall_penalty_cents",
    "opening_energy_value_cents",
    "terminal_energy_value_cents",
    "energy_delivered_kwh",
    "requested_kwh",
    "accepted_kwh",
    "delivered_kwh",
    "shortfall_kwh",
    "min_reserve_kwh",
    "observed_min_soc_kwh",
    "start_soc_kwh",
    "end_soc_kwh",
    "reserve_breach_count",
    "attempted_reserve_violations",
    "failed_commitments",
    "assets",
)


def zulu(day: str, hour: int, minute: int = 0) -> str:
    year, month, dom = (int(part) for part in day.split("-"))
    return syn.iso(datetime(year, month, dom, hour, minute, tzinfo=syn.CHI))


@contextmanager
def catalog(tmp_path, monkeypatch, **days):
    root = tmp_path / "catalog"
    for day, options in days.items():
        syn.write_day(root, day, **(options or {}))
    with syn.client(root, monkeypatch) as api:
        yield api


def _sum(rows, field):
    return sum((syn.dec(row[field]) for row in rows), Decimal(0))


def run(api, payload):
    response = syn.post(api, payload)
    assert response.status_code == 200, response.text
    body = response.json()
    syn.assert_public(body)
    assert body["day"] == payload["day"]
    assert [row["strategy"] for row in body["scoreboard"]] == payload["strategies"]
    starts = [step["interval_start"] for step in body["timeline"]]
    assert starts == [syn.iso(start) for start, _end in syn.quarters(payload["day"])]
    settlements = syn.flat(body, "settlements")
    keys = [(row["strategy"], row["asset_id"], row["delivery_start"]) for row in settlements]
    assert len(keys) == len(set(keys))
    for row in body["scoreboard"]:
        for name in SCORE:
            assert name in row
        syn.money_ok(row)
        assert syn.dec(row["energy_delivered_kwh"]) == syn.dec(row["delivered_kwh"])
        mine = [item for item in settlements if item["strategy"] == row["strategy"]]
        assert syn.dec(row["delivered_kwh"]) == _sum(mine, "delivered_kwh")
        assert syn.dec(row["shortfall_kwh"]) == _sum(mine, "shortfall_kwh")
        assert syn.dec(row["accepted_kwh"]) == _sum(mine, "accepted_kwh")
        failed = [item for item in mine if syn.dec(item["shortfall_kwh"]) > Decimal("0.000001")]
        assert row["failed_commitments"] == len(failed)
        assert syn.dec(row["start_soc_kwh"]) == _sum(row["assets"], "start_soc_kwh")
        assert syn.dec(row["end_soc_kwh"]) == _sum(row["assets"], "end_soc_kwh")
        reserves = [syn.dec(item["min_reserve_kwh"]) for item in row["assets"]]
        assert syn.dec(row["min_reserve_kwh"]) == min(reserves)
        assert row["reserve_breach_count"] == 0
    return body


def full(asset_id="synthetic-a", provider="base_sim", discharge="144"):
    return syn.asset(
        asset_id=asset_id,
        provider_id=provider,
        capacity_kwh="10",
        initial_soc_kwh="10",
        min_reserve_kwh="1",
        max_charge_kw="4",
        max_discharge_kw=discharge,
        eta_round_trip="1",
    )


def lossy():
    return syn.asset(
        capacity_kwh="5",
        initial_soc_kwh="4.1",
        min_reserve_kwh="4",
        max_charge_kw="4",
        max_discharge_kw="14.4",
        eta_round_trip="0.81",
    )


def offline(provider, day, start_h, start_m, end_h, end_m):
    return {
        "type": "provider_offline",
        "provider_id": provider,
        "start": zulu(day, start_h, start_m),
        "end": zulu(day, end_h, end_m),
    }


def test_C3_no_action_run_scores_zero(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        body = run(
            api,
            syn.body(
                day,
                ["price_based"],
                [syn.asset(initial_soc_kwh="5", min_reserve_kwh="1", eta_round_trip="1")],
            ),
        )
    row = syn.score(body, "price_based")
    assert row["opening_energy_value_cents"] == 4
    assert row["terminal_energy_value_cents"] == 4
    assert row["net_value_cents"] == 0
    assert row["cash_net_cents"] == 0
    assert syn.dec(row["energy_delivered_kwh"]) == 0
    assert row["failed_commitments"] == 0
    assert syn.dec(row["end_soc_kwh"]) == Decimal(5)
    assert len(body["timeline"]) == 96


def test_C3_lossy_cycle_ledger(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        body = run(api, syn.body(day, ["fixed_schedule"], [lossy()]))
    row = syn.score(body, "fixed_schedule")
    assert syn.dec(row["energy_delivered_kwh"]) == Decimal("0.9")
    assert syn.dec(row["requested_kwh"]) == Decimal("0.9")
    assert syn.dec(row["accepted_kwh"]) == Decimal("0.9")
    assert syn.dec(row["shortfall_kwh"]) == 0
    assert row["energy_value_cents"] == 1
    assert row["charging_cost_cents"] == 1
    assert row["flexibility_bonus_cents"] == 1
    assert row["shortfall_penalty_cents"] == 0
    assert row["opening_energy_value_cents"] == 0
    assert row["terminal_energy_value_cents"] == 0
    assert row["net_value_cents"] == 1
    assert syn.dec(row["end_soc_kwh"]) == Decimal(4)
    assert syn.dec(row["observed_min_soc_kwh"]) == Decimal(4)
    assert row["attempted_reserve_violations"] == 15
    assert row["failed_commitments"] == 0


def test_R3_half_even_subcent_rounds_once_per_component(tmp_path, monkeypatch):
    day = "2026-06-17"
    root = tmp_path / "catalog"
    syn.write_day(root, day, dam=Decimal(0), rt=Decimal(0), rt_at={zulu(day, 0, 0): Decimal(25)})
    payload = syn.body(
        day,
        ["fixed_schedule"],
        [
            syn.asset(
                capacity_kwh="1",
                initial_soc_kwh="0",
                min_reserve_kwh="0",
                max_charge_kw="4",
                max_discharge_kw="0",
                eta_round_trip="1",
            )
        ],
    )
    with syn.client(root, monkeypatch) as api:
        row = syn.score(run(api, payload), "fixed_schedule")
    assert row["charging_cost_cents"] == 2
    assert row["energy_value_cents"] == 0
    assert row["net_value_cents"] == -2
    assert syn.dec(row["end_soc_kwh"]) == Decimal(1)


def test_R3_negative_spp_keeps_sign(tmp_path, monkeypatch):
    day = "2026-06-16"
    root = tmp_path / "catalog"
    syn.write_day(root, day, rt=Decimal(10), rt_at={zulu(day, 17, 0): Decimal(-40)})
    with syn.client(root, monkeypatch) as api:
        row = syn.score(run(api, syn.body(day, ["fixed_schedule"], [lossy()])), "fixed_schedule")
    assert row["energy_value_cents"] == -4
    assert row["charging_cost_cents"] == 1
    assert row["flexibility_bonus_cents"] == 1
    assert row["net_value_cents"] == -4
    assert row["cash_net_cents"] == -4


def test_C3_half_even_sums_assets_before_rounding(tmp_path, monkeypatch):
    day = "2026-06-18"
    root = tmp_path / "catalog"
    syn.write_day(root, day, dam=Decimal(0), rt=Decimal(0), rt_at={zulu(day, 17, 0): Decimal(10)})
    spec = {
        "capacity_kwh": "0.5",
        "initial_soc_kwh": "0.5",
        "min_reserve_kwh": "0",
        "max_charge_kw": "4",
        "max_discharge_kw": "8",
        "eta_round_trip": "1",
    }
    with syn.client(root, monkeypatch) as api:
        alone = syn.score(
            run(api, syn.body(day, ["fixed_schedule"], [syn.asset(**spec)])),
            "fixed_schedule",
        )
        pair = syn.score(
            run(
                api,
                syn.body(
                    day,
                    ["fixed_schedule"],
                    [syn.asset(**spec), syn.asset(asset_id="synthetic-b", **spec)],
                ),
            ),
            "fixed_schedule",
        )
    assert alone["energy_value_cents"] == 0
    assert alone["flexibility_bonus_cents"] == 0
    assert alone["net_value_cents"] == 0
    assert pair["energy_value_cents"] == 1
    assert pair["flexibility_bonus_cents"] == 1
    assert pair["net_value_cents"] == 2


def test_C3_pro_rata_oversubscribed(tmp_path, monkeypatch):
    day = "2026-06-15"
    assets = [
        syn.asset(
            asset_id="synthetic-a",
            capacity_kwh="10",
            initial_soc_kwh="10",
            min_reserve_kwh="0",
            max_discharge_kw="4",
            eta_round_trip="1",
        ),
        syn.asset(
            asset_id="synthetic-b",
            capacity_kwh="10",
            initial_soc_kwh="10",
            min_reserve_kwh="0",
            max_discharge_kw="4",
            eta_round_trip="1",
        ),
    ]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        taken = [
            syn.dec(row["accepted_kwh"])
            for row in syn.flat(run(api, syn.body(day, ["fixed_schedule"], assets)), "settlements")
            if syn.dec(row["accepted_kwh"]) > 0
        ]
    assert taken == [Decimal("0.25")] * 32


def test_C3_undersubscribed_is_not_a_failure(tmp_path, monkeypatch):
    day = "2026-06-15"
    asset = syn.asset(
        capacity_kwh="0.1",
        initial_soc_kwh="0.1",
        min_reserve_kwh="0",
        max_discharge_kw="4",
        eta_round_trip="1",
    )
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        row = syn.score(run(api, syn.body(day, ["fixed_schedule"], [asset])), "fixed_schedule")
    assert syn.dec(row["accepted_kwh"]) == Decimal("0.1")
    assert syn.dec(row["delivered_kwh"]) == Decimal("0.1")
    assert row["failed_commitments"] == 0
    assert row["shortfall_penalty_cents"] == 0


def test_C3_residual_quantum_goes_to_lowest_asset_id(tmp_path, monkeypatch):
    day = "2026-06-15"
    power = "1.000008"
    assets = [
        syn.asset(
            asset_id=name,
            capacity_kwh="5",
            initial_soc_kwh="5",
            min_reserve_kwh="0",
            max_discharge_kw=power,
            eta_round_trip="1",
        )
        for name in ("synthetic-a", "synthetic-b", "synthetic-c")
    ]
    offers = {asset["asset_id"]: Decimal(power) * Decimal("0.25") for asset in assets}
    demand = Decimal("0.0625") * Decimal(power) * 3
    expected = syn.allocate(demand, offers)
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        body = run(api, syn.body(day, ["fixed_schedule"], assets))
    peak = zulu(day, 17, 0)
    got = {
        row["asset_id"]: syn.dec(row["accepted_kwh"])
        for row in syn.flat(body, "settlements")
        if row["delivery_start"] == peak
    }
    assert got == expected
    assert got["synthetic-a"] == Decimal("0.062501")
    assert got["synthetic-b"] == got["synthetic-c"] == Decimal("0.062500")


def test_C3_reservation_across_consecutive_commitments(tmp_path, monkeypatch):
    day = "2026-06-15"
    asset = syn.asset(
        capacity_kwh="0.3",
        initial_soc_kwh="0.3",
        min_reserve_kwh="0",
        max_discharge_kw="4",
        eta_round_trip="1",
    )
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        body = run(api, syn.body(day, ["fixed_schedule"], [asset]))
    accepted = sorted(
        syn.dec(row["accepted_kwh"])
        for row in syn.flat(body, "settlements")
        if syn.dec(row["accepted_kwh"]) > 0
    )
    row = syn.score(body, "fixed_schedule")
    assert accepted == [Decimal("0.05"), Decimal("0.25")]
    assert syn.dec(row["delivered_kwh"]) == Decimal("0.3")
    assert row["failed_commitments"] == 0
    assert syn.dec(row["end_soc_kwh"]) == 0


def _money(api, day, assets, disruptions):
    return syn.score(
        run(api, syn.body(day, ["fixed_schedule"], assets, disruptions=disruptions)),
        "fixed_schedule",
    )


def test_C3_outage_at_delivery_keeps_the_liability(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        base = _money(api, day, [full()], [])
        during = _money(api, day, [full()], [offline("base_sim", day, 17, 0, 17, 15)])
        blocked = _money(api, day, [full()], [offline("base_sim", day, 16, 45, 17, 0)])
        covered = _money(api, day, [full()], [offline("base_sim", day, 17, 0, 21, 0)])
    assert syn.dec(base["delivered_kwh"]) == 9
    assert base["failed_commitments"] == 0
    assert base["net_value_cents"] == 9
    assert syn.dec(during["delivered_kwh"]) == 9
    assert syn.dec(during["shortfall_kwh"]) == 9
    assert during["shortfall_penalty_cents"] == 90
    assert during["failed_commitments"] == 1
    assert during["net_value_cents"] == -81
    assert syn.dec(during["end_soc_kwh"]) == 1
    assert syn.dec(blocked["delivered_kwh"]) == 9
    assert blocked["failed_commitments"] == 0
    assert blocked["shortfall_penalty_cents"] == 0
    assert blocked["net_value_cents"] == 9
    assert syn.dec(covered["delivered_kwh"]) == 0
    assert syn.dec(covered["shortfall_kwh"]) == 9
    assert covered["shortfall_penalty_cents"] == 90
    assert covered["net_value_cents"] == -90
    assert syn.dec(covered["end_soc_kwh"]) == 10


def _delivered_at(body, day, hour, minute):
    stamp = zulu(day, hour, minute)
    return [
        row
        for row in syn.flat(body, "settlements")
        if row["delivery_start"] == stamp and syn.dec(row["delivered_kwh"]) > 0
    ]


def test_C3_outage_windows_are_distinct(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        base = run(api, syn.body(day, ["fixed_schedule"], [full()]))
        during = run(
            api,
            syn.body(
                day,
                ["fixed_schedule"],
                [full()],
                disruptions=[offline("base_sim", day, 17, 0, 17, 15)],
            ),
        )
        blocked = run(
            api,
            syn.body(
                day,
                ["fixed_schedule"],
                [full()],
                disruptions=[offline("base_sim", day, 16, 45, 17, 0)],
            ),
        )
    assert _delivered_at(base, day, 17, 0)
    assert not _delivered_at(blocked, day, 17, 0)
    assert _delivered_at(blocked, day, 17, 15)
    assert not _delivered_at(during, day, 17, 0)
    assert _delivered_at(during, day, 17, 30)
    short = [
        row for row in syn.flat(during, "settlements") if row["delivery_start"] == zulu(day, 17, 0)
    ]
    assert len(short) == 1
    assert short[0]["cause"] == "provider_offline"
    assert syn.dec(short[0]["shortfall_kwh"]) == 9


def test_C3_overlapping_outages_merge_once(tmp_path, monkeypatch):
    day = "2026-06-15"
    one = [offline("base_sim", day, 17, 0, 21, 0)]
    overlap = [
        offline("base_sim", day, 17, 0, 19, 0),
        offline("base_sim", day, 18, 0, 21, 0),
    ]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        single = _money(api, day, [full()], one)
        merged = _money(api, day, [full()], overlap)
    assert merged["net_value_cents"] == single["net_value_cents"] == -90
    assert merged["failed_commitments"] == 1
    assert merged["shortfall_penalty_cents"] == 90


def test_C3_partial_outage_settles_exactly_once(tmp_path, monkeypatch):
    day = "2026-06-15"
    assets = [full("synthetic-a", "base_sim"), full("synthetic-b", "other_sim")]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        body = run(
            api,
            syn.body(
                day,
                ["fixed_schedule"],
                assets,
                disruptions=[offline("other_sim", day, 17, 0, 21, 0)],
            ),
        )
    row = syn.score(body, "fixed_schedule")
    assert syn.dec(row["delivered_kwh"]) == 9
    assert syn.dec(row["shortfall_kwh"]) == 9
    assert row["failed_commitments"] == 1
    assert row["shortfall_penalty_cents"] == 90
    assert row["energy_value_cents"] == 9
    assert row["flexibility_bonus_cents"] == 9
    assert row["opening_energy_value_cents"] == 18
    assert row["terminal_energy_value_cents"] == 9
    assert row["net_value_cents"] == -81
    by_id = {item["asset_id"]: item for item in row["assets"]}
    assert syn.dec(by_id["synthetic-a"]["end_soc_kwh"]) == 1
    assert syn.dec(by_id["synthetic-b"]["end_soc_kwh"]) == 10
    shorts = [item for item in syn.flat(body, "settlements") if item["cause"] == "provider_offline"]
    assert len(shorts) == 1
    assert shorts[0]["asset_id"] == "synthetic-b"


def test_C3_feed_interrupt_does_not_block_fixed_schedule_dispatch(tmp_path, monkeypatch):
    day = "2026-06-15"
    start, end = syn.local_bounds(day)
    interrupt = {
        "type": "feed_interrupt",
        "source": "rt_spp",
        "start": syn.iso(start),
        "end": syn.iso(end),
    }
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        base = _money(api, day, [full()], [])
        lost_body = run(api, syn.body(day, ["fixed_schedule"], [full()], disruptions=[interrupt]))
    lost = syn.score(lost_body, "fixed_schedule")
    assert lost["net_value_cents"] == base["net_value_cents"]
    assert syn.dec(lost["delivered_kwh"]) == syn.dec(base["delivered_kwh"]) == 9
    noon = zulu(day, 12, 0)
    decisions = [
        row
        for row in syn.flat(lost_body, "decisions")
        if row["decision_time"] == noon and row["strategy"] == "fixed_schedule"
    ]
    assert decisions
    rt_inputs = [item for item in decisions[0]["inputs"] if item["source"] == "rt_spp"]
    assert all(Decimal(str(item["value"])) != 0 for item in rt_inputs)


def test_C3_feed_interrupt_esr_changes_esr_informed(tmp_path, monkeypatch):
    day = "2026-07-01"
    root = tmp_path / "catalog"
    syn.write_day(
        root,
        day,
        rt=Decimal(40),
        rt_at={zulu(day, 16, 30): Decimal(200)},
        dam=syn.esr_dam(day),
        esr=Decimal(-50),
        esr_at={zulu(day, 16, 15): Decimal(-80), zulu(day, 16, 30): Decimal(-20)},
    )
    asset = syn.asset(
        capacity_kwh="10",
        initial_soc_kwh="10",
        min_reserve_kwh="1",
        max_charge_kw="4",
        max_discharge_kw="16",
        eta_round_trip="1",
    )
    interrupt = {
        "type": "feed_interrupt",
        "source": "esr",
        "start": zulu(day, 16, 0),
        "end": zulu(day, 17, 0),
    }
    with syn.client(root, monkeypatch) as api:
        plain = syn.score(run(api, syn.body(day, ["esr_informed"], [asset])), "esr_informed")
        lost_body = run(api, syn.body(day, ["esr_informed"], [asset], disruptions=[interrupt]))
        lost = syn.score(lost_body, "esr_informed")
    assert plain["energy_value_cents"] == 4
    assert syn.dec(plain["delivered_kwh"]) == 1
    assert syn.dec(plain["end_soc_kwh"]) == 9
    assert lost["energy_value_cents"] == 0
    assert syn.dec(lost["delivered_kwh"]) == 0
    assert syn.dec(lost["end_soc_kwh"]) == 10
    assert lost["charging_cost_cents"] == plain["charging_cost_cents"] == 0
    when = zulu(day, 16, 45)
    decision = next(
        row
        for row in syn.flat(lost_body, "decisions")
        if row["decision_time"] == when and row["strategy"] == "esr_informed"
    )
    assert decision["action"] == "hold"
    assert "fallback" in decision["reason"].lower()


def test_C3_strategy_copies_are_isolated(tmp_path, monkeypatch):
    day = "2026-06-15"
    fleet = [lossy()]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        both = run(api, syn.body(day, ["fixed_schedule", "price_based"], fleet))
        fixed = syn.score(run(api, syn.body(day, ["fixed_schedule"], fleet)), "fixed_schedule")
        price = syn.score(run(api, syn.body(day, ["price_based"], fleet)), "price_based")
    assert syn.score(both, "fixed_schedule")["net_value_cents"] == fixed["net_value_cents"] == 1
    assert syn.score(both, "price_based")["net_value_cents"] == price["net_value_cents"] == 0
    assert syn.dec(syn.score(both, "price_based")["end_soc_kwh"]) == Decimal("4.1")
    assert syn.dec(syn.score(both, "fixed_schedule")["end_soc_kwh"]) == Decimal(4)


@pytest.mark.parametrize(
    ("day", "count", "esr"),
    [("2026-03-08", 92, False), ("2026-11-01", 100, True)],
)
def test_R3_dst_day_quarter_count(tmp_path, monkeypatch, day, count, esr):
    with catalog(tmp_path, monkeypatch, **{day: {"include_esr": esr}}) as api:
        body = run(api, syn.body(day, ["price_based"], [syn.asset()]))
    starts = [step["interval_start"] for step in body["timeline"]]
    assert len(starts) == count
    if day == "2026-11-01":
        assert "2026-11-01T06:00:00Z" in starts
        assert "2026-11-01T07:00:00Z" in starts
    else:
        hours = {datetime.fromisoformat(stamp).astimezone(syn.CHI).hour for stamp in starts}
        assert 2 not in hours


def test_R5_repeated_responses_are_byte_identical(tmp_path, monkeypatch):
    day = "2026-06-15"
    payload = syn.body(day, ["fixed_schedule"], [full()], seed=7)
    flipped = {key: payload[key] for key in reversed(payload)}
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        first = syn.post(api, payload)
        assert first.status_code == 200, first.text
        for _ in range(4):
            again = syn.post(api, payload)
            assert again.content == first.content
        assert syn.post(api, flipped).content == first.content
        body = first.json()
        assert body["run_id"] == syn.run_id_of(body["binding"])
        assert body["binding"]["seed"] == 7
        assert body["binding"]["day"] == day
        assert len(body["binding"]["dataset_digest"]) == 64
        other = syn.post(api, syn.body(day, ["fixed_schedule"], [full()], seed=8))
        assert other.status_code == 200
        assert other.json()["run_id"] != body["run_id"]
        fetched = api.get(f"/v1/replay/{body['run_id']}")
        assert fetched.status_code == 200
        assert fetched.content == first.content
        syn.no_timing_keys(body)
