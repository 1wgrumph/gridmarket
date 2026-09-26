"""C2 red tests. Fixed examples; synthetic prices, not external observations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from gridmarket_server.flex import (
    Battery,
    Decision,
    EsrInformed,
    FeedWindow,
    FixedSchedule,
    InformationSet,
    Observation,
    PriceBased,
)

CHI = ZoneInfo("America/Chicago")


def z(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=CHI).astimezone(UTC)


# Local hour -> $/MWh for 2026-06-15. Nearest-rank Q25=10 (tie), Q75=100 (tie).
# Linear interpolation of this sample would put Q25 at 40; the input must be 10.
PRICES = (
    [Decimal(1)] * 4
    + [Decimal(10)] * 2
    + [Decimal(200)]
    + [Decimal(50)] * 11
    + [Decimal(100)] * 2
    + [Decimal(200)] * 4
)
PUBLISHED = z(2026, 6, 14, 13, 30)
POLICIES = (FixedSchedule, PriceBased, EsrInformed)


def nearest_rank(values: list[Decimal], percentile: int) -> Decimal:
    ordered = sorted(values)
    rank = (percentile * len(ordered) + 99) // 100
    return ordered[rank - 1]


def battery(**overrides) -> Battery:
    fields = {
        "asset_id": "synthetic-asset",
        "capacity_kwh": Decimal(20),
        "soc_kwh": Decimal(10),
        "max_charge_kw": Decimal(4),
        "max_discharge_kw": Decimal(4),
        "eta_round_trip": Decimal(1),
        "min_reserve_kwh": Decimal(1),
        "label": "synthetic",
    }
    fields.update(overrides)
    return Battery(**fields)


def obs(**overrides) -> Observation:
    start = z(2026, 6, 15, 0, 0)
    fields = {
        "series": "dam_spp",
        "source": "dam_spp",
        "value": Decimal(10),
        "unit": "USD/MWh",
        "interval_start": start,
        "interval_end": start + timedelta(hours=1),
        "published_at": PUBLISHED,
        "available_at": PUBLISHED,
        "quality": "synthetic",
        "zone": "LZ_HOUSTON",
        "settlement_point": "LZ_HOUSTON",
    }
    fields.update(overrides)
    return Observation(**fields)


def dam(prices=PRICES, available=PUBLISHED) -> list[Observation]:
    rows = []
    for hour, price in enumerate(prices):
        start = z(2026, 6, 15, hour)
        rows.append(
            obs(
                value=price,
                interval_start=start,
                interval_end=start + timedelta(hours=1),
                published_at=available,
                available_at=available,
            )
        )
    return rows


def decide(policy, when, rows, bat=None, interrupts=(), load=Decimal(0)):
    decision = policy.decide(
        battery=bat or battery(),
        information=InformationSet(list(rows)),
        household_load_kw=load,
        config={"label": "synthetic"},
        decision_time=when,
        feed_interrupts=tuple(interrupts),
    )
    assert isinstance(decision, Decision)
    assert decision.asset_id == (bat or battery()).asset_id
    assert decision.decision_time == when
    assert decision.kw >= 0
    text = decision.reason.strip()
    assert " " in text and len(text) >= 8
    assert decision.policy_version
    assert isinstance(decision.config, dict)
    assert decision.inputs
    for item in decision.inputs:
        assert item.name and item.source and item.unit
        assert item.available_at <= when
    return decision


def named(decision, name):
    rows = [item for item in decision.inputs if item.name == name]
    assert len(rows) == 1
    return rows[0]


def test_C2_policies_share_one_interface_and_are_deterministic():
    when = z(2026, 6, 15, 2, 0)
    rows = dam()
    for cls in POLICIES:
        first = decide(cls(), when, rows)
        second = decide(cls(), when, rows)
        assert (second.action, second.kw, second.reason) == (first.action, first.kw, first.reason)


def test_C2_fixed_schedule_charges_at_night_and_offers_the_evening_peak():
    night = z(2026, 6, 15, 2, 0)
    late_night = z(2026, 6, 15, 5, 30)
    for when in (night, late_night):
        decision = decide(FixedSchedule(), when, dam())
        assert decision.action == "charge"
        assert decision.kw == Decimal(4)
        assert decision.delivery_start == when
        assert decision.delivery_end == when + timedelta(minutes=15)
        assert decision.attempted_reserve_violation is False
    offer_at = z(2026, 6, 15, 19, 45)
    last = z(2026, 6, 15, 20, 30)
    for when in (offer_at, last):
        decision = decide(FixedSchedule(), when, dam())
        assert decision.action == "offer_flex"
        assert decision.kw == Decimal(4)
        assert decision.delivery_start == when + timedelta(minutes=15)
        assert decision.delivery_end == when + timedelta(minutes=30)


def test_C2_fixed_schedule_holds_outside_its_windows():
    for when in (z(2026, 6, 15, 7, 0), z(2026, 6, 15, 12, 0), z(2026, 6, 15, 23, 0)):
        decision = decide(FixedSchedule(), when, dam())
        assert decision.action == "hold"
        assert decision.kw == Decimal(0)


def test_C2_fixed_schedule_ignores_missing_prices():
    when = z(2026, 6, 15, 2, 0)
    priced = decide(FixedSchedule(), when, dam())
    blind = decide(FixedSchedule(), when, [])
    assert (blind.action, blind.kw) == (priced.action, priced.kw)


def test_C2_preserve_backup_when_offer_would_breach_reserve():
    when = z(2026, 6, 15, 19, 45)
    bat = battery(soc_kwh=Decimal(1), min_reserve_kwh=Decimal(1), capacity_kwh=Decimal(10))
    decision = decide(FixedSchedule(), when, dam(), bat=bat)
    assert decision.action == "preserve_backup"
    assert decision.kw == Decimal(0)
    assert decision.attempted_reserve_violation is True


def test_C2_price_based_nearest_rank_quantiles_ties_and_precedence():
    assert nearest_rank(list(PRICES), 25) == Decimal(10)
    assert nearest_rank(list(PRICES), 75) == Decimal(100)
    rows = dam()
    held = decide(PriceBased(), z(2026, 6, 15, 8, 0), rows)
    assert held.action == "hold" and held.kw == Decimal(0)
    assert named(held, "dam_q25").value == Decimal(10)
    assert named(held, "dam_q75").value == Decimal(100)
    assert named(held, "dam_q25").unit == "USD/MWh"
    charged = decide(PriceBased(), z(2026, 6, 15, 5, 0), rows)
    assert charged.action == "charge" and charged.kw == Decimal(4)
    assert charged.delivery_start == z(2026, 6, 15, 5, 0)
    offered = decide(PriceBased(), z(2026, 6, 15, 6, 0), rows)
    assert offered.action == "offer_flex" and offered.kw == Decimal(4)
    # DEC-GM-127 (a): delivery 100 meets Q75 but hour 18 is not procurement.
    suppressed = decide(PriceBased(), z(2026, 6, 15, 18, 0), rows)
    assert suppressed.action == "hold" and suppressed.kw == Decimal(0)
    tie_prices = [Decimal(10)] * 12 + [Decimal(100)] * 12
    tied = decide(PriceBased(), z(2026, 6, 15, 11, 45), dam(tie_prices))
    assert tied.action == "offer_flex" and tied.kw == Decimal(4)
    both = decide(PriceBased(), z(2026, 6, 15, 5, 45), rows)
    assert both.action == "offer_flex"
    assert both.delivery_start == z(2026, 6, 15, 6, 0)
    assert both.delivery_end == z(2026, 6, 15, 6, 15)


def test_C2_price_based_q25_ge_q75_holds():
    flat = [Decimal(40)] * 24
    when = z(2026, 6, 15, 5, 0)
    decision = decide(PriceBased(), when, dam(flat))
    assert decision.action == "hold" and decision.kw == Decimal(0)
    evening = decide(PriceBased(), z(2026, 6, 15, 18, 0), dam(flat))
    assert evening.action == "hold"


def test_C2_price_based_missing_or_incomplete_dam_holds_and_is_not_zero():
    when = z(2026, 6, 15, 5, 0)
    missing = decide(PriceBased(), when, [])
    assert missing.action == "hold" and missing.kw == Decimal(0)
    assert all(item.value != Decimal(0) for item in missing.inputs)
    incomplete = decide(PriceBased(), when, dam(PRICES[:-1]))
    assert incomplete.action == "hold" and incomplete.kw == Decimal(0)


def test_C2_price_based_future_dam_revision_does_not_flip_the_decision():
    when = z(2026, 6, 15, 8, 0)
    base = dam()
    revised_prices = list(PRICES)
    revised_prices[8] = Decimal(1)
    future = dam(revised_prices, available=when + timedelta(hours=1))
    visible = dam(revised_prices, available=PUBLISHED)
    assert decide(PriceBased(), when, base).action == "hold"
    assert decide(PriceBased(), when, [*base, *future]).action == "hold"
    assert decide(PriceBased(), when, visible).action == "charge"


def test_C2_esr_informed_trend_does_not_override_a16_procurement():
    when = z(2026, 6, 15, 16, 45)
    rows = [*dam(), *_esr(Decimal(-80), Decimal(-20)), _rt(Decimal(200))]
    price = decide(PriceBased(), when, rows)
    informed = decide(EsrInformed(), when, rows)
    assert price.action == "hold"
    assert informed.action == "hold" and informed.kw == 0  # A16: zero household load.
    assert "commitment, load or reserve" in informed.reason.lower()


def test_C2_esr_informed_does_not_offer_when_charging_magnitude_increases():
    when = z(2026, 6, 15, 16, 45)
    rows = [*dam(), *_esr(Decimal(-20), Decimal(-80)), _rt(Decimal(200))]
    assert decide(EsrInformed(), when, rows).action == "hold"


def test_C2_esr_informed_uses_only_the_latest_two_complete_bins():
    when = z(2026, 6, 15, 16, 45)
    older = _esr_bin(z(2026, 6, 15, 16, 0), Decimal(-100))
    # Latest two are -20 then -80 (magnitude rises). A future -1 must not leak in.
    rows = [
        *dam(),
        older,
        *_esr(Decimal(-20), Decimal(-80)),
        _rt(Decimal(200)),
        _esr_bin(when, Decimal(-1), available=when + timedelta(minutes=15)),
    ]
    assert decide(EsrInformed(), when, rows).action == "hold"


def test_C2_esr_informed_fallback_when_esr_or_rt_missing():
    # DEC-GM-127 (b): 18:00 holds since current 100 exceeds Q50; 08:00 would charge.
    when = z(2026, 6, 15, 18, 0)
    no_esr = decide(EsrInformed(), when, dam())
    no_rt = decide(EsrInformed(), when, [*dam(), *_esr(Decimal(-80), Decimal(-20))])
    for decision in (no_esr, no_rt):
        assert decision.action == "hold"
        assert "fallback" in decision.reason.lower()
        assert all(item.value != Decimal(0) for item in decision.inputs)
    covered = FeedWindow(source="esr", start=z(2026, 6, 15, 16, 0), end=z(2026, 6, 15, 17, 0))
    blinded = decide(
        EsrInformed(),
        z(2026, 6, 15, 16, 45),
        [*dam(), *_esr(Decimal(-80), Decimal(-20)), _rt(Decimal(200))],
        interrupts=(covered,),
    )
    assert blinded.action == "hold"
    assert "fallback" in blinded.reason.lower()


def test_C2_esr_future_rt_spike_does_not_create_an_offer():
    # DEC-GM-127 (b): moved to 18:45 so current 100 exceeds Q50; fixtures follow.
    when = z(2026, 6, 15, 18, 45)
    rows = [*dam(), *_esr(Decimal(-80), Decimal(-20), 18), _rt(Decimal(30), hour=18)]
    spike = _rt(Decimal(9000), available=when + timedelta(minutes=5), hour=18)
    assert decide(EsrInformed(), when, rows, load=Decimal(2)).action == "hold"
    assert decide(EsrInformed(), when, [*rows, spike], load=Decimal(2)).action == "hold"
    seen = [*dam(), *_esr(Decimal(-80), Decimal(-20), 18), _rt(Decimal(9000), hour=18)]
    assert decide(EsrInformed(), when, seen, load=Decimal(2)).action == "self_supply"


def test_C2_battery_aware_q50_triggers_differ_from_price_based():
    # DEC-GM-127 (b): PRICES Q50=50. At 08:00 current DAM is exactly 50.
    when = z(2026, 6, 15, 8, 0)
    assert nearest_rank(list(PRICES), 50) == Decimal(50)
    price = decide(PriceBased(), when, dam())
    aware = decide(EsrInformed(), when, dam())
    assert price.action == "hold" and price.kw == Decimal(0)
    assert aware.action == "charge" and aware.kw == Decimal(4)
    assert named(aware, "dam_q50").value == Decimal(50)
    assert "fallback" in aware.reason.lower()
    # RT 60 meets Q50 but not Q75: Battery-aware serves load, PriceBased holds.
    start = when - timedelta(minutes=15)
    rt = obs(
        series="rt_spp",
        source="rt_spp",
        value=Decimal(60),
        interval_start=start,
        interval_end=when,
        published_at=when,
        available_at=when,
    )
    loaded = [*dam(), *_esr(Decimal(-80), Decimal(-20)), rt]
    price = decide(PriceBased(), when, loaded, load=Decimal(2))
    aware = decide(EsrInformed(), when, loaded, load=Decimal(2))
    assert price.action == "hold" and price.kw == Decimal(0)
    assert aware.action == "self_supply" and aware.kw == Decimal(2)
    # Overlapping quantiles still hold for both policies.
    flat = [Decimal(40)] * 24
    for cls in (PriceBased, EsrInformed):
        held = decide(cls(), z(2026, 6, 15, 18, 0), dam(flat))
        assert held.action == "hold" and held.kw == Decimal(0)


def _esr(previous: Decimal, latest: Decimal, hour: int = 16) -> list[Observation]:
    return [
        _esr_bin(z(2026, 6, 15, hour, 15), previous),
        _esr_bin(z(2026, 6, 15, hour, 30), latest),
    ]


def _esr_bin(start, value: Decimal, available=None) -> Observation:
    end = start + timedelta(minutes=15)
    stamp = end if available is None else available
    return obs(
        series="esr_charging",
        source="esr",
        value=value,
        unit="MW",
        zone="ERCOT",
        settlement_point=None,
        interval_start=start,
        interval_end=end,
        published_at=stamp,
        available_at=stamp,
    )


def _rt(value: Decimal, available=None, hour: int = 16) -> Observation:
    start = z(2026, 6, 15, hour, 30)
    end = start + timedelta(minutes=15)
    stamp = end if available is None else available
    return obs(
        series="rt_spp",
        source="rt_spp",
        value=value,
        interval_start=start,
        interval_end=end,
        published_at=stamp,
        available_at=stamp,
    )
