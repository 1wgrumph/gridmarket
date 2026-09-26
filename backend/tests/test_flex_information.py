"""R2 red tests. Visibility uses available_at, not delivery time."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from gridmarket_server.flex import (
    Battery,
    EsrInformed,
    FeedWindow,
    FixedSchedule,
    InformationSet,
    Observation,
    PriceBased,
)

CHI = ZoneInfo("America/Chicago")


def _utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=CHI).astimezone(UTC)


def obs(**overrides) -> Observation:
    start = _utc(2026, 6, 15, 8, 0)
    fields = {
        "series": "rt_spp",
        "source": "rt_spp",
        "value": Decimal(21),
        "unit": "USD/MWh",
        "interval_start": start,
        "interval_end": start + timedelta(minutes=15),
        "published_at": start,
        "available_at": start,
        "quality": "synthetic",
        "zone": "LZ_HOUSTON",
        "settlement_point": "LZ_HOUSTON",
    }
    fields.update(overrides)
    return Observation(**fields)


def values(view) -> set[Decimal]:
    return {row.value for row in view.observations if row.value is not None}


def test_R2_future_spike_invisible():
    now = _utc(2026, 6, 15, 12, 0)
    base = obs(available_at=now - timedelta(minutes=1), value=Decimal(21))
    spike = obs(
        value=Decimal(9000),
        available_at=now + timedelta(minutes=1),
        published_at=now + timedelta(minutes=1),
        interval_start=now + timedelta(hours=1),
        interval_end=now + timedelta(hours=1, minutes=15),
    )
    hidden = InformationSet([base, spike]).at(now)
    visible = InformationSet([base, spike]).at(now + timedelta(minutes=1))
    assert Decimal(9000) not in values(hidden)
    assert Decimal(21) in values(hidden)
    assert Decimal(9000) in values(visible)


def test_R2_late_revision_stays_invisible_until_available():
    now = _utc(2026, 6, 15, 12, 0)
    start = now - timedelta(minutes=30)
    original = obs(
        value=Decimal(21),
        interval_start=start,
        interval_end=start + timedelta(minutes=15),
        published_at=start,
        available_at=start,
    )
    revision = obs(
        value=Decimal(9000),
        interval_start=start,
        interval_end=start + timedelta(minutes=15),
        published_at=now + timedelta(hours=1),
        available_at=now + timedelta(hours=1),
    )
    view = InformationSet([original, revision]).at(now)
    assert values(view) == {Decimal(21)}


def test_R2_dam_published_on_d_minus_1_stays_visible():
    now = _utc(2026, 6, 15, 0, 0)
    published = _utc(2026, 6, 14, 13, 30)
    later = _utc(2026, 6, 15, 20, 0)
    dam = obs(
        series="dam_spp",
        source="dam_spp",
        value=Decimal(80),
        interval_start=later,
        interval_end=later + timedelta(hours=1),
        published_at=published,
        available_at=published,
    )
    leaked = obs(
        series="dam_spp",
        source="dam_spp",
        value=Decimal(9000),
        interval_start=later,
        interval_end=later + timedelta(hours=1),
        published_at=now + timedelta(hours=2),
        available_at=now + timedelta(hours=2),
    )
    view = InformationSet([dam, leaked]).at(now)
    assert Decimal(80) in values(view)
    assert Decimal(9000) not in values(view)


def test_R2_rt_interval_hidden_at_its_opening():
    opening = _utc(2026, 6, 15, 17, 0)
    current = obs(
        value=Decimal(9000),
        interval_start=opening,
        interval_end=opening + timedelta(minutes=15),
        published_at=opening + timedelta(minutes=20),
        available_at=opening + timedelta(minutes=20),
    )
    previous_end = opening
    previous = obs(
        value=Decimal(21),
        interval_start=opening - timedelta(minutes=15),
        interval_end=previous_end,
        published_at=previous_end,
        available_at=previous_end,
    )
    view = InformationSet([current, previous]).at(opening)
    assert Decimal(9000) not in values(view)
    assert Decimal(21) in values(view)


def test_R2_feed_interrupt_expires_actuals_after_30_minutes_and_keeps_dam():
    end = _utc(2026, 6, 15, 16, 0)
    actual = obs(
        value=Decimal(21),
        interval_start=end - timedelta(minutes=15),
        interval_end=end,
        published_at=end - timedelta(minutes=30),
        available_at=end - timedelta(minutes=30),
    )
    published = _utc(2026, 6, 14, 13, 30)
    dam = obs(
        series="dam_spp",
        source="dam_spp",
        value=Decimal(40),
        interval_start=_utc(2026, 6, 15, 18, 0),
        interval_end=_utc(2026, 6, 15, 19, 0),
        published_at=published,
        available_at=published,
    )
    window = FeedWindow(source="rt_spp", start=end, end=end + timedelta(hours=2))
    info = InformationSet([actual, dam])
    still = info.at(end + timedelta(minutes=29), feed_interrupts=(window,))
    expired = info.at(end + timedelta(minutes=30), feed_interrupts=(window,))
    assert Decimal(21) in values(still)
    assert Decimal(21) not in values(expired)
    assert Decimal(40) in values(expired)
    assert all(row.value != Decimal(0) for row in expired.observations)


def test_R2_feed_interrupt_recovery_exposes_only_r2_observations():
    start = _utc(2026, 6, 15, 16, 0)
    arrived = obs(
        value=Decimal(33),
        interval_start=start,
        interval_end=start + timedelta(minutes=15),
        published_at=start + timedelta(minutes=10),
        available_at=start + timedelta(minutes=10),
    )
    window = FeedWindow(source="rt_spp", start=start, end=start + timedelta(hours=1))
    info = InformationSet([arrived])
    during = info.at(start + timedelta(minutes=20), feed_interrupts=(window,))
    after = info.at(start + timedelta(hours=1), feed_interrupts=(window,))
    assert Decimal(33) not in values(during)
    assert Decimal(33) in values(after)


def test_R2_future_spike_and_late_revision_do_not_change_any_policy():
    now = _utc(2026, 6, 15, 12, 0)
    base = [
        obs(value=Decimal(21), available_at=now - timedelta(hours=1), published_at=now),
    ]
    spike = obs(
        value=Decimal(9000),
        available_at=now + timedelta(minutes=5),
        published_at=now + timedelta(minutes=5),
        interval_start=now + timedelta(hours=2),
        interval_end=now + timedelta(hours=2, minutes=15),
    )
    revision = obs(
        value=Decimal(9000),
        interval_start=base[0].interval_start,
        interval_end=base[0].interval_end,
        available_at=now + timedelta(hours=3),
        published_at=now + timedelta(hours=3),
    )
    battery_kwargs = {
        "asset_id": "synthetic-asset",
        "capacity_kwh": Decimal(20),
        "soc_kwh": Decimal(10),
        "max_charge_kw": Decimal(4),
        "max_discharge_kw": Decimal(4),
        "eta_round_trip": Decimal(1),
        "min_reserve_kwh": Decimal(1),
        "label": "synthetic",
    }
    for policy in (FixedSchedule(), PriceBased(), EsrInformed()):
        plain = policy.decide(
            battery=Battery(**battery_kwargs),
            information=InformationSet(base),
            household_load_kw=Decimal(0),
            config={},
            decision_time=now,
            feed_interrupts=(),
        )
        poisoned = policy.decide(
            battery=Battery(**battery_kwargs),
            information=InformationSet([*base, spike, revision]),
            household_load_kw=Decimal(0),
            config={},
            decision_time=now,
            feed_interrupts=(),
        )
        assert poisoned.action == plain.action
        assert poisoned.kw == plain.kw
        assert Decimal(9000) not in {item.value for item in poisoned.inputs}
        assert "9000" not in poisoned.reason
