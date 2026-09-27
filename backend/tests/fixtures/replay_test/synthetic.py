"""Build synthetic replay days and scoreboard checks. Not an external source."""

import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

CHI = ZoneInfo("America/Chicago")
POINTS = (
    "LZ_HOUSTON",
    "LZ_NORTH",
    "LZ_SOUTH",
    "LZ_WEST",
    "HB_HOUSTON",
    "HB_NORTH",
    "HB_SOUTH",
    "HB_WEST",
)
RETRIEVAL = "2026-09-26T20:00:00Z"
QUANTUM = Decimal("0.000001")

# Assumptions the tests bind (DEC-GM-113), so the implementer has one target:
# - Import surface is gridmarket_server.flex (Battery, StepResult, InformationSet,
#   Observation, FeedWindow, Decision, FixedSchedule, PriceBased, EsrInformed).
# - Nearest rank: 1-based k = ceil(p/100 * N), no interpolation.
# - PriceBased/EsrInformed inputs include dam_q25 and dam_q75 (USD/MWh) when the
#   zone's DAM vector for D is complete. Incomplete or missing DAM holds.
# - Those policies request feasible max AC kW (power and headroom/reserve).
# - Offer precedence beats charge. Q25 >= Q75 forces hold even if both fire.
# - Decreasing ESR charging magnitude means abs(latest) < abs(previous) on the
#   latest two complete bins (charging MW is negative). Source id "esr".
# - Library code uses Decimal. Replay JSON uses decimal strings for kWh/kW and
#   ints for cents. UTC timestamps end in Z.
# - run_id = sha256(json.dumps(binding, sort_keys=True, separators=(",", ":"),
#   ensure_ascii=False).encode()).hexdigest(). binding includes day, seed,
#   strategies, fleet, disruptions, dataset_digest, engine_version, policy_version.
# - Catalog root is $GRIDMARKET_REPLAY_DIR, read when the app is created.
# - Timeline quarters match the local-day UTC grid. decisions[].decision_time and
#   settlements[].delivery_start may sit on any entry; tests flatten them.
# - At a quarter start the engine settles that quarter's commitment, then decides
#   the next quarter. Procurement quarters start at 17:00–20:45 Central.
# - Pro-rata floors each share to 0.000001 kWh (ROUND_DOWN) and gives leftover
#   quanta to asset ids in lexicographic order. Dust below one quantum is dropped.
# - max_discharge_kw may be 0. load kw 0 means discharge is export and charge is import.
# - Scoreboard assets[] holds per-asset SoC. Top-level start/end SoC are sums.
#   Top-level min_reserve_kwh is the minimum configured reserve.
# - One preserve_backup caused by energy at or below reserve counts as one
#   attempted reserve violation and not an actual breach.
# - API errors use {"error": {"code", "message"}} with NOT_FOUND, VALIDATION_ERROR,
#   PAYLOAD_TOO_LARGE, RATE_LIMITED. Oversize is judged before schema validation.
# - provider_id is the fleet asset's id. Replay does not read live provider health.
#   A disruption provider/source that no asset or series uses is 422.
# - A 15-minute bin is complete at decision time when interval_end <= t.
# - The replay rate limiter reads time.monotonic. test_C3_evicts_after_20_runs advances
#   that clock; test_C3_rate_limit_is_429 does not.
# - Bodies larger than 2*1024*1024 bytes are 413.


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_bounds(day: str) -> tuple[datetime, datetime]:
    year, month, dom = (int(part) for part in day.split("-"))
    start = datetime(year, month, dom, tzinfo=CHI)
    return start, start + timedelta(days=1)


def quarters(day: str) -> list[tuple[datetime, datetime]]:
    start, end = local_bounds(day)
    cursor = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    rows = []
    while cursor < stop:
        nxt = cursor + timedelta(minutes=15)
        rows.append((cursor, nxt))
        cursor = nxt
    return rows


def hours(day: str) -> list[tuple[datetime, datetime]]:
    start, end = local_bounds(day)
    cursor = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    rows = []
    while cursor < stop:
        nxt = cursor + timedelta(hours=1)
        rows.append((cursor, nxt))
        cursor = nxt
    return rows


