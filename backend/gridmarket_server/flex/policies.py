"""DEC-GM-113 amendment 6: reproducible requests, explanations and three policies."""

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


def price_request(view, zone, now):
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
        return "hold", "Missing or ineligible complete-day DAM vector.", [], None
    values = sorted(r.value for r in rows)
    q25, q75 = (values[(p * len(values) + 99) // 100 - 1] for p in (25, 75))
    inputs = [source_input(r, f"dam_hour_{i}") for i, r in enumerate(rows)]
    for name, value in (("dam_q25", q25), ("dam_q75", q75)):
        inputs.append(
            DecisionInput(
                name,
                value,
                "USD/MWh",
                "derived:dam_spp",
                start,
                end,
                max(r.published_at for r in rows),
                max(r.available_at for r in rows),
                "derived",
            )
        )
    if q25 >= q75:
        return "hold", "DAM quantiles overlap; hold energy.", inputs, None
    current = next(r for r in rows if r.interval_start <= now < r.interval_end)
    delivery = next((r for r in rows if r.interval_start <= now + QUARTER < r.interval_end), None)
    if delivery and delivery.value >= q75:
        return "offer_flex", "Next-quarter DAM price meets the upper threshold.", inputs, q75
    if current.value <= q25:
        return "charge", "Current-hour DAM price meets the lower threshold.", inputs, q75
    return "hold", "DAM prices are between the action thresholds.", inputs, q75


class FixedSchedule:
    policy_version = "FixedSchedule/DEC-GM-113-v1"

    def request(self, view, zone, now):
        if 17 <= (now + QUARTER).astimezone(CHI).hour < 21:
            return "offer_flex", "Next-quarter delivery is in the simulated evening schedule.", []
        if now.astimezone(CHI).hour < 6:
            return "charge", "Current quarter is in the simulated overnight charging schedule.", []
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
        action, reason, inputs = self.request(view, settings["zone"], now)
        start = now + QUARTER if action == "offer_flex" else now
        attempted = False
        kw = ZERO
        if action == "offer_flex":
            kw = battery.feasible_discharge_kw(HOURS)
            if start + QUARTER > day_bounds(now)[1]:
                action, kw, reason = (
                    "hold",
                    ZERO,
                    "Next-quarter delivery would cross the replay day.",
                )
            elif kw == 0:
                attempted = battery.soc_kwh <= battery.min_reserve_kwh + battery.reserved_dc_kwh
                action = "preserve_backup" if attempted else "hold"
                reason = "Reserve, reservations or discharge power prevent a new offer."
        elif action == "charge":
            kw = battery.feasible_charge_kw(HOURS)
            if commitment or not kw:
                action, kw = "hold", ZERO
                reason = "Existing delivery or battery headroom prevents new charging."
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
    policy_version = "PriceBased/DEC-GM-113-v1"

    def request(self, view, zone, now):
        action, reason, inputs, _ = price_request(view, zone, now)
        return action, reason, inputs


class EsrInformed(FixedSchedule):
    policy_version = "EsrInformed/DEC-GM-113-v1"

    def request(self, view, zone, now):
        action, reason, inputs, q75 = price_request(view, zone, now)
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
        if len(esr) < 2 or not rt or esr[0].interval_end != esr[1].interval_start:
            return (
                action,
                "PriceBased fallback: missing eligible ESR or RT inputs. " + reason,
                inputs,
            )
        inputs += [
            source_input(esr[0], "esr_previous"),
            source_input(esr[1], "esr_latest"),
            source_input(rt[-1], "rt_latest"),
        ]
        if q75 is not None and rt[-1].value >= q75 and abs(esr[-1].value) < abs(esr[0].value):
            return "offer_flex", "Simulated price/trend heuristic requests flexibility.", inputs
        return action, reason, inputs
