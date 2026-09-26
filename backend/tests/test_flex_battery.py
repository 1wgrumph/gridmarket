"""R4 red tests. Synthetic internal battery; no external observation."""

from decimal import Decimal

import pytest

from gridmarket_server.flex import Battery, StepResult

H = Decimal("0.25")
ETA = Decimal("0.81")
SQRT = Decimal("0.9")


def battery(**overrides) -> Battery:
    fields = {
        "asset_id": "synthetic-asset",
        "capacity_kwh": Decimal(10),
        "soc_kwh": Decimal(5),
        "max_charge_kw": Decimal(4),
        "max_discharge_kw": Decimal(4),
        "eta_round_trip": ETA,
        "min_reserve_kwh": Decimal(1),
        "label": "synthetic",
    }
    fields.update(overrides)
    return Battery(**fields)


def step(bat: Battery, **overrides) -> StepResult:
    fields = {
        "charge_kw": Decimal(0),
        "discharge_kw": Decimal(0),
        "hours": H,
        "load_kw": Decimal(0),
        "forced": False,
    }
    fields.update(overrides)
    result = bat.step(**fields)
    assert isinstance(result, StepResult)
    assert result.soc_kwh == bat.soc_kwh
    return result


def test_R4_label_is_synthetic():
    assert battery().label == "synthetic"


def test_R4_efficiency_splits_as_sqrt_each_way():
    bat = battery()
    assert bat.eta_c == SQRT
    assert bat.eta_d == SQRT


def test_R4_one_kwh_cycle_returns_eta_round_trip():
    bat = battery(
        soc_kwh=Decimal(0),
        min_reserve_kwh=Decimal(0),
        max_charge_kw=Decimal(10),
        max_discharge_kw=Decimal(10),
    )
    charged = step(bat, charge_kw=Decimal(1), hours=Decimal(1))
    assert charged.charge_ac_kwh == Decimal(1)
    assert charged.soc_kwh == SQRT
    discharged = step(bat, discharge_kw=ETA, hours=Decimal(1))
    assert discharged.discharge_ac_kwh == ETA
    assert discharged.soc_kwh == Decimal(0)


def test_R4_energy_account_closes():
    bat = battery(soc_kwh=Decimal(0), min_reserve_kwh=Decimal(0), max_charge_kw=Decimal(10))
    charged = step(bat, charge_kw=Decimal(1), hours=Decimal(1))
    assert charged.losses_kwh == Decimal(1) - SQRT
    assert charged.charge_ac_kwh - charged.discharge_ac_kwh - charged.losses_kwh == charged.soc_kwh
    drained = battery(
        soc_kwh=SQRT,
        min_reserve_kwh=Decimal(0),
        max_discharge_kw=Decimal(10),
    )
    discharged = step(drained, discharge_kw=ETA, hours=Decimal(1))
    assert discharged.losses_kwh == SQRT - ETA
    assert discharged.charge_ac_kwh - discharged.discharge_ac_kwh - discharged.losses_kwh == (
        discharged.soc_kwh - SQRT
    )


def test_R4_power_limit_clips_charge_kw():
    bat = battery(max_charge_kw=Decimal(4))
    result = step(bat, charge_kw=Decimal(100))
    assert result.charge_kw == Decimal(4)
    assert result.soc_kwh == Decimal(5) + SQRT * Decimal(4) * H
    assert result.attempted_reserve_violation is False


def test_R4_headroom_clips_charge():
    bat = battery(
        soc_kwh=Decimal("9.5"),
        max_charge_kw=Decimal(100),
        min_reserve_kwh=Decimal(0),
    )
    result = step(bat, charge_kw=Decimal(100))
    assert result.charge_kw == Decimal("0.5") / (SQRT * H)
    assert result.soc_kwh == Decimal(10)
    assert result.actual_breach is False


def test_R4_reserve_clips_flexibility_discharge_without_breach():
    bat = battery(
        soc_kwh=Decimal("1.2"),
        min_reserve_kwh=Decimal(1),
        eta_round_trip=Decimal(1),
        max_discharge_kw=Decimal(4),
    )
    result = step(bat, discharge_kw=Decimal(4))
    assert result.discharge_kw == Decimal("0.8")
    assert result.soc_kwh == Decimal(1)
    assert result.attempted_reserve_violation is True
    assert result.actual_breach is False
    assert result.invalidated is False


def test_R4_flexibility_discharge_that_lands_on_reserve_is_not_an_attempt():
    bat = battery(
        soc_kwh=Decimal(2),
        min_reserve_kwh=Decimal(1),
        eta_round_trip=Decimal(1),
        max_discharge_kw=Decimal(10),
    )
    result = step(bat, discharge_kw=Decimal(1), hours=Decimal(1))
    assert result.soc_kwh == Decimal(1)
    assert result.attempted_reserve_violation is False
    assert result.actual_breach is False


def test_R4_forced_discharge_below_reserve_is_a_breach():
    bat = battery(
        soc_kwh=Decimal("1.2"),
        min_reserve_kwh=Decimal(1),
        eta_round_trip=Decimal(1),
        max_discharge_kw=Decimal(4),
    )
    result = step(bat, discharge_kw=Decimal(4), forced=True)
    assert result.soc_kwh == Decimal("0.2")
    assert result.actual_breach is True
    assert result.invalidated is True
    assert result.soc_kwh < bat.min_reserve_kwh


def test_R4_simultaneous_charge_and_discharge_rejected():
    bat = battery()
    before = bat.soc_kwh
    with pytest.raises(ValueError):
        step(bat, charge_kw=Decimal(1), discharge_kw=Decimal(1))
    assert bat.soc_kwh == before


def test_R4_load_splits_import_and_export():
    bat = battery(
        soc_kwh=Decimal(5),
        min_reserve_kwh=Decimal(0),
        eta_round_trip=Decimal(1),
        max_discharge_kw=Decimal(4),
    )
    result = step(bat, discharge_kw=Decimal(4), load_kw=Decimal(2))
    assert result.discharge_ac_kwh == Decimal(1)
    assert result.load_served_kwh == Decimal("0.5")
    assert result.grid_export_kwh == Decimal("0.5")
    assert result.grid_import_kwh == Decimal(0)
    assert result.load_served_kwh + result.grid_export_kwh == result.discharge_ac_kwh
    assert result.soc_kwh == Decimal(4)


@pytest.mark.parametrize(
    "overrides",
    [
        {"eta_round_trip": Decimal(0)},
        {"eta_round_trip": Decimal("1.1")},
        {"eta_round_trip": Decimal("-0.1")},
        {"soc_kwh": Decimal(11)},
        {"soc_kwh": Decimal(0), "min_reserve_kwh": Decimal(1)},
        {"min_reserve_kwh": Decimal(11)},
        {"min_reserve_kwh": Decimal(-1)},
        {"capacity_kwh": Decimal(0)},
        {"max_charge_kw": Decimal(-1)},
        {"max_discharge_kw": Decimal(-1)},
        {"soc_kwh": Decimal("NaN")},
        {"max_charge_kw": Decimal("Infinity")},
    ],
)
def test_R4_invalid_inputs_rejected(overrides):
    with pytest.raises(ValueError):
        battery(**overrides)