def dam_published(day: str) -> datetime:
    start, _end = local_bounds(day)
    previous = datetime.combine(start.date() - timedelta(days=1), datetime.min.time(), tzinfo=CHI)
    return previous.replace(hour=13, minute=30).astimezone(UTC)


def _row(
    series: str,
    source: str,
    value: Decimal,
    unit: str,
    start: datetime,
    end: datetime,
    available: datetime,
    zone: str,
    point: str | None,
) -> dict:
    stamp = iso(available)
    return {
        "series": series,
        "source": source,
        "settlement_point": point,
        "zone": zone,
        "value": format(value, "f"),
        "unit": unit,
        "interval_start": iso(start),
        "interval_end": iso(end),
        "published_at": stamp,
        "available_at": stamp,
        "retrieval_time": RETRIEVAL,
        "quality": "synthetic",
        "provenance": {
            "label": "synthetic",
            "claims_external_observation": False,
            "note": "Constructed test value. Not an ERCOT capture.",
        },
    }


def write_day(
    root: Path,
    day: str,
    *,
    rt: Decimal = Decimal(10),
    rt_at: dict[str, Decimal] | None = None,
    dam: Decimal | list[Decimal] = Decimal(10),
    include_esr: bool = True,
    esr: Decimal = Decimal(-50),
    esr_at: dict[str, Decimal] | None = None,
    load_mw: Decimal = Decimal(40000),
) -> Path:
    """Write manifest.json and observations.json. Override keys are interval-start Zulu."""
    folder = root / day
    folder.mkdir(parents=True, exist_ok=True)
    quarter_rows = quarters(day)
    hour_rows = hours(day)
    published = dam_published(day)
    observations: list[dict] = []
    if isinstance(dam, Decimal):
        dam_values = [dam] * len(hour_rows)
    else:
        if len(dam) != len(hour_rows):
            raise ValueError(f"{day} has {len(hour_rows)} hours, got {len(dam)} DAM prices")
        dam_values = dam
    for (start, end), price in zip(hour_rows, dam_values, strict=True):
        for point in POINTS:
            observations.append(
                _row("dam_spp", "dam_spp", price, "USD/MWh", start, end, published, point, point)
            )
        observations.append(
            _row(
                "load",
                "load",
                load_mw,
                "MW",
                start,
                end,
                end + timedelta(minutes=20),
                "ERCOT",
                None,
            )
        )
    for start, end in quarter_rows:
        key = iso(start)
        price = (rt_at or {}).get(key, rt)
        for point in POINTS:
            observations.append(
                _row(
                    "rt_spp",
                    "rt_spp",
                    price,
                    "USD/MWh",
                    start,
                    end,
                    end + timedelta(minutes=5),
                    point,
                    point,
                )
            )
        if include_esr:
            charging = (esr_at or {}).get(key, esr)
            observations.append(
                _row(
                    "esr_charging",
                    "esr",
                    charging,
                    "MW",
                    start,
                    end,
                    end,
                    "ERCOT",
                    None,
                )
            )
    gaps = [] if include_esr else ["esr"]
    manifest = {
        "day": day,
        "timezone": "America/Chicago",
        "label": "synthetic",
        "claims_external_observation": False,
        "quarters": len(quarter_rows),
        "hours": len(hour_rows),
        "gaps": gaps,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (folder / "observations.json").write_text(json.dumps(observations) + "\n")
    return folder


def run_id_of(binding: dict) -> str:
    payload = json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def cents(raw: Decimal) -> int:
    return int(raw.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def dec(value: object) -> Decimal:
    assert isinstance(value, str)
    return Decimal(value)


def money_ok(row: dict) -> None:
    net = (
        row["energy_value_cents"]
        - row["charging_cost_cents"]
        + row["flexibility_bonus_cents"]
        - row["shortfall_penalty_cents"]
        + row["terminal_energy_value_cents"]
        - row["opening_energy_value_cents"]
    )
    cash = (
        row["energy_value_cents"]
        - row["charging_cost_cents"]
        + row["flexibility_bonus_cents"]
        - row["shortfall_penalty_cents"]
    )
    assert row["net_value_cents"] == net
    assert row["cash_net_cents"] == cash
    assert isinstance(row["net_value_cents"], int)
    assert not isinstance(row["net_value_cents"], bool)


def score(body: dict, strategy: str) -> dict:
    rows = [row for row in body["scoreboard"] if row["strategy"] == strategy]
    assert len(rows) == 1
    return rows[0]


def flat(body: dict, key: str) -> list[dict]:
    rows: list[dict] = []
    for step in body["timeline"]:
        rows.extend(step[key])
    return rows


def no_timing_keys(value: object) -> None:
    banned = {"created_at", "started_at", "finished_at", "elapsed_ms", "duration_ms"}
    if isinstance(value, dict):
        assert banned.isdisjoint(value)
        for child in value.values():
            no_timing_keys(child)
    elif isinstance(value, list):
        for child in value:
            no_timing_keys(child)


def allocate(demand: Decimal, offers: dict[str, Decimal]) -> dict[str, Decimal]:
    """Contract assumption: floor to 0.000001 then lexicographic residual quanta."""
    total = sum(offers.values(), Decimal(0))
    if total <= demand:
        return dict(offers)
    raw = {asset_id: demand * qty / total for asset_id, qty in offers.items()}
    floored = {
        asset_id: amount.quantize(QUANTUM, rounding=ROUND_DOWN) for asset_id, amount in raw.items()
    }
    residual = demand - sum(floored.values(), Decimal(0))
    order = sorted(floored)
    index = 0
    while residual >= QUANTUM:
        floored[order[index % len(order)]] += QUANTUM
        residual -= QUANTUM
        index += 1
    return floored


def asset(**overrides: str) -> dict:
    row = {
        "asset_id": "synthetic-a",
        "provider_id": "base_sim",
        "capacity_kwh": "10",
        "initial_soc_kwh": "5",
        "min_reserve_kwh": "1",
        "max_charge_kw": "4",
        "max_discharge_kw": "4",
        "eta_round_trip": "1",
        "label": "synthetic",
    }
    row.update(overrides)
    return row


def body(
    day: str,
    strategies: list[str],
    assets: list[dict],
    seed: int = 1,
    disruptions: list[dict] | None = None,
    load_kw: str = "0",
) -> dict:
    start, end = local_bounds(day)
    return {
        "day": day,
        "strategies": strategies,
        "seed": seed,
        "disruptions": disruptions or [],
        "fleet": {
            "zone": "LZ_HOUSTON",
            "label": "synthetic",
            "assets": assets,
            "household_load": {
                "unit": "kW",
                "label": "synthetic",
                "intervals": [
                    {"interval_start": iso(start), "interval_end": iso(end), "kw": load_kw}
                ],
            },
        },
    }


def esr_dam(day: str) -> list[Decimal]:
    """Q25=10, Q75=100, mean=50. Local hours 16–20 are 40, so PriceBased holds then."""
    rows = hours(day)
    if len(rows) != 24:
        raise ValueError("esr_dam is the 24-hour example")
    prices = []
    for hour in range(24):
        if hour <= 5:
            prices.append(Decimal(10))
        elif 10 <= hour <= 20:
            prices.append(Decimal(40))
        else:
            prices.append(Decimal(100))
    return prices


def policy_dam() -> list[Decimal]:
    """Non-DST example. Sorted nearest-rank Q25=10 (tied) and Q75=100 (tied)."""
    prices = [Decimal(1)] * 4
    prices += [Decimal(10)] * 2
    prices.append(Decimal(200))
    prices += [Decimal(50)] * 11
    prices += [Decimal(100)] * 2
    prices += [Decimal(200)] * 4
    assert len(prices) == 24
    return prices


@contextmanager
def client(root: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridmarket_server import main

    monkeypatch.setenv("GRIDMARKET_DB", str(root / "replay.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_REPLAY_DIR", str(root))
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "20260926")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s68-replay-test")
    with TestClient(main.create_app()) as api:
        yield api


def post(api, payload: dict):
    return api.post("/v1/replay", json=payload)


def assert_public(body_json: dict) -> None:
    assert body_json["label"] == "synthetic"
    assert body_json["claims_external_observation"] is False
    assert "scoreboard" in body_json and "timeline" in body_json and "binding" in body_json
    no_timing_keys(body_json)
