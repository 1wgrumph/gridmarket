"""DEC-GM-113 amendment 5: AC dispatch and stored DC battery energy."""

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)


def nonnegative(value, name):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


@dataclass(frozen=True)
class StepResult:
    soc_kwh: Decimal
    charge_kw: Decimal
    discharge_kw: Decimal
    charge_ac_kwh: Decimal
    discharge_ac_kwh: Decimal
    losses_kwh: Decimal
    load_served_kwh: Decimal
    grid_import_kwh: Decimal
    grid_export_kwh: Decimal
    attempted_reserve_violation: bool
    actual_breach: bool
    invalidated: bool


@dataclass
class Battery:
    asset_id: str
    capacity_kwh: Decimal
    soc_kwh: Decimal
    max_charge_kw: Decimal
    max_discharge_kw: Decimal
    eta_round_trip: Decimal
    min_reserve_kwh: Decimal
    label: str = "simulated"
    reserved_dc_kwh: Decimal = ZERO

    def __post_init__(self):
        for name in (
            "capacity_kwh",
            "soc_kwh",
            "max_charge_kw",
            "max_discharge_kw",
            "eta_round_trip",
            "min_reserve_kwh",
            "reserved_dc_kwh",
        ):
            setattr(self, name, nonnegative(getattr(self, name), name))
        if (
            not self.capacity_kwh
            or not 0 < self.eta_round_trip <= 1
            or not self.min_reserve_kwh <= self.soc_kwh <= self.capacity_kwh
            or self.reserved_dc_kwh > self.soc_kwh - self.min_reserve_kwh
        ):
            raise ValueError("Invalid capacity, efficiency, reserve or initial energy")

    @property
    def eta_c(self):
        return self.eta_round_trip.sqrt()

    @property
    def eta_d(self):
        return self.eta_c

    def feasible_charge_kw(self, hours):
        hours = nonnegative(hours, "hours")
        if not hours:
            raise ValueError("hours must be positive")
        return min(self.max_charge_kw, (self.capacity_kwh - self.soc_kwh) / (self.eta_c * hours))

    def feasible_discharge_kw(self, hours):
        hours = nonnegative(hours, "hours")
        if not hours:
            raise ValueError("hours must be positive")
        energy = max(self.soc_kwh - self.min_reserve_kwh - self.reserved_dc_kwh, ZERO)
        return min(self.max_discharge_kw, energy * self.eta_d / hours)

    def transition(
        self,
        *,
        charge_kw=ZERO,
        discharge_kw=ZERO,
        hours=Decimal("0.25"),
        load_kw=ZERO,
        forced=False,
    ):
        """Pure transition; forced discharge is diagnostic and invalidates a breach."""
        charge_kw = nonnegative(charge_kw, "charge_kw")
        discharge_kw = nonnegative(discharge_kw, "discharge_kw")
        hours = nonnegative(hours, "hours")
        load_kw = nonnegative(load_kw, "load_kw")
        if not hours or charge_kw * discharge_kw:
            raise ValueError("Positive duration and mutually exclusive dispatch required")
        charge = min(charge_kw, self.feasible_charge_kw(hours))
        feasible = self.feasible_discharge_kw(hours)
        attempted = min(discharge_kw, self.max_discharge_kw) > feasible
        limit = (
            min(self.max_discharge_kw, self.soc_kwh * self.eta_d / hours) if forced else feasible
        )
        discharge = min(discharge_kw, limit)
        incoming, outgoing = charge * hours, discharge * hours
        soc = self.soc_kwh + incoming * self.eta_c - outgoing / self.eta_d
        breach = soc < self.min_reserve_kwh
        return StepResult(
            soc,
            charge,
            discharge,
            incoming,
            outgoing,
            incoming * (1 - self.eta_c) + outgoing / self.eta_d - outgoing,
            min(load_kw, discharge) * hours,
            max(load_kw + charge - discharge, ZERO) * hours,
            max(discharge - load_kw - charge, ZERO) * hours,
            attempted,
            breach,
            breach,
        )

    def step(self, **kwargs):
        """Apply the pure transition to this caller-owned battery instance."""
        result = self.transition(**kwargs)
        self.soc_kwh = result.soc_kwh
        return result
