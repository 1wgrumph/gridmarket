"""Offline ML training-data helpers (stretch, DES-GM-ML, SEIT-GM-ML-01).

Never in the live data path: feature building from archived hour records,
Census/LODES population weights, and ERCOT Worker report fetches under the
lane's own <= 5 requests/min budget. Stdlib only, so owner-run training does
not need the app import chain.
"""

import csv
import gzip
import json
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

CHICAGO = ZoneInfo("America/Chicago")

# Allowlisted ERCOT Worker report routes (CONTRACTS.md, worker lane).
REPORT_ROUTES = (
    "/api/report/np6-905-cd/spp_node_zone_hub",
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
    "/api/report/np3-565-cd/lf_by_model_weather_zone",
    "/api/report/np3-233-cd/hourly_res_outage_cap",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
)
WORKER_KEY_HEADER = "x-gridmarket-key"
BUDGET_REQUESTS = 5
BUDGET_WINDOW_S = 60.0

_requests: list[float] = []


# Peak calendar mirrors scoring.on_peak (NERC 5x16 with Sunday-observed
# holidays); vendored so this offline module stays stdlib-only.


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last = next_month - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    return day + timedelta(days=1) if day.weekday() == 6 else day


def _holidays(year: int) -> set[date]:
    return {
        _observed(date(year, 1, 1)),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }


def peak_flag(instant: datetime) -> int:
    """1 for NERC 5x16 on-peak hours, else 0 (plain int, never bool)."""
    local = instant if instant.tzinfo is not None else instant.replace(tzinfo=CHICAGO)
    chicago = local.astimezone(CHICAGO)
    day = chicago.date()
    on_peak = (
        chicago.weekday() < 5
        and 7 <= chicago.hour < 23
        and day not in (_holidays(day.year) | _holidays(day.year - 1))
    )
    return int(on_peak)


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="")
    return open(path, newline="")


def zone_population_weight(
    wac_path: Path, rac_path: Path, county_zone: dict[str, str]
) -> dict[str, int]:
    """Daytime population weight per zone: sum of WAC C000 minus RAC C000."""
    totals = {zone: 0 for zone in county_zone.values()}
    for path, geocode_col in ((wac_path, "w_geocode"), (rac_path, "h_geocode")):
        sign = 1 if path == wac_path else -1
        with _open_text(Path(path)) as handle:
            reader = csv.DictReader(handle)
            geocode = (
                geocode_col
                if reader.fieldnames and geocode_col in reader.fieldnames
                else (reader.fieldnames or [""])[0]
            )
            for row in reader:
                county = (row.get(geocode) or "")[:5]
                zone = county_zone.get(county)
                if zone is not None:
                    totals[zone] += sign * int(row["C000"])
    return totals


def _county_zone(data_dir: Path) -> dict[str, str]:
    mapping = {}
    with open(data_dir / "county_zone.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            mapping[row["county"]] = row["zone"]
    return mapping


def build_features(data_dir: Path) -> list[dict]:
    """Build raw ML feature rows from archived hour records plus weights."""
    data_dir = Path(data_dir)
    hours = json.loads((data_dir / "hour.json").read_text())
    if isinstance(hours, dict):
        hours = [hours]
    weights = zone_population_weight(
        data_dir / "wac.csv.gz", data_dir / "rac.csv.gz", _county_zone(data_dir)
    )
    rows = []
    for hour in hours:
        instant = datetime.fromisoformat(hour["delivery_hour"])
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=CHICAGO)
        chicago = instant.astimezone(CHICAGO)
        rt_price = hour["rt_spp_last_hour"][-1]
        hub_price = hour["rt_spp_hubavg"]
        load = hour["load_forecast_next_24h"]
        outage = hour["outage_next_168h"]
        rows.append(
            {
                "zone": hour["zone"],
                "delivery_hour": hour["delivery_hour"],
                "hour_of_day": int(chicago.hour),
                "peak_flag": peak_flag(instant),
                "temperature": hour["temperature_f"],
                "price_spread": rt_price - hub_price,
                "load_pressure": load[0] - mean(load),
                "outage_pressure": outage[0] - median(outage),
                "congestion_pressure": (rt_price - hub_price) + 0.1 * sum(hour["shadow_prices"]),
                "population_weight": weights.get(hour["zone"], 0),
            }
        )
    return rows


def fetch_report(
    base_url: str, route: str, key: str | None = None, now: float | None = None
) -> dict:
    """GET one allowlisted Worker report under the lane's own 5/min budget."""
    if route not in REPORT_ROUTES:
        raise ValueError(f"route not allowlisted for ML fetch: {route}")
    at = time.time() if now is None else now
    recent = [stamp for stamp in _requests if stamp > at - BUDGET_WINDOW_S]
    if len(recent) >= BUDGET_REQUESTS:
        raise ValueError(
            f"ERCOT budget exceeded: {BUDGET_REQUESTS} requests per "
            f"{int(BUDGET_WINDOW_S)}s already used"
        )
    _requests.append(at)
    request = urllib.request.Request(
        base_url.rstrip("/") + route, headers={WORKER_KEY_HEADER: key or ""}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())
