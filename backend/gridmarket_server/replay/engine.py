"""DEC-GM-113 amendments 7, 8 and 9: simulated procurement, ledger, disruptions."""

import hashlib
import json
from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

from ..flex import Battery, EsrInformed, FixedSchedule, InformationSet, PriceBased
from ..flex.battery import ZERO
from ..flex.information import FeedWindow
from ..flex.policies import CHI as POLICY_CHI
from .catalog import DISCLAIMER, ENGINE_VERSION, POLICY_VERSION, iso

CHI = ZoneInfo("America/Chicago")
HOURS = Decimal("0.25")
QUANTUM = Decimal("0.000001")
BONUS_PER_MWH = Decimal(10)
PENALTY_PER_MWH = Decimal(100)
POLICIES = {
    "fixed_schedule": FixedSchedule,
    "price_based": PriceBased,
    "esr_informed": EsrInformed,
}


def fmt(value: Decimal) -> str:
    return format(value, "f")


def cents(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def allocate(demand: Decimal, offers: dict[str, Decimal]) -> dict[str, Decimal]:
    total = sum(offers.values(), ZERO)
    if not offers or total <= demand:
        return dict(offers)
    floored = {
        asset_id: (demand * qty / total).quantize(QUANTUM, rounding=ROUND_DOWN)
        for asset_id, qty in offers.items()
    }
    residual = demand - sum(floored.values(), ZERO)
    order = sorted(floored)
    index = 0
    while residual >= QUANTUM and order:
        floored[order[index % len(order)]] += QUANTUM
        residual -= QUANTUM
        index += 1
    return floored


def merge_windows(items: list[dict]) -> list[dict]:
    """Deterministically merge overlapping windows with the same type and key."""
    grouped: dict[tuple, list[dict]] = {}
    for item in items:
        key = (item["type"], item.get("provider_id", ""), item.get("source", ""))
        grouped.setdefault(key, []).append(item)
    merged = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda r: (r["start"], r["end"]))
        current = dict(rows[0])
        for row in rows[1:]:
            if row["start"] <= current["end"]:
                current["end"] = max(current["end"], row["end"])
            else:
                merged.append(current)
                current = dict(row)
        merged.append(current)
    merged.sort(
        key=lambda r: (r["type"], r.get("provider_id", ""), r.get("source", ""), r["start"])
    )
    return merged


def _memoize_request(policy):
    cache: dict[int, tuple] = {}
    inner = policy.request

    def request(view, zone, now):
        key = id(view)
        hit = cache.get(key)
        if hit is None:
            hit = inner(view, zone, now)
            cache[key] = hit
        action, reason, inputs = hit[0], hit[1], hit[2]
        return action, reason, list(inputs)

    policy.request = request
    return policy


class ReplayDataError(RuntimeError):
    """Required settlement data is missing; ranking is invalid, never zero."""


def build_binding(
    *,
    day_data,
    strategies: list[str],
    assets: list[dict],
    zone: str,
    load_intervals: list[dict],
    seed: int,
    merged: list[dict],
    fleet_label: str,
) -> tuple[dict, str]:
    binding = {
        "day": day_data.day,
        "seed": seed,
        "strategies": list(strategies),
        "fleet": {
            "zone": zone,
            "label": fleet_label,
            "assets": [
                {
                    "asset_id": spec["asset_id"],
                    "provider_id": spec["provider_id"],
                    "capacity_kwh": fmt(spec["capacity_kwh"]),
                    "initial_soc_kwh": fmt(spec["initial_soc_kwh"]),
                    "min_reserve_kwh": fmt(spec["min_reserve_kwh"]),
                    "max_charge_kw": fmt(spec["max_charge_kw"]),
                    "max_discharge_kw": fmt(spec["max_discharge_kw"]),
                    "eta_round_trip": fmt(spec["eta_round_trip"]),
                    "label": spec.get("label", "simulated"),
                }
                for spec in assets
            ],
            "household_load": {
                "unit": "kW",
                "label": fleet_label,
                "intervals": [
                    {
                        "interval_start": iso(row["start"]),
                        "interval_end": iso(row["end"]),
                        "kw": fmt(row["kw"]),
                    }
                    for row in sorted(load_intervals, key=lambda r: r["start"])
                ],
            },
        },
        "disruptions": [
            {
                "type": item["type"],
                **(
                    {"provider_id": item["provider_id"]}
                    if item["type"] == "provider_offline"
                    else {"source": item["source"]}
                ),
                "start": iso(item["start"]),
                "end": iso(item["end"]),
            }
            for item in merged
        ],
        "dataset_digest": day_data.dataset_digest,
        "engine_version": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
    }
    return binding, hashlib.sha256(canonical(binding)).hexdigest()


