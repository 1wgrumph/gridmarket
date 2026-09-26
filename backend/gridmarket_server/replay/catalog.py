"""DEC-GM-113 amendments 2, 3 and 13: replay day catalog and availability modes."""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from ..flex.information import Observation

CHI = ZoneInfo("America/Chicago")
ENGINE_VERSION = "C3/DEC-GM-127-A16"
POLICY_VERSION = "C2/DEC-GM-127-A16"
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
SOURCES = ("rt_spp", "dam_spp", "load", "esr")
DISCLAIMER = (
    "Historical ERCOT observations; simulated households, batteries, procurement and outcomes."
)
STRICT_NOTE = (
    "Strict no-lookahead: every decision used only observations with available_at <= decision_time."
)
ASSUMED_NOTE = (
    "Assumed availability (labelled sensitivity run, not a strict no-lookahead result): "
    "DAM prices treated as available 13:30 America/Chicago on D-1, real-time 15-minute "
    "prices 5 minutes after interval end, hourly load 20 minutes after interval end. "
    "ERCOT archives do not record original publication times, so strict no-lookahead "
    "is impossible on this dataset (DEC-GM-113 amendment 3)."
)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_bounds(day: str) -> tuple[datetime, datetime]:
    year, month, dom = (int(part) for part in day.split("-"))
    start = datetime(year, month, dom, tzinfo=CHI)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def quarters(day: str) -> list[tuple[datetime, datetime]]:
    start, stop = day_bounds(day)
    rows = []
    cursor = start
    while cursor < stop:
        nxt = cursor + timedelta(minutes=15)
        rows.append((cursor, nxt))
        cursor = nxt
    return rows


@dataclass
class DayData:
    day: str
    label: str
    synthetic: bool
    claims_external_observation: bool
    gaps: list[str]
    grid: list[tuple[datetime, datetime]]
    observations: list[Observation]
    rt: dict[tuple[str, datetime], Decimal]
    dam: dict[str, list[Decimal]]
    availability_mode: str
    availability_note: str
    dataset_digest: str
    peak: dict


