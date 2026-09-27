"""DEC-GM-127 A16: bounded replay bodies and immutable decision drilldowns."""

import json
import threading
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Request, Response

from ..api import address, error_response
from ..flex import Battery
from . import engine
from .catalog import CHI, POINTS, SOURCES, load_catalog
from .engine import canonical

router = APIRouter()
MAX_BODY = 2 * 1024 * 1024
MAX_RUNS = 20
RATE_WINDOW = 60.0
RATE_LIMIT = 6
MAX_INFLIGHT = 2


class Invalid(Exception):
    pass


def _state(request: Request, name: str, factory):
    store = request.app.state
    value = getattr(store, name, None)
    if value is None:
        value = factory()
        setattr(store, name, value)
    return value


def _catalog(request: Request):
    return _state(request, "replay_catalog", load_catalog)


def _runs(request: Request):
    return _state(request, "replay_runs", dict)


def _hits(request: Request):
    return _state(request, "replay_hits", dict)


def _lock(request: Request):
    return _state(request, "replay_lock", threading.Lock)


def _moment(value: Any) -> datetime:
    if not isinstance(value, str):
        raise Invalid("Timestamp must be a string")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise Invalid(f"Bad timestamp: {value!r}") from None
    if moment.tzinfo is None:
        raise Invalid(f"Timestamp without offset: {value!r}")
    from datetime import UTC as _UTC

    return moment.astimezone(_UTC)


