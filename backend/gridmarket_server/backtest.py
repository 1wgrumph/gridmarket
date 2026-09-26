"""SEIT-GM-BT-01 backtest: score history days and report Spearman vs realized RT.

`python -m gridmarket_server.backtest --days N --end YYYY-MM-DD` fetches the
five allowlisted Worker report routes once each and scores load-zone hours
over delivery dates end-(N-1) through end. Stdout is one JSON object with
keys spearman, n, start, end plus a human-readable text line.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta

ROUTES = (
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
    "/api/report/np6-905-cd/spp_node_zone_hub",
    "/api/report/np3-565-cd/lf_by_model_weather_zone",
    "/api/report/np3-233-cd/hourly_res_outage_cap",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
)

ZONES = ("LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST")
WEATHER = {
    "LZ_HOUSTON": ("coast",),
    "LZ_NORTH": ("north", "northCentral", "east"),
    "LZ_SOUTH": ("southCentral", "southern"),
    "LZ_WEST": ("west", "farWest"),
}
OUTAGE = {
    "LZ_HOUSTON": "totalResourceMWZoneHouston",
    "LZ_NORTH": "totalResourceMWZoneNorth",
    "LZ_SOUTH": "totalResourceMWZoneSouth",
    "LZ_WEST": "totalResourceMWZoneWest",
}
WEIGHTS = {
    "price-spread": 0.18,
    "load-pressure": 0.18,
    "outage-pressure": 0.18,
    "congestion-pressure": 0.18,
    "heat-stress": 0.12,
    "peak-period": 0.08,
    "weather-alert": 0.08,
}

HUB = "HB_HUBAVG"


def fetch_reports(base_url: str, key: str) -> dict[str, list[dict]]:
    """GET each allowlisted report route exactly once; return field-zipped rows."""
    reports: dict[str, list[dict]] = {}
    for route in ROUTES:
        request = urllib.request.Request(base_url + route, headers={"x-gridmarket-key": key})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
        fields = [
            field["name"] if isinstance(field, dict) else field for field in payload["fields"]
        ]
        reports[route] = [dict(zip(fields, row, strict=True)) for row in payload["data"]]
    return reports


def _shift(day: str, hour_ending: int, steps: int) -> tuple[str, int]:
    start = datetime.fromisoformat(day) + timedelta(hours=hour_ending - 1 + steps)
    return start.date().isoformat(), start.hour + 1


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        rank = [0.0] * len(values)
        index = 0
        while index < len(values):
            end = index
            while end + 1 < len(values) and values[order[end + 1]] == values[order[index]]:
                end += 1
            average = (index + end) / 2 + 1
            for cursor in range(index, end + 1):
                rank[order[cursor]] = average
            index = end + 1
        return rank

    rx, ry = ranks(xs), ranks(ys)
    mean_x, mean_y = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    den = math.sqrt(sum((a - mean_x) ** 2 for a in rx) * sum((b - mean_y) ** 2 for b in ry))
    if den == 0:
        raise ValueError("undefined spearman")
    return num / den


def score_reports(reports: dict[str, list[dict]], days: int, end: str) -> dict | None:
    """Score history hours; None when fewer than `days` distinct dates score."""
    rt: dict[tuple[str, int, str], list[float]] = {}
    for row in reports["/api/report/np6-905-cd/spp_node_zone_hub"]:
        key = (row["deliveryDate"], int(row["deliveryHour"]), row["settlementPoint"])
        rt.setdefault(key, []).append(float(row["settlementPointPrice"]))
    means = {key: sum(vals) / len(vals) for key, vals in rt.items() if len(vals) == 4}
    dam = {
        (
            row["deliveryDate"],
            int(str(row["hourEnding"]).split(":")[0]),
            row["settlementPoint"],
        ): float(row["settlementPointPrice"])
        for row in reports["/api/report/np4-190-cd/dam_stlmnt_pnt_prices"]
    }
    load = {
        (row["deliveryDate"], int(str(row["hourEnding"]).split(":")[0]), name): float(row[name])
        for row in reports["/api/report/np3-565-cd/lf_by_model_weather_zone"]
        if row.get("inUseFlag", True)
        for names in WEATHER.values()
        for name in names
        if row.get(name) is not None
    }
    outage = {
        (row["operatingDate"], int(row["hourEnding"]), zone): float(row[column])
        for row in reports["/api/report/np3-233-cd/hourly_res_outage_cap"]
        for zone, column in OUTAGE.items()
        if row.get(column) is not None
    }
    # NP6-86 carries SCEDTimestamp, not a publishTime. The existing backtest
    # aggregates this report's shadow prices without using a publication time.
    shadow = sum(
        float(row["shadowPrice"])
        for row in reports["/api/report/np6-86-cd/shdw_prices_bnd_trns_const"]
    )
    end_day = date.fromisoformat(end)
    start_day = end_day - timedelta(days=days - 1)
    scores, realized, dates = [], [], []
    for (day, hour, zone), rt_price in sorted(means.items()):
        if zone not in ZONES or (day, hour, zone) not in dam:
            continue
        if not start_day <= date.fromisoformat(day) <= end_day:
            continue
        prev_day, prev_hour = _shift(day, hour, -1)
        if (prev_day, prev_hour, zone) not in means or (
            prev_day,
            prev_hour,
            HUB,
        ) not in means:
            continue
        if (day, hour, zone) not in outage or any(
            (day, hour, name) not in load for name in WEATHER[zone]
        ):
            continue
        load_vals, out_vals = [], []
        for step in range(24):
            d, h = _shift(day, hour, step)
            if all((d, h, name) in load for name in WEATHER[zone]):
                load_vals.append(sum(load[(d, h, name)] for name in WEATHER[zone]))
        for step in range(168):
            d, h = _shift(day, hour, step)
            if (d, h, zone) in outage:
                out_vals.append(outage[(d, h, zone)])
        if not load_vals or not out_vals:
            continue
        load_now = sum(load[(day, hour, name)] for name in WEATHER[zone])
        load_mean = sum(load_vals) / len(load_vals)
        out_now = outage[(day, hour, zone)]
        out_med = _median(out_vals)
        prev_rt = means[(prev_day, prev_hour, zone)]
        prev_hub = means[(prev_day, prev_hour, HUB)]
        local_hour = hour - 1
        peak = (
            -1
            if local_hour < 7 or local_hour >= 23 or date.fromisoformat(day).weekday() >= 5
            else 1
        )
        raw = {
            "price-spread": (dam[(day, hour, zone)] - prev_rt) / 50,
            "load-pressure": (load_now - load_mean) / max(0.1 * load_mean, 1),
            "outage-pressure": (out_now - out_med) / (0.1 * out_med + 100),
            "congestion-pressure": (prev_rt - prev_hub + 0.1 * shadow) / 25,
            "heat-stress": 0,
            "peak-period": peak,
            "weather-alert": 0,
        }
        total = sum(
            50 * weight * (raw[name] if name == "peak-period" else math.tanh(raw[name]))
            for name, weight in WEIGHTS.items()
        )
        scores.append(min(100, max(0, 50 + total)))
        realized.append(rt_price)
        dates.append(day)
    if len(set(dates)) < days:
        return None
    return {
        "spearman": _spearman(scores, realized),
        "n": len(scores),
        "start": min(dates),
        "end": max(dates),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gridmarket_server.backtest")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args(argv)
    base_url = os.environ.get("GRIDMARKET_WORKER_URL", "")
    key = os.environ.get("GRIDMARKET_WORKER_KEY", "")
    reports = fetch_reports(base_url, key)
    metrics = score_reports(reports, args.days, args.end)
    if metrics is None:
        print("INSUFFICIENT_HISTORY", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "spearman": metrics["spearman"],
                "n": metrics["n"],
                "start": metrics["start"],
                "end": metrics["end"],
            }
        )
    )
    print(
        f"Spearman {metrics['spearman']:.4f} n={metrics['n']} {metrics['start']}..{metrics['end']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
