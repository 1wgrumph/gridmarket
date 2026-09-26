"""SEIT-GM-BT-01 red tests for `python -m gridmarket_server.backtest`.

`--days N --end YYYY-MM-DD` scores load-zone hours from the delivery date
`end - (N - 1)` through `end`. History comes from the five allowlisted Worker
report routes and header `x-gridmarket-key`. A scored hour has a DAM price and
four RT intervals for LZ_HOUSTON, LZ_NORTH, LZ_SOUTH, or LZ_WEST. Spearman is
against that hour's mean RT. Price-spread and congestion use the previous
hour's mean RT (HB_HUBAVG for the hub). NWS is not fetched (85 F, 0 alerts).
Missing load or outage hours are omitted, not zero-filled. Stdout is one JSON
object with keys spearman, n, start, end, plus a text line containing
Spearman, the correlation to 4 decimals, n, and both delivery dates. Fewer
than N distinct scored delivery dates exits non-zero and includes
INSUFFICIENT_HISTORY. Each allowlisted route is requested once (at most 5
requests in any 60 s). Raw report bodies are not written.
"""

import json
import math
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FULL = Path(__file__).resolve().parent / "fixtures" / "ercot_history"
SHORT = FULL / "short"
END = "2026-09-07"
DAYS = 7
KEY = "fixture-key"
PATHS = {
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices": "np4-190-cd.json",
    "/api/report/np6-905-cd/spp_node_zone_hub": "np6-905-cd.json",
    "/api/report/np3-565-cd/lf_by_model_weather_zone": "np3-565-cd.json",
    "/api/report/np3-233-cd/hourly_res_outage_cap": "np3-233-cd.json",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const": "np6-86-cd.json",
}
ZONES = ("LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST")
WEATHER = {
    "LZ_HOUSTON": ("Coast",),
    "LZ_NORTH": ("North", "North Central", "East"),
    "LZ_SOUTH": ("South Central", "Southern"),
    "LZ_WEST": ("West", "Far West"),
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


def _rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    fields = payload["fields"]
    return [dict(zip(fields, row, strict=True)) for row in payload["data"]]


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


def reference_metrics(root: Path, days: int, end: str) -> dict | None:
    rt: dict[tuple[str, int, str], list[float]] = {}
    for row in _rows(root / "np6-905-cd.json"):
        key = (row["deliveryDate"], int(row["deliveryHour"]), row["settlementPointName"])
        rt.setdefault(key, []).append(float(row["settlementPointPrice"]))
    means = {key: sum(vals) / len(vals) for key, vals in rt.items() if len(vals) == 4}
    dam = {
        (row["deliveryDate"], int(row["hourEnding"]), row["settlementPoint"]): float(
            row["settlementPointPrice"]
        )
        for row in _rows(root / "np4-190-cd.json")
    }
    load = {
        (row["deliveryDate"], int(row["hourEnding"]), row["weatherZone"]): float(
            row["loadForecast"]
        )
        for row in _rows(root / "np3-565-cd.json")
    }
    outage = {
        (row["deliveryDate"], int(row["hourEnding"]), row["loadZone"]): float(row["outageCapacity"])
        for row in _rows(root / "np3-233-cd.json")
    }
    shadow = sum(float(row["shadowPrice"]) for row in _rows(root / "np6-86-cd.json"))
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
            "HB_HUBAVG",
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
        prev_hub = means[(prev_day, prev_hour, "HB_HUBAVG")]
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


class _HistoryServer(ThreadingHTTPServer):
    def __init__(self, root: Path):
        self.root = root
        self.times: list[float] = []
        self.paths: list[str] = []
        self.lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server: _HistoryServer = self.server  # type: ignore[assignment]
        parsed = urllib.parse.urlsplit(self.path)
        name = PATHS.get(parsed.path)
        with server.lock:
            server.times.append(time.monotonic())
            server.paths.append(parsed.path)
        if name is None:
            self.send_error(404)
            return
        if self.headers.get("x-gridmarket-key") != KEY:
            self.send_error(401)
            return
        payload = json.loads((server.root / name).read_text())
        page = urllib.parse.parse_qs(parsed.query).get("page", ["1"])[0]
        if page not in {"", "1"}:
            payload = {**payload, "data": []}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def _run(root: Path, cwd: Path, days: int = DAYS, end: str = END):
    server = _HistoryServer(root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy()
    env["GRIDMARKET_WORKER_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
    env["GRIDMARKET_WORKER_KEY"] = KEY
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gridmarket_server.backtest",
                "--days",
                str(days),
                "--end",
                end,
            ],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    return proc, list(server.paths), list(server.times)


def _metrics(stdout: str) -> dict:
    found = [
        json.loads(line)
        for line in stdout.splitlines()
        if line.strip().startswith("{") and line.strip().endswith("}")
    ]
    assert len(found) == 1
    return found[0]


def _text_reports(stdout: str, expected: dict) -> None:
    rendered = f"{expected['spearman']:.4f}"
    assert any(
        not line.strip().startswith("{")
        and "Spearman" in line
        and rendered in line
        and str(expected["n"]) in line
        and expected["start"] in line
        and expected["end"] in line
        for line in stdout.splitlines()
    )


def test_seit_gm_bt_01_spearman_n_and_range(tmp_path: Path) -> None:
    import gridmarket_server.backtest  # noqa: F401

    expected = reference_metrics(FULL, DAYS, END)
    assert expected is not None
    proc, _paths, _times = _run(FULL, tmp_path)
    assert proc.returncode == 0, proc.stderr
    got = _metrics(proc.stdout)
    assert got["n"] == expected["n"]
    assert got["start"] == expected["start"]
    assert got["end"] == expected["end"]
    assert math.isclose(got["spearman"], expected["spearman"], abs_tol=1e-9)
    _text_reports(proc.stdout, expected)


def test_seit_gm_bt_01_metrics_only(tmp_path: Path) -> None:
    import gridmarket_server.backtest  # noqa: F401

    proc, _paths, _times = _run(FULL, tmp_path)
    assert proc.returncode == 0, proc.stderr
    got = _metrics(proc.stdout)
    assert set(got) == {"spearman", "n", "start", "end"}
    blob = proc.stdout + proc.stderr
    for marker in ("settlementPointPrice", "loadForecast", "outageCapacity", "shadowPrice"):
        assert marker not in blob
        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert marker not in path.read_text()


def test_seit_gm_bt_01_fewer_than_seven_days(tmp_path: Path) -> None:
    import gridmarket_server.backtest  # noqa: F401

    assert reference_metrics(SHORT, DAYS, END) is None
    proc, _paths, _times = _run(SHORT, tmp_path)
    assert proc.returncode != 0
    assert "INSUFFICIENT_HISTORY" in proc.stdout + proc.stderr


def test_seit_gm_bt_01_request_budget(tmp_path: Path) -> None:
    import gridmarket_server.backtest  # noqa: F401

    proc, paths, times = _run(FULL, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert sorted(paths) == sorted(PATHS)
    for stamp in times:
        assert sum(stamp - 60 < other <= stamp for other in times) <= 5


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