def _decimal(value: Any, name: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise Invalid(f"Bad decimal: {name}") from None
    if not result.is_finite():
        raise Invalid(f"Non-finite decimal: {name}")
    return result


def _validated(payload: Any, catalog) -> dict:
    if not isinstance(payload, dict):
        raise Invalid("Body must be an object")
    day = payload.get("day")
    data = catalog.get(day) if isinstance(day, str) else None
    if data is None:
        raise LookupError(day)
    strategies = payload.get("strategies")
    if (
        not isinstance(strategies, list)
        or not (1 <= len(strategies) <= 3)
        or not all(isinstance(name, str) for name in strategies)
        or len(set(strategies)) != len(strategies)
        or any(name not in engine.POLICIES for name in strategies)
    ):
        raise Invalid("strategies must be 1-3 distinct known policies")
    seed = payload.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise Invalid("seed must be an integer")
    fleet = payload.get("fleet")
    if not isinstance(fleet, dict):
        raise Invalid("fleet must be an object")
    zone = fleet.get("zone")
    if zone not in POINTS or zone not in data.dam:
        raise Invalid("Unknown fleet zone")
    raw_assets = fleet.get("assets")
    if not isinstance(raw_assets, list) or not (1 <= len(raw_assets) <= 1000):
        raise Invalid("fleet.assets must list 1-1000 assets")
    assets = []
    seen = set()
    for raw in raw_assets:
        if not isinstance(raw, dict):
            raise Invalid("Asset must be an object")
        asset_id, provider_id = raw.get("asset_id"), raw.get("provider_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise Invalid("asset_id must be a non-empty string")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise Invalid("provider_id must be a non-empty string")
        if asset_id in seen:
            raise Invalid("Assets need distinct non-empty ids")
        seen.add(asset_id)
        try:
            spec = {
                "asset_id": asset_id,
                "provider_id": provider_id,
                "capacity_kwh": _decimal(raw.get("capacity_kwh"), "capacity_kwh"),
                "initial_soc_kwh": _decimal(raw.get("initial_soc_kwh"), "initial_soc_kwh"),
                "min_reserve_kwh": _decimal(raw.get("min_reserve_kwh"), "min_reserve_kwh"),
                "max_charge_kw": _decimal(raw.get("max_charge_kw"), "max_charge_kw"),
                "max_discharge_kw": _decimal(raw.get("max_discharge_kw"), "max_discharge_kw"),
                "eta_round_trip": _decimal(raw.get("eta_round_trip"), "eta_round_trip"),
                "label": raw.get("label", "simulated"),
            }
            Battery(
                asset_id=asset_id,
                capacity_kwh=spec["capacity_kwh"],
                soc_kwh=spec["initial_soc_kwh"],
                max_charge_kw=spec["max_charge_kw"],
                max_discharge_kw=spec["max_discharge_kw"],
                eta_round_trip=spec["eta_round_trip"],
                min_reserve_kwh=spec["min_reserve_kwh"],
            )
        except (Invalid, ValueError):
            raise Invalid(f"Invalid asset {asset_id}") from None
        assets.append(spec)
    load = fleet.get("household_load")
    if load is None:
        # A16 simulated Texas summer shape: 28.8 kWh / 24 h = 1.2 kW.
        shape = ["0.7"] * 6 + ["1.0"] * 4 + ["1.2"] * 7 + ["2.0"] * 4 + ["1.4"] * 3
        load = {
            "unit": "kW",
            "intervals": [
                {
                    "interval_start": start.isoformat(),
                    "interval_end": end.isoformat(),
                    "kw": shape[start.astimezone(CHI).hour],
                }
                for start, end in data.grid
            ],
        }
    if not isinstance(load, dict) or load.get("unit", "kW") != "kW":
        raise Invalid("household_load must use kW")
    raw_intervals = load.get("intervals")
    if not isinstance(raw_intervals, list):
        raise Invalid("household_load.intervals must be a list")
    intervals = []
    for raw in raw_intervals:
        if not isinstance(raw, dict):
            raise Invalid("load interval must be an object")
        start, end = _moment(raw.get("interval_start")), _moment(raw.get("interval_end"))
        if end <= start:
            raise Invalid("load interval must be positive")
        intervals.append({"start": start, "end": end, "kw": _decimal(raw.get("kw"), "kw")})
        if intervals[-1]["kw"] < 0:
            raise Invalid("load kw must be nonnegative")
    raw_disruptions = payload.get("disruptions", [])
    if not isinstance(raw_disruptions, list) or len(raw_disruptions) > 20:
        raise Invalid("disruptions must list 0-20 windows")
    providers = {spec["provider_id"] for spec in assets}
    day_start, day_end = data.grid[0][0], data.grid[-1][1]
    allowed = {start for start, _ in data.grid} | {day_end}
    disruptions = []
    for raw in raw_disruptions:
        if not isinstance(raw, dict):
            raise Invalid("disruption must be an object")
        kind = raw.get("type")
        start, end = _moment(raw.get("start")), _moment(raw.get("end"))
        if (
            end <= start
            or start not in allowed
            or end not in allowed
            or not (day_start <= start and end <= day_end)
        ):
            raise Invalid("disruption window must align to quarters within the day")
        if kind == "provider_offline":
            if raw.get("provider_id") not in providers:
                raise Invalid("Unknown disruption provider")
            disruptions.append(
                {"type": kind, "provider_id": raw["provider_id"], "start": start, "end": end}
            )
        elif kind == "feed_interrupt":
            if raw.get("source") not in SOURCES:
                raise Invalid("Unknown disruption source")
            disruptions.append({"type": kind, "source": raw["source"], "start": start, "end": end})
        else:
            raise Invalid("Unknown disruption type")
    return {
        "data": data,
        "strategies": strategies,
        "seed": seed,
        "assets": assets,
        "zone": zone,
        "intervals": intervals,
        "disruptions": disruptions,
        "fleet_label": fleet.get("label", "simulated"),
    }


@router.get("/v1/replay/days")
def replay_days(request: Request):
    catalog = _catalog(request)
    return Response(
        canonical(
            {
                "days": [
                    {
                        "day": data.day,
                        "timezone": "America/Chicago",
                        "quarters": len(data.grid),
                        "gaps": data.gaps,
                        "synthetic": data.synthetic,
                        "claims_external_observation": data.claims_external_observation,
                        "label": data.label,
                        "availability_mode": data.availability_mode,
                        "availability_note": data.availability_note,
                        "peak_rt_price": data.peak,
                        "dataset_digest": data.dataset_digest,
                    }
                    for _, data in sorted(catalog.items())
                ]
            }
        ),
        media_type="application/json",
    )


@router.post("/v1/replay")
async def create_replay(request: Request):
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return error_response(413, "PAYLOAD_TOO_LARGE")
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        return error_response(422, "VALIDATION_ERROR")
    try:
        checked = _validated(payload, _catalog(request))
    except LookupError:
        return error_response(404, "NOT_FOUND", "Unknown replay day")
    except Invalid as exc:
        return error_response(422, "VALIDATION_ERROR", str(exc))
    binding, run_id = engine.build_binding(
        day_data=checked["data"],
        strategies=checked["strategies"],
        assets=checked["assets"],
        zone=checked["zone"],
        load_intervals=checked["intervals"],
        seed=checked["seed"],
        merged=engine.merge_windows(checked["disruptions"]),
        fleet_label=checked["fleet_label"],
    )
    with _lock(request):
        stored = _runs(request).get(run_id)
    if stored is not None:
        return Response(stored[0], media_type="application/json")
    client = address(request)
    now = time.monotonic()
    with _lock(request):
        hits = _hits(request)
        recent = [stamp for stamp in hits.get(client, []) if now - stamp < RATE_WINDOW]
        if len(recent) >= RATE_LIMIT:
            hits[client] = recent
            return error_response(429, "RATE_LIMITED")
        recent.append(now)
        hits[client] = recent
        inflight = getattr(request.app.state, "replay_inflight", 0)
        if inflight >= MAX_INFLIGHT:
            return error_response(429, "RATE_LIMITED")
        request.app.state.replay_inflight = inflight + 1
    try:
        body = engine.run_replay(
            day_data=checked["data"],
            strategies=checked["strategies"],
            assets=checked["assets"],
            zone=checked["zone"],
            load_intervals=checked["intervals"],
            seed=checked["seed"],
            disruptions=checked["disruptions"],
            fleet_label=checked["fleet_label"],
            binding=binding,
            run_id=run_id,
        )
    except engine.ReplayDataError as exc:
        return error_response(500, "INTERNAL_ERROR", str(exc))
    finally:
        with _lock(request):
            request.app.state.replay_inflight -= 1
    with _lock(request):
        runs = _runs(request)
        runs.pop(run_id, None)
        runs[run_id] = (body, checked)
        while len(runs) > MAX_RUNS:
            runs.pop(next(iter(runs)))
    return Response(body, media_type="application/json")


@router.get("/v1/replay/{run_id}")
def get_replay(request: Request, run_id: str):
    stored = _runs(request).get(run_id)
    if stored is None:
        return error_response(404, "NOT_FOUND", "Unknown run")
    return Response(stored[0], media_type="application/json")


@router.get("/v1/replay/{run_id}/decisions")
def get_decisions(request: Request, run_id: str, strategy: str, asset: str, start: str, end: str):
    """A16: reproduce one home's decisions from immutable inputs; [start,end), <=500 rows."""
    with _lock(request):
        stored = _runs(request).get(run_id)
    if stored is None:
        return error_response(404, "NOT_FOUND", "Unknown run")
    body, checked = stored
    try:
        lo, hi = _moment(start), _moment(end)
        grid = checked["data"].grid
        if (
            strategy not in checked["strategies"]
            or asset not in {a["asset_id"] for a in checked["assets"]}
            or not grid[0][0] <= lo < hi <= grid[-1][1]
            or sum(lo <= t < hi for t, _ in grid) > 500
        ):
            raise Invalid("Unknown strategy/asset or invalid decision range")
    except Invalid as exc:
        return error_response(422, "VALIDATION_ERROR", str(exc))
    original = json.loads(body)
    if asset == original["sample_asset_id"]:
        result = original
    else:
        with _lock(request):
            inflight = getattr(request.app.state, "replay_inflight", 0)
            if inflight >= MAX_INFLIGHT:
                return error_response(429, "RATE_LIMITED")
            request.app.state.replay_inflight = inflight + 1
        # ponytail: replay per drilldown; cache bounded traces if latency becomes limiting.
        try:
            result = json.loads(
                engine.run_replay(
                    day_data=checked["data"],
                    strategies=[strategy],
                    assets=checked["assets"],
                    zone=checked["zone"],
                    load_intervals=checked["intervals"],
                    seed=checked["seed"],
                    disruptions=checked["disruptions"],
                    fleet_label=checked["fleet_label"],
                    binding=original["binding"],
                    run_id=run_id,
                    sample_asset=asset,
                )
            )
        finally:
            with _lock(request):
                request.app.state.replay_inflight -= 1
    rows = [
        row
        for step in result["timeline"]
        for row in step["decisions"]
        if row["strategy"] == strategy and lo <= _moment(row["decision_time"]) < hi
    ]
    return Response(canonical({"run_id": run_id, "decisions": rows}), media_type="application/json")