def _moment(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError(f"Timestamp without offset: {value!r}")
    return moment.astimezone(UTC)


def _synthetic_day(folder: Path) -> DayData:
    manifest = json.loads((folder / "manifest.json").read_text())
    rows = json.loads((folder / "observations.json").read_text())
    observations = [
        Observation(
            series=row["series"],
            source=row["source"],
            value=Decimal(str(row["value"])) if row["value"] is not None else None,
            unit=row["unit"],
            interval_start=_moment(row["interval_start"]),
            interval_end=_moment(row["interval_end"]),
            published_at=_moment(row["published_at"]) if row["published_at"] else None,
            available_at=_moment(row["available_at"]) if row["available_at"] else None,
            quality=row["quality"],
            zone=row["zone"],
            settlement_point=row.get("settlement_point"),
            retrieval_time=_moment(row["retrieval_time"]) if row.get("retrieval_time") else None,
            provenance=row.get("provenance") or {},
        )
        for row in rows
    ]
    digest = hashlib.sha256()
    for name in ("manifest.json", "observations.json"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((folder / name).read_bytes())
    strict = bool(rows) and all(row.get("available_at") for row in rows)
    return _finish(
        day=manifest["day"],
        label=manifest.get("label", "synthetic"),
        synthetic=True,
        claims=bool(manifest.get("claims_external_observation", False)),
        gaps=list(manifest.get("gaps", [])),
        observations=observations,
        dataset_digest=digest.hexdigest(),
        strict=strict,
    )


def _real_day(folder: Path, day: str) -> DayData:
    meta = json.loads((folder / "meta.json").read_text())
    dam_release = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=CHI) - timedelta(days=1)
    dam_release = dam_release.replace(hour=13, minute=30).astimezone(UTC)
    series_of = {
        "rt_prices.json": ("rt_spp", "rt_spp"),
        "da_prices.json": ("dam_spp", "dam_spp"),
        "load.json": ("load", "load"),
        "esr.json": ("esr_charging", "esr"),
    }
    observations = []
    for name, (series, source) in series_of.items():
        payload = json.loads((folder / name).read_text())
        for row in payload.get("observations", []):
            start = _moment(row["interval_start"])
            end = _moment(row["interval_end"])
            if series == "dam_spp":
                available = dam_release
            elif series == "rt_spp":
                available = end + timedelta(minutes=5)
            else:
                available = end + timedelta(minutes=20)
            zone = "ERCOT" if series in ("load", "esr_charging") else row["point"]
            unit = payload.get("unit", "USD/MWh")
            if unit == "$/MWh":  # S67 archive label for the USD/MWh policy contract.
                unit = "USD/MWh"
            observations.append(
                Observation(
                    series=series,
                    source=source,
                    value=Decimal(str(row["value"])),
                    unit=unit,
                    interval_start=start,
                    interval_end=end,
                    published_at=available,
                    available_at=available,
                    quality=row.get("quality", ""),
                    zone=zone,
                    settlement_point=None if series in ("load", "esr_charging") else row["point"],
                    retrieval_time=_moment(row["retrieved_at"]),
                    provenance={
                        "source": row.get("provenance", {}).get("source", name),
                        "row": str(row.get("provenance", {}).get("row", "")),
                        "file": name,
                    },
                )
            )
    gap_codes = {g["code"] for g in meta["qualification"]["optional_gaps"]}
    gaps = [
        short
        for code, short in (("ESR_DAY_NOT_CAPTURED", "esr"), ("SCED_NOT_YET_PUBLISHED", "esr_soc"))
        if code in gap_codes
    ]
    digest = hashlib.sha256()
    for name in sorted(p.name for p in folder.iterdir() if p.suffix == ".json"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((folder / name).read_bytes())
    return _finish(
        day=day,
        label="ercot_public_archives",
        synthetic=False,
        claims=True,
        gaps=gaps,
        observations=observations,
        dataset_digest=digest.hexdigest(),
        strict=False,
    )


def _finish(
    *, day, label, synthetic, claims, gaps, observations, dataset_digest, strict
) -> DayData:
    grid = quarters(day)
    rt: dict[tuple[str, datetime], Decimal] = {}
    dam: dict[str, list[Decimal]] = {}
    peak = None
    for row in observations:
        if row.series == "rt_spp" and row.value is not None:
            key = (row.zone, row.interval_start)
            rt[key] = row.value
            candidate = (row.value, row.zone, row.interval_start)
            if peak is None or candidate > (peak[0], peak[1], peak[2]):
                peak = (row.value, row.zone, row.interval_start, row.interval_end)
        elif row.series == "dam_spp" and row.value is not None:
            dam.setdefault(row.zone, []).append(row.value)
    if peak is None:
        raise ValueError(f"Replay day {day} has no real-time prices")
    return DayData(
        day=day,
        label=label,
        synthetic=synthetic,
        claims_external_observation=claims,
        gaps=gaps,
        grid=grid,
        observations=observations,
        rt=rt,
        dam=dam,
        availability_mode="strict" if strict else "assumed",
        availability_note=STRICT_NOTE if strict else ASSUMED_NOTE,
        dataset_digest=dataset_digest,
        peak={
            "point": peak[1],
            "interval_start": iso(peak[2]),
            "interval_end": iso(peak[3]),
            "value": float(peak[0]),
            "unit": "USD/MWh",
        },
    )


def default_root() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "replay"


def load_catalog(root: Path | None = None) -> dict[str, DayData]:
    base = Path(os.getenv("GRIDMARKET_REPLAY_DIR", str(root or default_root())))
    days: dict[str, DayData] = {}
    if not base.is_dir():
        return days
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        if (folder / "manifest.json").is_file() and (folder / "observations.json").is_file():
            data = _synthetic_day(folder)
        elif (folder / "meta.json").is_file():
            data = _real_day(folder, folder.name)
        else:
            continue
        days[data.day] = data
    return days