def run_replay(
    *,
    day_data,
    strategies: list[str],
    assets: list[dict],
    zone: str,
    load_intervals: list[dict],
    seed: int,
    disruptions: list[dict],
    fleet_label: str,
    binding: dict | None = None,
    run_id: str | None = None,
) -> bytes:
    grid = day_data.grid
    day_end = grid[-1][1]
    merged = merge_windows(disruptions)
    if binding is None or run_id is None:
        binding, run_id = build_binding(
            day_data=day_data,
            strategies=strategies,
            assets=assets,
            zone=zone,
            load_intervals=load_intervals,
            seed=seed,
            merged=merged,
            fleet_label=fleet_label,
        )
    provider_windows: dict[str, list[tuple]] = {}
    feed_windows: list[FeedWindow] = []
    for item in merged:
        if item["type"] == "provider_offline":
            provider_windows.setdefault(item["provider_id"], []).append(
                (item["start"], item["end"])
            )
        else:
            feed_windows.append(FeedWindow(item["source"], item["start"], item["end"]))

    def offline(provider_id: str, moment) -> bool:
        return any(start <= moment < end for start, end in provider_windows.get(provider_id, []))

    information = InformationSet(day_data.observations)
    views = [information.at(start, feed_interrupts=tuple(feed_windows)) for start, _ in grid]

    load_rows = sorted(load_intervals, key=lambda r: r["start"])

    def load_at(moment) -> Decimal:
        for row in load_rows:
            if row["start"] <= moment < row["end"]:
                return row["kw"]
        return ZERO

    rated_kw = sum((spec["max_discharge_kw"] for spec in assets), ZERO)
    demand_kwh = rated_kw * Decimal("0.25") * HOURS

    def demand_for(delivery_start) -> Decimal:
        if 17 <= delivery_start.astimezone(POLICY_CHI).hour < 21:
            return demand_kwh
        return ZERO

    dam_values = day_data.dam.get(zone, [])
    if not dam_values:
        raise ReplayDataError(f"No DAM prices for zone {zone}")
    valuation = max(ZERO, sum(dam_values, ZERO) / len(dam_values))

    policies = {name: _memoize_request(POLICIES[name]()) for name in strategies}
    timeline: list[dict] = [
        {"interval_start": iso(start), "interval_end": iso(end), "decisions": [], "settlements": []}
        for start, end in grid
    ]
    scoreboard = []
    for strategy in strategies:
        policy = policies[strategy]
        batteries = {
            spec["asset_id"]: Battery(
                asset_id=spec["asset_id"],
                capacity_kwh=spec["capacity_kwh"],
                soc_kwh=spec["initial_soc_kwh"],
                max_charge_kw=spec["max_charge_kw"],
                max_discharge_kw=spec["max_discharge_kw"],
                eta_round_trip=spec["eta_round_trip"],
                min_reserve_kwh=spec["min_reserve_kwh"],
                label=spec.get("label", "simulated"),
            )
            for spec in assets
        }
        reserved = dict.fromkeys(batteries, ZERO)
        commitments: dict[tuple[str, object], tuple[Decimal, Decimal]] = {}
        energy_base = charging_base = bonus_base = penalty_base = ZERO
        requested = accepted_total = delivered_total = shortfall_total = ZERO
        attempted = failed = breaches = 0
        start_soc = sum((b.soc_kwh for b in batteries.values()), ZERO)
        observed_min = start_soc
        providers = {spec["asset_id"]: spec["provider_id"] for spec in assets}
        for index, (start, end) in enumerate(grid):
            price = day_data.rt.get((zone, start))
            if price is None:
                raise ReplayDataError(f"Missing RT price for {zone} at {iso(start)}")
            load_kw = load_at(start)
            step = timeline[index]
            due = {
                aid: commitments.pop((aid, start))
                for aid in batteries
                if (aid, start) in commitments
            }
            current_kw = {
                aid: due.get(aid, (ZERO, ZERO))[1] / HOURS if aid in due else ZERO
                for aid in batteries
            }
            for asset_id, battery in batteries.items():
                if asset_id not in due:
                    continue
                req, acc = due[asset_id]
                reserved[asset_id] -= acc / battery.eta_d
                battery.reserved_dc_kwh = max(reserved[asset_id], ZERO)
                if offline(providers[asset_id], start):
                    delivered, shortfall, cause = ZERO, acc, "provider_offline"
                else:
                    result = battery.step(discharge_kw=acc / HOURS, hours=HOURS, load_kw=load_kw)
                    delivered, shortfall = result.discharge_ac_kwh, acc - result.discharge_ac_kwh
                    cause = None if shortfall <= QUANTUM else "insufficient_energy"
                    breaches += result.actual_breach
                energy_base += delivered * price / 10
                bonus_base += delivered * BONUS_PER_MWH / 10
                penalty_base += shortfall * PENALTY_PER_MWH / 10
                delivered_total += delivered
                shortfall_total += shortfall
                if shortfall > QUANTUM:
                    failed += 1
                step["settlements"].append(
                    {
                        "strategy": strategy,
                        "asset_id": asset_id,
                        "delivery_start": iso(start),
                        "delivery_end": iso(end),
                        "requested_kwh": fmt(req),
                        "accepted_kwh": fmt(acc),
                        "delivered_kwh": fmt(delivered),
                        "shortfall_kwh": fmt(shortfall),
                        "cause": cause,
                    }
                )
            observed_min = min(observed_min, sum((b.soc_kwh for b in batteries.values()), ZERO))
            offers: dict[str, Decimal] = {}
            for spec in assets:
                asset_id = spec["asset_id"]
                battery = batteries[asset_id]
                battery.reserved_dc_kwh = max(reserved[asset_id], ZERO)
                if offline(providers[asset_id], start):
                    step["decisions"].append(
                        {
                            "strategy": strategy,
                            "asset_id": asset_id,
                            "decision_time": iso(start),
                            "action": "hold",
                            "kw": fmt(ZERO),
                            "delivery_start": iso(start),
                            "delivery_end": iso(end),
                            "reason": (
                                f"provider_offline {providers[asset_id]}: new commitments and "
                                "dispatch blocked during the outage window."
                            ),
                            "policy_version": policy.policy_version,
                            "config": {"zone": zone, "blocked": "provider_offline"},
                            "inputs": [],
                        }
                    )
                    continue
                decision = policy.decide(
                    battery=battery,
                    information=views[index],
                    household_load_kw=load_kw,
                    config={
                        "zone": zone,
                        "current_commitment_kw": current_kw[asset_id],
                        "label": fleet_label,
                    },
                    decision_time=start,
                )
                attempted += bool(decision.attempted_reserve_violation)
                step["decisions"].append(
                    {
                        "strategy": strategy,
                        "asset_id": asset_id,
                        "decision_time": iso(decision.decision_time),
                        "action": decision.action,
                        "kw": fmt(decision.kw),
                        "delivery_start": iso(decision.delivery_start),
                        "delivery_end": iso(decision.delivery_end),
                        "reason": decision.reason,
                        "policy_version": decision.policy_version,
                        "config": _jsonable(decision.config),
                        "inputs": [
                            {
                                "name": item.name,
                                "value": fmt(item.value)
                                if isinstance(item.value, Decimal)
                                else item.value,
                                "unit": item.unit,
                                "source": item.source,
                                "interval_start": iso(item.interval_start),
                                "interval_end": iso(item.interval_end),
                                "published_at": iso(item.published_at),
                                "available_at": iso(item.available_at),
                                "quality": item.quality,
                            }
                            for item in decision.inputs
                        ],
                    }
                )
                if decision.action == "offer_flex" and decision.kw > 0:
                    if decision.delivery_end <= day_end:
                        offers[asset_id] = decision.kw * HOURS
                elif decision.action == "charge" and decision.kw > 0 and current_kw[asset_id] == 0:
                    result = battery.step(charge_kw=decision.kw, hours=HOURS, load_kw=load_kw)
                    charging_base += result.charge_ac_kwh * price / 10
                    breaches += result.actual_breach
            if offers:
                delivery_start = start + timedelta(minutes=15)
                accepted = allocate(demand_for(delivery_start), offers)
                for asset_id, qty in offers.items():
                    take = accepted.get(asset_id, ZERO)
                    commitments[(asset_id, delivery_start)] = (qty, take)
                    reserved[asset_id] += take / batteries[asset_id].eta_d
                    requested += qty
                    accepted_total += take
            observed_min = min(observed_min, sum((b.soc_kwh for b in batteries.values()), ZERO))
        if breaches:
            raise ReplayDataError("Actual reserve breach invalidates the run")
        opening_base = terminal_base = ZERO
        asset_rows = []
        for spec in assets:
            battery = batteries[spec["asset_id"]]
            for base, energy in (
                ("opening", spec["initial_soc_kwh"]),
                ("terminal", battery.soc_kwh),
            ):
                mark = battery.eta_d * max(energy - battery.min_reserve_kwh, ZERO) * valuation / 10
                if base == "opening":
                    opening_base += mark
                else:
                    terminal_base += mark
            asset_rows.append(
                {
                    "asset_id": spec["asset_id"],
                    "provider_id": spec["provider_id"],
                    "start_soc_kwh": fmt(spec["initial_soc_kwh"]),
                    "end_soc_kwh": fmt(battery.soc_kwh),
                    "min_reserve_kwh": fmt(battery.min_reserve_kwh),
                }
            )
        energy_value, charging_cost, bonus, penalty = (
            cents(energy_base),
            cents(charging_base),
            cents(bonus_base),
            cents(penalty_base),
        )
        opening, terminal = cents(opening_base), cents(terminal_base)
        net = energy_value - charging_cost + bonus - penalty + terminal - opening
        scoreboard.append(
            {
                "strategy": strategy,
                "net_value_cents": net,
                "cash_net_cents": energy_value - charging_cost + bonus - penalty,
                "energy_value_cents": energy_value,
                "charging_cost_cents": charging_cost,
                "flexibility_bonus_cents": bonus,
                "shortfall_penalty_cents": penalty,
                "opening_energy_value_cents": opening,
                "terminal_energy_value_cents": terminal,
                "energy_delivered_kwh": fmt(delivered_total),
                "requested_kwh": fmt(requested),
                "accepted_kwh": fmt(accepted_total),
                "delivered_kwh": fmt(delivered_total),
                "shortfall_kwh": fmt(shortfall_total),
                "min_reserve_kwh": fmt(min(spec["min_reserve_kwh"] for spec in assets)),
                "observed_min_soc_kwh": fmt(observed_min),
                "start_soc_kwh": fmt(start_soc),
                "end_soc_kwh": fmt(sum((b.soc_kwh for b in batteries.values()), ZERO)),
                "reserve_breach_count": 0,
                "attempted_reserve_violations": attempted,
                "failed_commitments": failed,
                "assets": asset_rows,
            }
        )
    body = {
        "run_id": run_id,
        "day": day_data.day,
        "label": day_data.label,
        "claims_external_observation": day_data.claims_external_observation,
        "disclaimer": DISCLAIMER,
        "availability_mode": day_data.availability_mode,
        "availability_note": day_data.availability_note,
        "binding": binding,
        "scoreboard": scoreboard,
        "timeline": timeline,
    }
    return canonical(body)


def _jsonable(value):
    if isinstance(value, Decimal):
        return fmt(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
