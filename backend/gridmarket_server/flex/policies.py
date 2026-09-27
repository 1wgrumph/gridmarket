"""DEC-GM-136 (amends A16): fixed, price-based and budget-guarded battery-aware policies."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from .battery import ZERO, nonnegative
from .information import InformationView, aware

CHI = ZoneInfo("America/Chicago")
QUARTER = timedelta(minutes=15)
HOURS = Decimal("0.25")


@dataclass(frozen=True)
class DecisionInput:
    name: str
    value: Decimal | str | None
    unit: str
    source: str
    interval_start: datetime
    interval_end: datetime
    published_at: datetime
    available_at: datetime
    quality: str


@dataclass(frozen=True)
class Decision:
    asset_id: str
    decision_time: datetime
    action: str
    kw: Decimal
    delivery_start: datetime
    delivery_end: datetime
    reason: str
    policy_version: str
    config: dict
    inputs: tuple[DecisionInput, ...]
    attempted_reserve_violation: bool = False


def day_bounds(moment):
    local = moment.astimezone(CHI)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def source_input(row, name=None):
    return DecisionInput(
        name or row.series,
        row.value,
        row.unit,
        row.source,
        row.interval_start,
        row.interval_end,
        row.published_at,
        row.available_at,
        row.quality,
    )


def dam_rows(view, zone, now):
    start, end = day_bounds(now)
    rows = [
        r
        for r in view.observations
        if r.series == "dam_spp"
        and r.zone == zone
        and r.settlement_point in (None, zone)
        and start <= r.interval_start < end
        and r.value is not None
        and r.unit == "USD/MWh"
    ]
    rows.sort(key=lambda r: r.interval_start)
    expected = int((end - start).total_seconds() // 3600)
    if len(rows) != expected or any(
        r.interval_start != start + timedelta(hours=i)
        or r.interval_end != start + timedelta(hours=i + 1)
        for i, r in enumerate(rows)
    ):
        return []
    return rows


def procurement_hours(view, zone, now):
    """A16: four highest eligible DAM hours, ties by earlier UTC instant."""
    return sorted(
        r.interval_start
        for r in sorted(dam_rows(view, zone, now), key=lambda r: (-r.value, r.interval_start))[:4]
    )


def remaining_procurement_quarters(procurement, now):
    """DEC-GM-136: procurement quarter starts strictly after the decision time."""
    return sum(1 for hour in procurement for step in range(4) if hour + step * QUARTER > now)


def price_request(view, zone, now, *, procurement, charge_p, offer_p, self_p):
    """DEC-GM-127 (a)(b): offers only into procurement; per-policy quantiles."""
    start, end = day_bounds(now)
    rows = dam_rows(view, zone, now)
    if not rows:
        return "hold", "Missing or ineligible complete-day DAM vector.", [], None
    values = sorted(r.value for r in rows)
    percentiles = {25, 75, charge_p, offer_p, self_p}
    quants = {p: values[(p * len(values) + 99) // 100 - 1] for p in percentiles}
    q_charge, q_offer, q_self = quants[charge_p], quants[offer_p], quants[self_p]
    inputs = [
        DecisionInput(
            "dam_vector",
            ",".join(str(r.value) for r in rows),
            "USD/MWh hourly from interval_start",
            "dam_spp",
            start,
            end,
            max(r.published_at for r in rows),
            max(r.available_at for r in rows),
            "derived:eligible hourly vector",
        )
    ]
    for percentile in sorted(quants):
        inputs.append(
            DecisionInput(
                f"dam_q{percentile}",
                quants[percentile],
                "USD/MWh",
                "derived:dam_spp",
                start,
                end,
                max(r.published_at for r in rows),
                max(r.available_at for r in rows),
                "derived",
            )
        )
    if quants[25] >= quants[75]:
        return "hold", "DAM quantiles overlap; hold energy.", inputs, None
    current = next(r for r in rows if r.interval_start <= now < r.interval_end)
    delivery = next((r for r in rows if r.interval_start <= now + QUARTER < r.interval_end), None)
    target = now + QUARTER
    procuring = any(hour <= target < hour + timedelta(hours=1) for hour in procurement)
    if delivery and procuring and delivery.value >= q_offer:
        return "offer_flex", "Next-quarter DAM price meets the offer threshold.", inputs, q_self
    if current.value <= q_charge:
        return "charge", "Current-hour DAM price meets the charge threshold.", inputs, q_self
    return "hold", "DAM prices are between the action thresholds.", inputs, q_self


class FixedSchedule:
    policy_version = "FixedSchedule/DEC-GM-127-A16"
    offer_fraction = Decimal(1)

    def __init__(self, procurement=None):
        self.procurement = procurement

    def procuring(self, view, zone, now):
        hours = (
            self.procurement if self.procurement is not None else procurement_hours(view, zone, now)
        )
        return any(hour <= now + QUARTER < hour + timedelta(hours=1) for hour in hours)

    def procurement_budget(self, battery, view, zone, now):
        """Remaining procurement quarters and per-quarter DC kWh share, or None."""
        return

    def request(self, view, zone, now):
        if self.procuring(view, zone, now):
            return "offer_flex", "Next-quarter delivery is in the DAM procurement schedule.", []
        if now.astimezone(CHI).hour < 6:
            return "charge", "Current quarter is in the simulated overnight charging schedule.", []
        if 17 <= now.astimezone(CHI).hour < 21:
            return "self_supply", "Simulated evening household self-supply.", []
        return "hold", "Current quarter is outside the charging and delivery schedules.", []

    def decide(
        self, *, battery, information, household_load_kw, config, decision_time, feed_interrupts=()
    ):
        now = aware(decision_time).astimezone(UTC)
        if now.minute % 15 or now.second or now.microsecond:
            raise ValueError("Decision time must open a quarter")
        load = nonnegative(household_load_kw, "household_load_kw")
        settings = deepcopy(config)
        settings.setdefault("zone", "LZ_HOUSTON")
        settings.setdefault("current_commitment_kw", ZERO)
        commitment = nonnegative(settings["current_commitment_kw"], "current_commitment_kw")
        if isinstance(information, InformationView):
            if information.decision_time != now or feed_interrupts:
                raise ValueError("Use an information view for this time with disruptions applied")
            view = information
        else:
            view = information.at(now, feed_interrupts=feed_interrupts)
        proc_hours = (
            self.procurement
            if self.procurement is not None
            else procurement_hours(view, settings["zone"], now)
        )
        settings["procurement_hours"] = [hour.isoformat() for hour in proc_hours]
        settings["offer_energy_fraction"] = self.offer_fraction
        action, reason, inputs = self.request(view, settings["zone"], now)
        start = now + QUARTER if action == "offer_flex" else now
        held_offer = held_self = ZERO
        budget = self.procurement_budget(battery, view, settings["zone"], now)
        if budget is not None:
            count, per_quarter = budget
            held_self = count * per_quarter
            # The offer itself is the target quarter's budgeted delivery.
            target = any(hour <= start < hour + timedelta(hours=1) for hour in proc_hours)
            held_offer = (count - bool(target)) * per_quarter
            settings["remaining_procurement_quarters"] = count
            settings["procurement_budget_dc_kwh"] = held_self
        attempted = False
        kw = ZERO
        if action == "offer_flex":
            available = max(
                battery.soc_kwh - battery.min_reserve_kwh - battery.reserved_dc_kwh - held_offer,
                ZERO,
            )
            kw = min(
                battery.feasible_discharge_kw(HOURS),
                available * battery.eta_d * self.offer_fraction / HOURS,
            )
            if start + QUARTER > day_bounds(now)[1]:
                action, kw, reason = (
                    "hold",
                    ZERO,
                    "Next-quarter delivery would cross the replay day.",
                )
            elif kw == 0:
                attempted = battery.soc_kwh <= battery.min_reserve_kwh + battery.reserved_dc_kwh
                action = "preserve_backup" if attempted else "hold"
                reason += " Reserve, reservations or discharge power prevent a new offer."
        elif action == "self_supply":
            surplus = max(
                battery.soc_kwh - battery.min_reserve_kwh - battery.reserved_dc_kwh - held_self,
                ZERO,
            )
            kw = (
                min(load, battery.feasible_discharge_kw(HOURS), surplus * battery.eta_d / HOURS)
                if not commitment
                else ZERO
            )
            if not kw:
                action, reason = (
                    "hold",
                    reason + " Commitment, load or reserve prevents self-supply.",
                )
        elif action == "charge":
            kw = battery.feasible_charge_kw(HOURS)
            if commitment or not kw:
                action, kw = "hold", ZERO
                reason += " Existing delivery or battery headroom prevents new charging."
        reason += f" Requested {kw} AC kW; acceptance and delivery are not yet determined."
        # Include state/config inputs even when no external feed is needed or available.
        state = [
            ("soc_kwh", battery.soc_kwh, "kWh DC"),
            ("capacity_kwh", battery.capacity_kwh, "kWh DC"),
            ("min_reserve_kwh", battery.min_reserve_kwh, "kWh DC"),
            ("reserved_dc_kwh", battery.reserved_dc_kwh, "kWh DC"),
            ("max_charge_kw", battery.max_charge_kw, "kW AC"),
            ("max_discharge_kw", battery.max_discharge_kw, "kW AC"),
            ("eta_round_trip", battery.eta_round_trip, "ratio"),
            ("household_load_kw", load, "kW AC"),
            ("current_commitment_kw", commitment, "kW AC"),
        ]
        settings["state_snapshot"] = {name: value for name, value, _ in state}
        # Missing observations remain absent, never represented by synthetic zero prices.
        inputs += [
            DecisionInput(
                name, value, unit, "simulated:asset", now, now + QUARTER, now, now, "simulated"
            )
            for name, value, unit in state
            if value != 0
        ]
        return Decision(
            battery.asset_id,
            now,
            action,
            kw,
            start,
            start + QUARTER,
            reason,
            self.policy_version,
            settings,
            tuple(inputs),
            attempted,
        )


class PriceBased(FixedSchedule):
    policy_version = "PriceBased/DEC-GM-127-A16"
    charge_p, offer_p, self_p = 25, 75, 75

    def request(self, view, zone, now):
        hours = (
            self.procurement if self.procurement is not None else procurement_hours(view, zone, now)
        )
        action, reason, inputs, threshold = price_request(
            view,
            zone,
            now,
            procurement=hours,
            charge_p=self.charge_p,
            offer_p=self.offer_p,
            self_p=self.self_p,
        )
        rt = sorted(
            (
                r
                for r in view.observations
                if r.series == "rt_spp"
                and r.zone == zone
                and r.settlement_point in (None, zone)
                and r.unit == "USD/MWh"
                and r.value is not None
                and r.interval_end <= now
            ),
            key=lambda r: r.interval_end,
        )
        if rt:
            inputs.append(source_input(rt[-1], "rt_latest"))
        if action != "offer_flex" and threshold is not None and rt and rt[-1].value >= threshold:
            return (
                "self_supply",
                f"Latest eligible RT meets DAM Q{self.self_p}; serve simulated load.",
                inputs,
            )
        return action, reason, inputs


class EsrInformed(PriceBased):
    policy_version = "EsrInformed/DEC-GM-136"
    charge_p, offer_p, self_p = 50, 75, 75
    offer_fraction = Decimal(1)

    def procurement_budget(self, battery, view, zone, now):
        """DEC-GM-136: hold the home's share of remaining procurement demand.

        Programme demand per quarter is 25% of fleet rated kW (engine), so the
        home's expected delivery is 25% of its own rated kW per remaining
        procurement quarter, in DC kWh. Procurement hours come from D's DAM
        vector, published D-1; no future RT is used.
        """
        hours = (
            self.procurement if self.procurement is not None else procurement_hours(view, zone, now)
        )
        per_quarter = battery.max_discharge_kw * HOURS * Decimal("0.25") / battery.eta_d
        return remaining_procurement_quarters(hours, now), per_quarter

    def request(self, view, zone, now):
        action, reason, inputs = super().request(view, zone, now)
        esr = sorted(
            (
                r
                for r in view.observations
                if r.series == "esr_charging"
                and r.zone == "ERCOT"
                and r.unit == "MW"
                and r.value is not None
                and r.value <= 0
                and r.interval_end <= now
                and r.interval_end - r.interval_start == QUARTER
            ),
            key=lambda r: r.interval_end,
        )[-2:]
        if (
            len(esr) < 2
            or esr[0].interval_end != esr[1].interval_start
            or not any(i.name == "rt_latest" for i in inputs)
        ):
            reason = "PriceBased fallback: missing eligible ESR or RT inputs. " + reason
        else:
            inputs += [source_input(esr[0], "esr_previous"), source_input(esr[1], "esr_latest")]
        return action, "Battery-aware: reserve-plus-budget guard. " + reason, inputs
